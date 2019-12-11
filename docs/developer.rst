=================================
 ``transaction`` Developer Notes
=================================

.. currentmodule:: transaction.interfaces

Transaction objects manage resources for an individual activity. This
document contains some notes that will help in understanding how
transactions work, and how to use them to accomplish specific objectives.

Two-phase commit
================

A transaction commit involves an interaction between the transaction
object and one or more resource managers. The transaction manager
calls the following four methods on each resource manager; it calls
`IDataManager.tpc_begin` on each resource manager before calling
`IDataManager.commit` on any of them.

    1. tpc_begin(txn)
    2. commit(txn)
    3. tpc_vote(txn)
    4. tpc_finish(txn)

Before-commit hook
==================

Sometimes, applications want to execute some code when a transaction
is committed. For example, one might want to delay object indexing
until a transaction commits, rather than indexing every time an object
is changed. Or someone might want to check invariants only after a set
of operations. A pre-commit hook is available for such use cases: use
`ITransaction.addBeforeCommitHook`, passing it a callable and
arguments. The callable will be called with its arguments at the start
of the commit.

After-commit hook
=================

Sometimes, applications want to execute code after a transaction
commit attempt succeeds or aborts. For example, one might want to
launch non transactional code after a successful commit. Or still
someone might want to launch asynchronous code after. A post-commit
hook is available for such use cases: use
`ITransaction.addAfterCommitHook`, passing it a callable and
arguments. The callable will be called with a Boolean value
representing the status of the commit operation as first argument
(true if successfull or false iff aborted) preceding its arguments at
the start of the commit.

Abort hooks
===========

Commit hooks are not called for `ITransaction.abort`. For that, use
`ITransaction.addBeforeAbortHook` or `ITransaction.addAfterAbortHook`.

Error handling
==============

When errors occur during two-phase commit, the transaction manager
aborts all joined the data managers. The specific methods it calls depend
on whether the error occurs before or after any call to `IDataManager.tpc_vote`
joined to that transaction.

If a data manager has not voted, then the data manager will have one
or more uncommitted objects. There are two cases that lead to this
state; either the transaction manager has not called
`IDataManager.commit` for any joined data managers, or the call that
failed was a `IDataManager.commit` for one of the joined data
managers. For each uncommitted data manager, including the object that
failed in its ``commit()``, `IDataManager.abort` is called.

Once uncommitted objects are aborted, `IDataManager.tpc_abort` is
called on each data manager.

Transaction Manager Lifecycle Notifications (Synchronization)
=============================================================

You can register sychronization objects (`synchronizers
<ISynchronizer>`) with the tranasction manager. The synchronizer must
implement `ISynchronizer.beforeCompletion` and
`ISynchronizer.afterCompletion` methods. The transaction manager calls
``beforeCompletion`` when it starts a top-level two-phase commit. It
calls ``afterCompletion`` when a top-level transaction is committed or
aborted. The methods are passed the current `ITransaction` as their only
argument.

Explicit vs implicit transactions
=================================

By default, transactions are implicitly managed.  Calling ``begin()``
on a transaction manager implicitly aborts the previous transaction
and calling ``commit()`` or ``abort()`` implicitly begins a new
one. This behavior can be convenient for interactive use, but invites
subtle bugs:

- Calling begin() without realizing that there are outstanding changes
  that will be aborted.

- Interacting with a database without controlling transactions, in
  which case changes may be unexpectedly discarded.

For applications, including frameworks that control transactions,
transaction managers provide an optional explicit mode.  Transaction
managers have an ``explicit`` constructor keyword argument that, if
True puts the transaction manager in explicit mode.  In explicit mode:

- It is an error to call ``get()``, ``commit()``, ``abort()``,
  ``doom()``, ``isDoomed``, or ``savepoint()`` without a preceding
  ``begin()`` call.  Doing so will raise a ``NoTransaction``
  exception.

- It is an error to call ``begin()`` after a previous ``begin()``
  without an intervening ``commit()`` or ``abort()`` call.  Doing so
  will raise an ``AlreadyInTransaction`` exception.

In explicit mode, bugs like those mentioned above are much easier to
avoid because they cause explicit exceptions that can typically be
caught in development.

An additional benefit of explicit mode is that it can allow data
managers to manage resources more efficiently.

Transaction managers have an explicit attribute that can be queried to
determine if explicit mode is enabled.
