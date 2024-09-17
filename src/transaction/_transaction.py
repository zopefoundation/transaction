############################################################################
#
# Copyright (c) 2004 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
############################################################################
import logging
import sys
import threading
import traceback
import warnings
import weakref
from io import StringIO

from zope.interface import implementer

from transaction import interfaces
from transaction.interfaces import TransactionFailedError
from transaction.weakset import WeakSet


_marker = object()

_TB_BUFFER = None  # unittests may hook


def _makeTracebackBuffer():  # pragma NO COVER
    if _TB_BUFFER is not None:
        return _TB_BUFFER
    return StringIO()


_LOGGER = None  # unittests may hook


def _makeLogger():  # pragma NO COVER
    if _LOGGER is not None:
        return _LOGGER
    return logging.getLogger("txn.%d" % threading.get_ident())


class Status:
    # ACTIVE is the initial state.
    ACTIVE = "Active"

    COMMITTING = "Committing"
    COMMITTED = "Committed"

    DOOMED = "Doomed"

    # commit() or commit(True) raised an exception.  All further attempts
    # to commit or join this transaction will raise TransactionFailedError.
    COMMITFAILED = "Commit failed"


class _NoSynchronizers:

    @staticmethod
    def map(_f):
        """Do nothing."""


@implementer(interfaces.ITransaction)
class Transaction:
    """Default implementation of `~transaction.interfaces.ITransaction`."""

    # Assign an index to each savepoint so we can invalidate later savepoints
    # on rollback.  The first index assigned is 1, and it goes up by 1 each
    # time.
    _savepoint_index = 0

    # If savepoints are used, keep a weak key dict of them.  This maps a
    # savepoint to its index (see above).
    _savepoint2index = None

    # Meta data. extended_info is also metadata, but is initialized to an
    # empty dict in __init__.
    _user = ""
    _description = ""

    def __init__(self, synchronizers=None, manager=None):
        self.status = Status.ACTIVE
        # List of resource managers, e.g. MultiObjectResourceAdapters.
        self._resources = []

        # Weak set of synchronizer objects to call.
        if synchronizers is None:
            synchronizers = WeakSet()
        self._synchronizers = synchronizers

        self._manager = manager

        # _adapters: Connection/_p_jar -> MultiObjectResourceAdapter[Sub]
        self._adapters = {}
        self._voted = {}  # id(Connection) -> boolean, True if voted
        # _voted and other dictionaries use the id() of the resource
        # manager as a key, because we can't guess whether the actual
        # resource managers will be safe to use as dict keys.

        # The user, description, and extension attributes are accessed
        # directly by storages, leading underscore notwithstanding.
        self.extension = {}

        self.log = _makeLogger()
        self.log.debug("new transaction")

        # If a commit fails, the traceback is saved in _failure_traceback.
        # If another attempt is made to commit, TransactionFailedError is
        # raised, incorporating this traceback.
        self._failure_traceback = None

        # List of (hook, args, kws) tuples added by addBeforeCommitHook().
        self._before_commit = []

        # List of (hook, args, kws) tuples added by addAfterCommitHook().
        self._after_commit = []

        # List of (hook, args, kws) tuples added by addBeforeAbortHook().
        self._before_abort = []

        # List of (hook, args, kws) tuples added by addAfterAbortHook().
        self._after_abort = []

    @property
    def _extension(self):
        # for backward compatibility, since most clients used this
        # absent any formal API.
        return self.extension

    @_extension.setter
    def _extension(self, v):
        self.extension = v

    @property
    def user(self):
        return self._user

    @user.setter
    def user(self, v):
        if v is None:
            raise ValueError("user must not be None")
        self._user = text_or_warn(v)

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, v):
        if v is not None:
            self._description = text_or_warn(v)

    def isDoomed(self):
        """See `~transaction.interfaces.ITransaction`."""
        return self.status is Status.DOOMED

    def doom(self):
        """See `~transaction.interfaces.ITransaction`."""
        if self.status is not Status.DOOMED:
            if self.status is not Status.ACTIVE:
                # should not doom transactions in the middle,
                # or after, a commit
                raise ValueError('non-doomable')
            self.status = Status.DOOMED

    # Raise TransactionFailedError, due to commit()/join()/register()
    # getting called when the current transaction has already suffered
    # a commit/savepoint failure.
    def _prior_operation_failed(self):
        assert self._failure_traceback is not None
        raise TransactionFailedError(
            "An operation previously failed, with traceback:\n\n%s" %
            self._failure_traceback.getvalue())

    def join(self, resource):
        """See `~transaction.interfaces.ITransaction`."""
        if self.status is Status.COMMITFAILED:
            self._prior_operation_failed()  # doesn't return

        if (self.status is not Status.ACTIVE and
                self.status is not Status.DOOMED):
            # TODO: Should it be possible to join a committing transaction?
            # I think some users want it.
            raise ValueError(
                f"expected txn status {Status.ACTIVE!r} or {Status.DOOMED!r},"
                f" but it's {self.status!r}")
        self._resources.append(resource)

        if self._savepoint2index:
            # A data manager has joined a transaction *after* a savepoint
            # was created.  A couple of things are different in this case:
            #
            # 1. We need to add its savepoint to all previous savepoints.
            # so that if they are rolled back, we roll this one back too.
            #
            # 2. We don't actually need to ask the data manager for a
            # savepoint:  because it's just joining, we can just abort it to
            # roll back to the current state, so we simply use an
            # AbortSavepoint.
            datamanager_savepoint = AbortSavepoint(resource, self)
            for transaction_savepoint in self._savepoint2index.keys():
                transaction_savepoint._savepoints.append(
                    datamanager_savepoint)

    def _unjoin(self, resource):
        # Leave a transaction because a savepoint was rolled back on a resource
        # that joined later.

        # Don't use remove.  We don't want to assume anything about __eq__.
        self._resources = [r for r in self._resources if r is not resource]

    def savepoint(self, optimistic=False):
        """See `~transaction.interfaces.ITransaction`."""
        if self.status is Status.COMMITFAILED:
            self._prior_operation_failed()  # doesn't return, it raises

        try:
            savepoint = Savepoint(self, optimistic, *self._resources)
        except:  # noqa: E722 do not use bare 'except'
            self._cleanup(self._resources)
            self._saveAndRaiseCommitishError()  # reraises!

        if self._savepoint2index is None:
            self._savepoint2index = weakref.WeakKeyDictionary()
        self._savepoint_index += 1
        self._savepoint2index[savepoint] = self._savepoint_index

        return savepoint

    # Remove and invalidate all savepoints we know about with an index
    # larger than `savepoint`'s.  This is what's needed when a rollback
    # _to_ `savepoint` is done.
    def _remove_and_invalidate_after(self, savepoint):
        savepoint2index = self._savepoint2index
        index = savepoint2index[savepoint]
        # use list(items()) to make copy to avoid mutating while iterating
        for savepoint, i in list(savepoint2index.items()):
            if i > index:
                savepoint.transaction = None  # invalidate
                del savepoint2index[savepoint]

    # Invalidate and forget about all savepoints.
    def _invalidate_all_savepoints(self):
        for savepoint in self._savepoint2index.keys():
            savepoint.transaction = None  # invalidate
        self._savepoint2index.clear()

    def commit(self):
        """See `~transaction.interfaces.ITransaction`."""
        if self.status is Status.DOOMED:
            raise interfaces.DoomedTransaction(
                'transaction doomed, cannot commit')

        if self._savepoint2index:
            self._invalidate_all_savepoints()

        if self.status is Status.COMMITFAILED:
            self._prior_operation_failed()  # doesn't return

        self._callBeforeCommitHooks()

        self._synchronizers.map(lambda s: s.beforeCompletion(self))
        self.status = Status.COMMITTING

        try:
            self._commitResources()
            self.status = Status.COMMITTED
        except:  # noqa: E722 do not use bare 'except'
            t = None
            v = None
            tb = None
            try:
                t, v, tb = self._saveAndGetCommitishError()
                self._callAfterCommitHooks(status=False)
                raise v.with_traceback(tb)
            finally:
                del t, v, tb
        else:
            self._synchronizers.map(lambda s: s.afterCompletion(self))
            self._callAfterCommitHooks(status=True)
            self._free()
        self.log.debug("commit")

    def _saveAndGetCommitishError(self):
        self.status = Status.COMMITFAILED
        # Save the traceback for TransactionFailedError.
        ft = self._failure_traceback = _makeTracebackBuffer()
        t = None
        v = None
        tb = None
        try:
            t, v, tb = sys.exc_info()
            # Record how we got into commit().
            traceback.print_stack(sys._getframe(1), None, ft)
            # Append the stack entries from here down to the exception.
            traceback.print_tb(tb, None, ft)
            # Append the exception type and value.
            ft.writelines(traceback.format_exception_only(t, v))
            return t, v, tb
        finally:
            del t, v, tb

    def _saveAndRaiseCommitishError(self):
        t = None
        v = None
        tb = None
        try:
            t, v, tb = self._saveAndGetCommitishError()
            raise v.with_traceback(tb)
        finally:
            del t, v, tb

    def getBeforeCommitHooks(self):
        """See `~transaction.interfaces.ITransaction`."""
        return iter(self._before_commit)

    def addBeforeCommitHook(self, hook, args=(), kws=None):
        """See `~transaction.interfaces.ITransaction`."""
        if kws is None:
            kws = {}
        self._before_commit.append((hook, tuple(args), kws))

    def _callBeforeCommitHooks(self):
        # Call all hooks registered, allowing further registrations
        # during processing.
        self._call_hooks(self._before_commit)

    def getAfterCommitHooks(self):
        """See `~transaction.interfaces.ITransaction`."""
        return iter(self._after_commit)

    def addAfterCommitHook(self, hook, args=(), kws=None):
        """See `~transaction.interfaces.ITransaction`."""
        if kws is None:
            kws = {}
        self._after_commit.append((hook, tuple(args), kws))

    def _callAfterCommitHooks(self, status=True):
        self._call_hooks(self._after_commit,
                         exc=False, clean=True, prefix_args=(status,))

    def _call_hooks(self, hooks, exc=True, clean=False, prefix_args=()):
        """Call *hooks*.

        If *exc* is true, fail on the first exception; otherwise
        log the exception and continue.

        If *clean* is true, abort all resources. This is to ensure
        a clean state should a (after) hook has affected one
        of the resources.

        *prefix_args* defines additional arguments prefixed
        to the arguments provided by the hook definition.

        ``_call_hooks`` supports that a hook adds new hooks.
        """
        # Avoid to abort anything at the end if no hooks are registered.
        if not hooks:
            return
        try:
            # Call all hooks registered, allowing further registrations
            # during processing
            for hook, args, kws in hooks:
                try:
                    hook(*(prefix_args + args), **kws)
                except:  # noqa: E722 do not use bare 'except'
                    if exc:
                        raise
                    # We should not fail
                    self.log.error("Error in hook exec in %s ",
                                   hook, exc_info=sys.exc_info())
        finally:
            del hooks[:]  # clear hooks
            if clean:
                # The primary operation has already been performed.
                # But the hooks execution might have left the resources
                # in an unclean state. Clean up
                for rm in self._resources:
                    try:
                        rm.abort(self)
                    except:  # noqa: E722 do not use bare 'except'
                        # XXX should we take further actions here ?
                        self.log.error("Error in abort() on manager %s",
                                       rm, exc_info=sys.exc_info())

    def getBeforeAbortHooks(self):
        """See `~transaction.interfaces.ITransaction`."""
        return iter(self._before_abort)

    def addBeforeAbortHook(self, hook, args=(), kws=None):
        """See `~transaction.interfaces.ITransaction`."""
        if kws is None:
            kws = {}
        self._before_abort.append((hook, tuple(args), kws))

    def _callBeforeAbortHooks(self):
        # Call all hooks registered, allowing further registrations
        # during processing.
        self._call_hooks(self._before_abort, exc=False)

    def getAfterAbortHooks(self):
        """See `~transaction.interfaces.ITransaction`."""
        return iter(self._after_abort)

    def addAfterAbortHook(self, hook, args=(), kws=None):
        """See `~transaction.interfaces.ITransaction`."""
        if kws is None:
            kws = {}
        self._after_abort.append((hook, tuple(args), kws))

    def _callAfterAbortHooks(self):
        self._call_hooks(self._after_abort, clean=True)

    def _commitResources(self):
        # Execute the two-phase commit protocol.

        L = list(self._resources)
        L.sort(key=rm_key)
        try:
            for rm in L:
                rm.tpc_begin(self)
            for rm in L:
                rm.commit(self)
                self.log.debug("commit %r", rm)
            for rm in L:
                rm.tpc_vote(self)
                self._voted[id(rm)] = True

            try:
                for rm in L:
                    rm.tpc_finish(self)
            except:  # noqa: E722 do not use bare 'except'
                # TODO: do we need to make this warning stronger?
                # TODO: It would be nice if the system could be configured
                # to stop committing transactions at this point.
                self.log.critical("A storage error occurred during the second "
                                  "phase of the two-phase commit.  Resources "
                                  "may be in an inconsistent state.")
                raise
        except:  # noqa: E722 do not use bare 'except'
            # If an error occurs committing a transaction, we try
            # to revert the changes in each of the resource managers.
            t, v, tb = sys.exc_info()
            try:
                try:
                    self._cleanup(L)
                finally:
                    self._synchronizers.map(lambda s: s.afterCompletion(self))
                raise v.with_traceback(tb)
            finally:
                del t, v, tb

    def _cleanup(self, L):
        # Called when an exception occurs during tpc_vote or tpc_finish.
        for rm in L:
            if id(rm) not in self._voted:
                try:
                    rm.abort(self)
                except Exception:
                    self.log.error("Error in abort() on manager %s",
                                   rm, exc_info=sys.exc_info())
        for rm in L:
            try:
                rm.tpc_abort(self)
            except Exception:
                self.log.error("Error in tpc_abort() on manager %s",
                               rm, exc_info=sys.exc_info())

    def _free_manager(self):
        try:
            if self._manager:
                self._manager.free(self)
        finally:
            # If we try to abort a transaction and fail, the manager
            # may have begun a new transaction, and will raise a
            # ValueError from free(); we don't want that to happen
            # again in _free(), which abort() always calls, so be sure
            # to clear out the manager.
            self._manager = None

    def _free(self):
        # Called when the transaction has been committed or aborted
        # to break references---this transaction object will not be returned
        # as the current transaction from its manager after this, and all
        # IDatamanager objects joined to it will forgotten
        # All hooks and data are forgotten.
        self._free_manager()

        if hasattr(self, '_data'):
            delattr(self, '_data')

        del self._resources[:]

        del self._before_commit[:]
        del self._after_commit[:]
        del self._before_abort[:]
        del self._after_abort[:]

        # self._synchronizers might be shared, we can't mutate it
        self._synchronizers = _NoSynchronizers
        self._adapters = None
        self._voted = None
        self.extension = None

    def data(self, ob):
        try:
            data = self._data
        except AttributeError:
            raise KeyError(ob)

        try:
            return data[id(ob)]
        except KeyError:
            raise KeyError(ob)

    def set_data(self, ob, ob_data):
        try:
            data = self._data
        except AttributeError:
            data = self._data = {}

        data[id(ob)] = ob_data

    def abort(self):
        """See `~transaction.interfaces.ITransaction`."""
        try:
            t = None
            v = None
            tb = None

            self._callBeforeAbortHooks()
            if self._savepoint2index:
                self._invalidate_all_savepoints()

            try:
                self._synchronizers.map(lambda s: s.beforeCompletion(self))
            except:  # noqa: E722 do not use bare 'except'
                t, v, tb = sys.exc_info()
                self.log.error(
                    "Failed to call synchronizers", exc_info=sys.exc_info())

            for rm in self._resources:
                try:
                    rm.abort(self)
                except:  # noqa: E722 do not use bare 'except'
                    if tb is None:
                        t, v, tb = sys.exc_info()
                    self.log.error("Failed to abort resource manager: %s",
                                   rm, exc_info=sys.exc_info())

            self._callAfterAbortHooks()
            # Unlike in commit(), we are no longer the current transaction
            # when we call afterCompletion(). But we can't be completely
            # _free(): the synchronizer might want to access some data it set
            # before.
            self._free_manager()

            self._synchronizers.map(lambda s: s.afterCompletion(self))

            self.log.debug("abort")

            if tb is not None:
                raise v.with_traceback(tb)
        finally:
            self._free()
            del t, v, tb

    def note(self, text):
        """See `~transaction.interfaces.ITransaction`."""
        if text is not None:
            text = text_or_warn(text).strip()
            if self.description:
                self.description += "\n" + text
            else:
                self.description = text

    def setUser(self, user_name, path="/"):
        """See `~transaction.interfaces.ITransaction`."""
        self.user = f"{text_or_warn(path)} {text_or_warn(user_name)}"

    def setExtendedInfo(self, name, value):
        """See `~transaction.interfaces.ITransaction`."""
        self.extension[name] = value

    def isRetryableError(self, error):
        return self._manager._retryable(type(error), error)


# TODO: We need a better name for the adapters.


def rm_key(rm):
    func = getattr(rm, 'sortKey', None)
    if func is not None:
        return func()


@implementer(interfaces.ISavepoint)
class Savepoint:
    """Implementation of `~transaction.interfaces.ISavepoint`, a transaction
    savepoint.

    Transaction savepoints coordinate savepoints for data managers
    participating in a transaction.
    """

    def __init__(self, transaction, optimistic, *resources):
        self.transaction = transaction
        self._savepoints = savepoints = []

        for datamanager in resources:
            try:
                savepoint = datamanager.savepoint
            except AttributeError:
                if not optimistic:
                    raise TypeError("Savepoints unsupported", datamanager)
                savepoint = NoRollbackSavepoint(datamanager)
            else:
                savepoint = savepoint()

            savepoints.append(savepoint)

    @property
    def valid(self):
        return self.transaction is not None

    def rollback(self):
        """See `~transaction.interfaces.ISavepoint`."""
        transaction = self.transaction
        if transaction is None:
            raise interfaces.InvalidSavepointRollbackError(
                'invalidated by a later savepoint')
        transaction._remove_and_invalidate_after(self)

        try:
            for savepoint in self._savepoints:
                savepoint.rollback()
        except:  # noqa: E722 do not use bare 'except'
            # Mark the transaction as failed.
            transaction._saveAndRaiseCommitishError()  # reraises!


class AbortSavepoint:

    def __init__(self, datamanager, transaction):
        self.datamanager = datamanager
        self.transaction = transaction

    def rollback(self):
        self.datamanager.abort(self.transaction)
        self.transaction._unjoin(self.datamanager)


class NoRollbackSavepoint:

    def __init__(self, datamanager):
        self.datamanager = datamanager

    def rollback(self):
        raise TypeError("Savepoints unsupported", self.datamanager)


def text_or_warn(s):
    if isinstance(s, str):
        return s

    warnings.warn("Expected text", DeprecationWarning, stacklevel=3)
    if isinstance(s, bytes):
        return s.decode('utf-8', 'replace')
    else:
        return str(s)
