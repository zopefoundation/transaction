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
"""A TransactionManager controls transaction boundaries.

It coordinates application code and resource managers, so that they
are associated with the right transaction.
"""
import itertools
import sys
import threading

from zope.interface import implementer

from transaction._compat import reraise
from transaction._compat import text_
from transaction._transaction import Transaction
from transaction.interfaces import AlreadyInTransaction
from transaction.interfaces import ITransactionManager
from transaction.interfaces import NoTransaction
from transaction.interfaces import TransientError
from transaction.weakset import WeakSet


# We have to remember sets of synch objects, especially Connections.
# But we don't want mere registration with a transaction manager to
# keep a synch object alive forever; in particular, it's common
# practice not to explicitly close Connection objects, and keeping
# a Connection alive keeps a potentially huge number of other objects
# alive (e.g., the cache, and everything reachable from it too).
# Therefore we use "weak sets" internally.

# Call the ISynchronizer newTransaction() method on every element of
# WeakSet synchs.
# A transaction manager needs to do this whenever begin() is called.
# Since it would be good if tm.get() returned the new transaction while
# newTransaction() is running, calling this has to be delayed until after
# the transaction manager has done whatever it needs to do to make its
# get() return the new txn.
def _new_transaction(txn, synchs):
    if synchs:
        synchs.map(lambda s: s.newTransaction(txn))

# Important:  we must always pass a WeakSet (even if empty) to the Transaction
# constructor:  synchronizers are registered with the TM, but the
# ISynchronizer xyzCompletion() methods are called by Transactions without
# consulting the TM, so we need to pass a mutable collection of synchronizers
# so that Transactions "see" synchronizers that get registered after the
# Transaction object is constructed.


@implementer(ITransactionManager)
class TransactionManager(object):
    """Single-thread implementation of
    `~transaction.interfaces.ITransactionManager`.
    """

    def __init__(self, explicit=False):
        self.explicit = explicit
        self._txn = None
        self._synchs = WeakSet()

    def begin(self):
        """See `~transaction.interfaces.ITransactionManager`."""
        if self._txn is not None:
            if self.explicit:
                raise AlreadyInTransaction()
            self._txn.abort()
        txn = self._txn = Transaction(self._synchs, self)
        _new_transaction(txn, self._synchs)
        return txn

    def __enter__(self):
        return self.begin()

    def get(self):
        """See `~transaction.interfaces.ITransactionManager`."""
        if self._txn is None:
            if self.explicit:
                raise NoTransaction()
            self._txn = Transaction(self._synchs, self)
        return self._txn

    def free(self, txn):
        if txn is not self._txn:
            raise ValueError("Foreign transaction")
        self._txn = None

    def registerSynch(self, synch):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        self._synchs.add(synch)
        if self._txn is not None:
            synch.newTransaction(self._txn)

    def unregisterSynch(self, synch):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        self._synchs.remove(synch)

    def clearSynchs(self):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        self._synchs.clear()

    def registeredSynchs(self):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        return bool(self._synchs)

    def isDoomed(self):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        return self.get().isDoomed()

    def doom(self):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        return self.get().doom()

    def commit(self):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        return self.get().commit()

    def abort(self):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        return self.get().abort()

    def __exit__(self, t, v, tb):
        if v is None:
            self.commit()
        else:
            self.abort()

    def savepoint(self, optimistic=False):
        """ See `~transaction.interfaces.ITransactionManager`.
        """
        return self.get().savepoint(optimistic)

    def attempts(self, number=3):
        if number <= 0:
            raise ValueError("number must be positive")
        while number:
            number -= 1
            if number:
                attempt = Attempt(self)
                yield attempt
                if attempt.success:
                    break
            else:
                yield self

    def _retryable(self, error_type, error):
        if issubclass(error_type, TransientError):
            return True

        for dm in self.get()._resources:
            should_retry = getattr(dm, 'should_retry', None)
            if (should_retry is not None) and should_retry(error):
                return True
        return False

    run_no_func_types = int, type(None)

    def run(self, func=None, tries=3):
        if isinstance(func, self.run_no_func_types):
            if func is not None:
                tries = func
            return lambda func: self.run(func, tries)

        if tries <= 0:
            raise ValueError("tries must be > 0")

        # These are ordinarily native strings, but that's
        # not required. A callable class could override them
        # to anything, and a Python 2.7 file could have
        # imported `from __future__ import unicode_literals`
        # which gets unicode docstrings.
        name = func.__name__
        doc = func.__doc__

        name = text_(name) if name else u''
        doc = text_(doc) if doc else u''

        if name and name != u'_':
            if doc:
                doc = name + u'\n\n' + doc
            else:
                doc = name

        for try_no in itertools.count(1):
            txn = self.begin()
            if doc:
                txn.note(doc)
            try:
                result = func()
                self.commit()
                return result
            except BaseException as exc:
                # Note: `abort` must not be called before `_retryable`
                retry = (isinstance(exc, Exception)
                         and try_no < tries
                         and self._retryable(exc.__class__, exc))
                self.abort()
                if retry:
                    continue
                else:
                    raise


@implementer(ITransactionManager)
class ThreadTransactionManager(threading.local):
    """Thread-local
    `transaction manager <transaction.interfaces.ITransactionManager>`.

    A thread-local transaction manager can be used as a global
    variable, but has a separate copy for each thread.

    Advanced applications can use the `manager` attribute to get a
    wrapped `TransactionManager` to allow cross-thread calls for
    graceful shutdown of data managers.
    """

    def __init__(self):
        self.manager = TransactionManager()

    @property
    def explicit(self):
        return self.manager.explicit

    @explicit.setter
    def explicit(self, v):
        self.manager.explicit = v

    def begin(self):
        return self.manager.begin()

    def get(self):
        return self.manager.get()

    def __enter__(self):
        return self.manager.__enter__()

    def commit(self):
        return self.manager.commit()

    def abort(self):
        return self.manager.abort()

    def __exit__(self, t, v, tb):
        return self.manager.__exit__(t, v, tb)

    def doom(self):
        return self.manager.doom()

    def isDoomed(self):
        return self.manager.isDoomed()

    def savepoint(self, optimistic=False):
        return self.manager.savepoint(optimistic)

    def registerSynch(self, synch):
        return self.manager.registerSynch(synch)

    def unregisterSynch(self, synch):
        return self.manager.unregisterSynch(synch)

    def clearSynchs(self):
        return self.manager.clearSynchs()

    def registeredSynchs(self):
        return self.manager.registeredSynchs()

    def attempts(self, number=3):
        return self.manager.attempts(number)

    def run(self, func=None, tries=3):
        return self.manager.run(func, tries)


class Attempt(object):

    success = False

    def __init__(self, manager):
        self.manager = manager

    def _retry_or_raise(self, t, v, tb):
        retry = self.manager._retryable(t, v)
        self.manager.abort()
        if retry:
            return retry  # suppress the exception if necessary
        reraise(t, v, tb)  # otherwise reraise the exception

    def __enter__(self):
        return self.manager.__enter__()

    def __exit__(self, t, v, tb):
        if v is None:
            try:
                self.manager.commit()
            except:  # noqa: E722 do not use bare 'except'
                return self._retry_or_raise(*sys.exc_info())
            else:
                self.success = True
        else:
            return self._retry_or_raise(t, v, tb)
