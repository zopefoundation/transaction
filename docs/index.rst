:mod:`transaction` Documentation
================================

Transaction objects manage resources for an individual activity.

Compatibility issues
--------------------

The implementation of Transaction objects involves two layers of
backwards compatibility, because this version of transaction supports
both ZODB 3 and ZODB 4.  Zope is evolving towards the ZODB4
interfaces.

Transaction has two methods for a resource manager to call to
participate in a transaction -- register() and join().  join() takes a
resource manager and adds it to the list of resources.  register() is
for backwards compatibility.  It takes a persistent object and
registers its _p_jar attribute.  TODO: explain adapter

Two-phase commit
----------------

A transaction commit involves an interaction between the transaction
object and one or more resource managers.  The transaction manager
calls the following four methods on each resource manager; it calls
tpc_begin() on each resource manager before calling commit() on any of
them.

    1. tpc_begin(txn)
    2. commit(txn)
    3. tpc_vote(txn)
    4. tpc_finish(txn)

Before-commit hook
------------------

Sometimes, applications want to execute some code when a transaction is
committed.  For example, one might want to delay object indexing until a
transaction commits, rather than indexing every time an object is changed.
Or someone might want to check invariants only after a set of operations.  A
pre-commit hook is available for such use cases:  use addBeforeCommitHook(),
passing it a callable and arguments.  The callable will be called with its
arguments at the start of the commit (but not for substransaction commits).

After-commit hook
------------------

Sometimes, applications want to execute code after a transaction commit
attempt succeeds or aborts. For example, one might want to launch non
transactional code after a successful commit. Or still someone might
want to launch asynchronous code after.  A post-commit hook is
available for such use cases: use addAfterCommitHook(), passing it a
callable and arguments.  The callable will be called with a Boolean
value representing the status of the commit operation as first
argument (true if successfull or false iff aborted) preceding its
arguments at the start of the commit (but not for substransaction
commits). Commit hooks are not called for transaction.abort().

Error handling
--------------

When errors occur during two-phase commit, the transaction manager
aborts all the resource managers.  The specific methods it calls
depend on whether the error occurs before or after the call to
tpc_vote() on that transaction manager.

If the resource manager has not voted, then the resource manager will
have one or more uncommitted objects.  There are two cases that lead
to this state; either the transaction manager has not called commit()
for any objects on this resource manager or the call that failed was a
commit() for one of the objects of this resource manager.  For each
uncommitted object, including the object that failed in its commit(),
call abort().

Once uncommitted objects are aborted, tpc_abort() or abort_sub() is
called on each resource manager.

Synchronization
---------------

You can register sychronization objects (synchronizers) with the
tranasction manager.  The synchronizer must implement
beforeCompletion() and afterCompletion() methods.  The transaction
manager calls beforeCompletion() when it starts a top-level two-phase
commit.  It calls afterCompletion() when a top-level transaction is
committed or aborted.  The methods are passed the current Transaction
as their only argument.

Contents:

.. toctree::
   :maxdepth: 2

   convenience
   doom
   savepoint
   hooks
   datamanager
   resourcemanager
   api


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

