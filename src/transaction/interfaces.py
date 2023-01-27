##############################################################################
#
# Copyright (c) 2001, 2002 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

from zope.interface import Attribute
from zope.interface import Interface


class ITransactionManager(Interface):
    """An object that manages a sequence of transactions.

    Applications use transaction managers to establish transaction boundaries.

    A transaction manager supports the "context manager" protocol:
    Its `__enter__` begins a new transaction; its `__exit__` commits
    the current transaction if no exception has occured; otherwise,
    it aborts it.
    """

    explicit = Attribute(
        """Explicit mode indicator.

        This is true if the transaction manager is in explicit mode.
        In explicit mode, transactions must be begun explicitly, by
        calling `begin` and ended explicitly by calling
        `commit` or `abort`.

        .. versionadded:: 2.1.0
        """)

    def begin():
        """Explicitly begin and return a new transaction.

        If an existing transaction is in progress and the transaction
        manager not in explicit mode, the previous transaction will be
        aborted.  If an existing transaction is in progress and the
        transaction manager is in explicit mode, an
        `AlreadyInTransaction` exception will be raised..

        The `~ISynchronizer.newTransaction` method of registered synchronizers
        is called, passing the new transaction object.

        Note that when not in explicit mode, transactions may be
        started implicitly without calling `begin`. In that case,
        ``newTransaction`` isn't called because the transaction
        manager doesn't know when to call it.  The transaction is
        likely to have begun long before the transaction manager is
        involved. (Conceivably the `commit` and `abort` methods
        could call `begin`, but they don't.)
        """

    def get():
        """Get the current transaction.

        In explicit mode, if a transaction hasn't begun, a
        `NoTransaction` exception will be raised.
        """

    def commit():
        """Commit the current transaction.

        In explicit mode, if a transaction hasn't begun, a
        `NoTransaction` exception will be raised.
        """

    def abort():
        """Abort the current transaction.

        In explicit mode, if a transaction hasn't begun, a
        `NoTransaction` exception will be raised.
        """

    def doom():
        """Doom the current transaction.

        In explicit mode, if a transaction hasn't begun, a
        `NoTransaction` exception will be raised.
        """

    def isDoomed():
        """Return True if the current transaction is doomed, otherwise False.

        In explicit mode, if a transaction hasn't begun, a
        `NoTransaction` exception will be raised.
        """

    def savepoint(optimistic=False):
        """Create a savepoint from the current transaction.

        If the optimistic argument is true, then data managers that
        don't support savepoints can be used, but an error will be
        raised if the savepoint is rolled back.

        An `ISavepoint` object is returned.

        In explicit mode, if a transaction hasn't begun, a
        `NoTransaction` exception will be raised.
        """

    def registerSynch(synch):
        """Register an `ISynchronizer`.

        Synchronizers are notified about some major events in a transaction's
        life.  See `ISynchronizer` for details.

        If a synchronizer registers while there is an active
        transaction, its ``newTransaction`` method will be called with the
        active transaction.
        """

    def unregisterSynch(synch):
        """Unregister an `ISynchronizer`.

        Synchronizers are notified about some major events in a transaction's
        life.  See `ISynchronizer` for details.
        """

    def clearSynchs():
        """Unregister all registered `ISynchronizer` objects.

        This exists to support test cleanup/initialization
        """

    def registeredSynchs():
        """Determine if any `ISynchronizers` are registered.

        Return true if any are registered, and return False otherwise.

        This exists to support test cleanup/initialization
        """

    def attempts(number=3):
        """Generate up to *number* (transactional) context managers.

        This method is typically used as follows::

            for attempt in transaction_manager.attempts():
                with attempt:
                    *with block*

        The ``with attempt:`` starts a new transaction for the
        execution of the *with block*. If the execution succeeds, the
        (then current) transaction is commited and the ``for`` loop
        terminates. If the execution raised an exception, then the
        transaction is aborted. If the exception was some kind of
        `retriable error <ITransaction.isRetryableError>` and the
        maximal number of attempts is not yet reached, then a next
        iteration of the ``for`` loop starts. In all other cases,
        the ``for`` loop terminates with the exception.
        """

    def run(func=None, tries=3):
        """Call *func()*  in its own transaction; retry
        in case of some kind of
        `retriable error <ITransaction.isRetryableError>`.

        The call is tried up to *tries* times.

        The call is performed in a new transaction. After the call,
        the (then current) transaction is committed (no exception) or
        aborted (exception).

        `run` supports the alternative signature ``run(tries=3)``. If
        *func* is not given or passed as `None`, then the call to
        `run` returns a function taking *func* as argument and then
        calling ``run(func, tries)``.
        """


class ITransaction(Interface):
    """Object representing a running transaction."""

    user = Attribute(
        """A user name associated with the transaction.

        The format of the user name is defined by the application.  The value
        is text (unicode). Storages record the user value, as meta-data,
        when a transaction commits.

        A storage may impose a limit on the size of the value; behavior is
        undefined if such a limit is exceeded (for example, a storage may
        raise an exception, or truncate the value).
        """)

    description = Attribute(
        """A textual description of the transaction.

        The value is text (unicode).  Method `note` is the intended
        way to set the value. Storages record the description, as meta-data,
        when a transaction commits.

        A storage may impose a limit on the size of the description; behavior
        is undefined if such a limit is exceeded (for example, a storage may
        raise an exception, or truncate the value).
        """)

    extension = Attribute(
        "A dictionary containing application-defined metadata.")

    def commit():
        """Finalize the transaction.

        This executes the two-phase commit algorithm for all
        `IDataManager` objects associated with the transaction.
        """

    def abort():
        """Abort the transaction.

        This is called from the application.  This can only be called
        before the two-phase commit protocol has been started.
        """

    def doom():
        """Doom the transaction.

        Dooms the current transaction. This will cause
        `DoomedTransaction` to be raised on any attempt to commit the
        transaction.

        Otherwise the transaction will behave as if it was active.
        """

    def savepoint(optimistic=False):
        """Create a savepoint.

        If the *optimistic* argument is true, then data managers that don't
        support savepoints can be used, but an error will be raised if the
        savepoint is rolled back.

        An `ISavepoint` object is returned.
        """

    def join(datamanager):
        """Add a data manager to the transaction.

        *datamanager* must provide the `IDataManager`
        interface.
        """

    def note(text):
        """Add text (unicode) to the transaction description.

        This modifies the `description` attribute; see its docs for more
        detail.  First surrounding whitespace is stripped from *text*.  If
        `description` is currently an empty string, then the stripped text
        becomes its value, else two newlines and the stripped text are
        appended to `description`.
        """

    def setExtendedInfo(name, value):
        """Add extension data to the transaction.

        :param text name:
          is the text (unicode) name of the extension property to set

        :param value:
          must be picklable and json serializable

        Multiple calls may be made to set multiple extension
        properties, provided the names are distinct.

        Storages record the extension data, as meta-data, when a transaction
        commits.

        A storage may impose a limit on the size of extension data; behavior
        is undefined if such a limit is exceeded (for example, a storage may
        raise an exception, or remove `<name, value>` pairs).
        """

    def addBeforeCommitHook(hook, args=(), kws=None):
        """Register a hook to call before the transaction is committed.

        The specified hook function will be called after the
        transaction's commit method has been called, but before the
        commit process has been started.

        :param sequence args:
            Additional positional arguments to be passed to the hook.
            The default is to pass no positional arguments.
        :param dict kws:
            Keyword arguments to pass to the hook. The default
            is to pass no keyword arguments.

        Multiple hooks can be registered and will be called in the
        order they were registered (first registered, first called).
        This method can also be called from a hook: an executing hook
        can register more hooks. Applications should take care to
        avoid creating infinite loops by recursively registering
        hooks.

        Hooks are called only for a top-level commit. A savepoint
        creation does not call any hooks. If the transaction is
        aborted, hooks are not called, and are discarded. Calling a
        hook "consumes" its registration too: hook registrations do
        not persist across transactions. If it's desired to call the
        same hook on every transaction commit, then
        `addBeforeCommitHook` must be called with that hook during
        every transaction; in such a case consider registering a
        synchronizer object via `ITransactionManager.registerSynch`
        instead.
        """

    def getBeforeCommitHooks():
        """Return iterable producing registered `addBeforeCommitHook` hooks.

        A triple ``(hook, args, kws)`` is produced for each registered hook.
        The hooks are produced in the order in which they would be invoked
        by a top-level transaction commit.
        """

    def addAfterCommitHook(hook, args=(), kws=None):
        """Register a hook to call after a transaction commit attempt.

        The specified hook function will be called after the
        transaction commit succeeds or aborts. The first argument
        passed to the hook is a Boolean value, `True` if the commit
        succeeded, or `False` if the commit aborted.
        *args* and *kws* are interpreted as for `addBeforeCommitHook`
        (with the exception that there is always one positional
        argument, the commit status).
        As with `addBeforeCommitHook`, multiple hooks can be
        registered, savepoint creation doesn't call any hooks, and
        calling a hook consumes its registration.
        """

    def getAfterCommitHooks():
        """Return iterable producing the registered `addAfterCommitHook` hooks.

        As with `getBeforeCommitHooks`, a triple ``(hook, args, kws)``
        is produced for each registered hook. The hooks are produced
        in the order in which they would be invoked by a top-level
        transaction commit.
        """

    def addBeforeAbortHook(hook, args=(), kws=None):
        """Register a hook to call before the transaction is aborted.

        The specified hook function will be called after the
        transaction's abort method has been called, but before the
        abort process has been started.

        *args* and *kws* are interpreted as for `addBeforeCommitHook`.
        As with `addBeforeCommitHook`, multiple hooks can be
        registered, savepoint creation doesn't call any hooks, and
        calling a hook consumes its registration.

        Abort hooks are called only for a top-level abort. If the
        transaction is committed, abort hooks are not called. This is
        true even if the commit fails. In this case, however, the
        transaction is in the ``COMMITFAILED`` state and is virtually
        unusable; therefore, a top-level abort will typically follow.
        """

    def getBeforeAbortHooks():
        """Return iterable producing the registered `addBeforeAbortHook` hooks.

        As with `getBeforeCommitHooks`, a triple ``(hook, args, kws)``
        is produced for each registered hook. The hooks are produced
        in the order in which they would be invoked by a top-level
        transaction abort.
        """

    def addAfterAbortHook(hook, args=(), kws=None):
        """Register a hook to call after a transaction abort.

        The specified hook function will be called after the
        transaction abort.

        *args* and *kws* are interpreted as for `addBeforeCommitHook`.
        As with `addBeforeCommitHook`, multiple hooks can be
        registered, savepoint creation doesn't call any hooks, and
        calling a hook consumes its registration.

        As with `addBeforeAbortHook`, these hooks are called only for
        a top-level abort. See that method for more.
        """

    def getAfterAbortHooks():
        """Return iterable producing the registered `addAfterAbortHook` hooks.

        As with `getBeforeCommitHooks`, a triple ``(hook, args, kws)``
        is produced for each registered hook. The hooks are produced
        in the order in which they would be invoked by a top-level
        transaction abort.
        """

    def set_data(ob, data):
        """Hold *data* on behalf of an object

        For objects such as data managers or their subobjects that
        work with multiple transactions, it's convenient to store
        transaction-specific data on the transaction itself.  The
        transaction knows nothing about the data, but simply holds it
        on behalf of the object.

        The object passed should be the object that needs the data, as
        opposed to a simple object like a string. (Internally, the id of
        the object is used as the key.)
        """

    def data(ob):
        """Retrieve data held on behalf of an object.

        See `set_data`.
        """

    def isRetryableError(error):
        """Determine if the error is retryable.

        Returns true if any joined `IRetryDataManager` considers the
        error transient *or* if the error is an instance of
        `TransientError`. Such errors may occur due to concurrency
        issues in the underlying storage engine.
        """


class IDataManager(Interface):
    """Objects that manage transactional storage.

    These objects may manage data for other objects, or they may manage
    non-object storages, such as relational databases.  For example,
    a `ZODB.Connection.Connection`.

    Note that when some data is modified, that data's data manager should
    join a transaction so that data can be committed when the user commits
    the transaction.

    These objects implement the two-phase commit protocol in order to allow
    multiple data managers to safely participate in a single transaction.
    The methods `tpc_begin`, `commit`, `tpc_vote`, and then either
    `tpc_finish` or `tpc_abort` are normally called in that order when
    committing a transaction.
    """

    transaction_manager = Attribute(
        """The transaction manager (TM) used by this data manager.

        This is a public attribute, intended for read-only use.  The value
        is an instance of `ITransactionManager`, typically set by the data
        manager's constructor.
        """)

    def abort(transaction):
        """Abort a transaction and forget all changes.

        Abort must be called outside of a two-phase commit.

        Abort is called by the transaction manager to abort
        transactions that are not yet in a two-phase commit.  It may
        also be called when rolling back a savepoint made before the
        data manager joined the transaction.

        In any case, after abort is called, the data manager is no
        longer participating in the transaction.  If there are new
        changes, the data manager must rejoin the transaction.
        """

    def tpc_begin(transaction):
        """Begin commit of a transaction, starting the two-phase commit.

        *transaction* is the `ITransaction` instance associated with the
        transaction being committed.
        """

    def commit(transaction):
        """Commit modifications to registered objects.

        Save changes to be made persistent if the transaction commits
        (if `tpc_finish` is called later). If `tpc_abort` is called
        later, changes must not persist.

        This includes conflict detection and handling. If no conflicts
        or errors occur, the data manager should be prepared to make
        the changes persist when `tpc_finish` is called.
        """

    def tpc_vote(transaction):
        """Verify that a data manager can commit the transaction.

        This is the last chance for a data manager to vote 'no'.  A
        data manager votes 'no' by raising an exception.

        *transaction* is the `ITransaction` instance associated with the
        transaction being committed.
        """

    def tpc_finish(transaction):
        """Indicate confirmation that the transaction is done.

        Make all changes to objects modified by this transaction persist.

        *transaction* is the `ITransaction` instance associated with the
        transaction being committed.

        This should never fail.  If this raises an exception, the
        database is not expected to maintain consistency; it's a
        serious error.
        """

    def tpc_abort(transaction):
        """Abort a transaction.

        This is called by a transaction manager to end a two-phase commit on
        the data manager.  Abandon all changes to objects modified by this
        transaction.

        *transaction* is the `ITransaction` instance associated with the
        transaction being committed.

        This should never fail.
        """

    def sortKey():
        """Return a key to use for ordering registered `IDataManagers`.

        In order to guarantee a total ordering, keys **must** be
        `strings <str>`.

        Transactions use a global sort order to prevent deadlock when
        committing transactions involving multiple data managers.
        The data managers **must** define a `sortKey` method that
        provides a global ordering across all registered data managers.
        """
        # Alternate version:
        # """Return a consistent sort key for this connection.
        #
        # This allows ordering multiple connections that use the same storage
        # in a consistent manner. This is unique for the lifetime of a
        # connection, which is good enough to avoid ZEO deadlocks.
        # """


class ISavepointDataManager(IDataManager):

    def savepoint():
        """Return a data-manager savepoint (`IDataManagerSavepoint`)."""


class IRetryDataManager(IDataManager):

    def should_retry(exception):
        """Return whether a given exception instance should be retried.

        A data manager can provide this method to indicate that a a
        transaction that raised the given error should be retried.
        This method may be called by an `ITransactionManager` when
        considering whether to retry a failed transaction.
        """


class IDataManagerSavepoint(Interface):
    """Savepoint for data-manager changes for use in transaction savepoints.

    Datamanager savepoints are used by, and only by, transaction
    savepoints.

    Note that data manager savepoints don't have any notion of, or
    responsibility for, validity. It isn't the responsibility of
    data-manager savepoints to prevent multiple rollbacks or rollbacks
    after transaction termination. Preventing invalid savepoint
    rollback is the responsibility of transaction rollbacks.
    Application code should never use data-manager savepoints.
    """

    def rollback():
        """Rollback any work done since the savepoint. """


class ISavepoint(Interface):
    """A transaction savepoint.
    """

    def rollback():
        """Rollback any work done since the savepoint.

        `InvalidSavepointRollbackError` is raised if the savepoint isn't valid.
        """

    valid = Attribute(
        "Boolean indicating whether the savepoint is valid")


class InvalidSavepointRollbackError(Exception):
    """Attempt to rollback an invalid savepoint.

    A savepoint may be invalid because:

    - The surrounding transaction has committed or aborted.

    - An earlier savepoint in the same transaction has been rolled back.
    """


class ISynchronizer(Interface):
    """Objects that participate in the transaction-boundary notification API.
    """

    def beforeCompletion(transaction):
        """Hook that is called by the transaction at the start of a commit."""

    def afterCompletion(transaction):
        """Hook that is called by the transaction after completing a commit."""

    def newTransaction(transaction):
        """Hook that is called at the start of a transaction.

        This hook is called when, and only when, a transaction manager's
        `~ITransactionManager.begin` method is called explicitly.
        """


class TransactionError(Exception):
    """An error occurred due to normal transaction processing."""


class TransactionFailedError(TransactionError):
    """Cannot perform an operation on a transaction that previously
    failed.

    An attempt was made to commit a transaction, or to join a
    transaction, but this transaction previously raised an exception
    during an attempt to commit it. The transaction must be explicitly
    aborted by invoking `ITransaction.abort`. (If the transaction manager
    is not operating in explicit mode, then `ITransactionManager.begin`
    can also be used to perform an implicit abort.)
    """


class DoomedTransaction(TransactionError):
    """A commit was attempted on a transaction that was doomed."""


class TransientError(TransactionError):
    """An error has occured when performing a transaction.

    It's possible that retrying the transaction will succeed.
    """


class NoTransaction(TransactionError):
    """No transaction has been defined

    An application called an operation on a transaction manager that
    affects an exciting transaction, but no transaction was begun.
    The transaction manager was in explicit mode, so a new transaction
    was not explicitly created.

    .. versionadded:: 2.1.0
    """


class AlreadyInTransaction(TransactionError):
    """Attempt to create a new transaction without ending a preceding one

    An application called `~ITransactionManager.begin` on a transaction manager
    in explicit mode, without committing or aborting the previous
    transaction.

    .. versionadded:: 2.1.0
    """
