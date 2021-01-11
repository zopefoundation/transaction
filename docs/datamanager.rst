========================
 Writing a Data Manager
========================

.. currentmodule:: transaction.interfaces

Simple Data Manager
===================

.. doctest::

   >>> from transaction.tests.examples import DataManager

This class provides a trivial `IDataManager` implementation and doc
strings to illustrate the protocol and to provide a tool for writing
tests.

Our sample data manager has state that is updated through an inc
method and through transaction operations.

When we create a sample data manager:

.. doctest::

   >>> rm = DataManager()

It has two pieces, state and delta, both initialized to 0:

.. doctest::

   >>> rm.state
   0
   >>> rm.delta
   0

state is meant to model committed state, while delta represents
tentative changes within a transaction.  We change the state by
calling inc:

.. doctest::

   >>> rm.inc()

which updates delta:

.. doctest::

   >>> rm.delta
   1

but state isn't changed until we commit the transaction:

.. doctest::

   >>> rm.state
   0

To commit the changes, we use 2-phase commit.  We execute the first
stage by calling ``tpc_begin``.  We need to pass a transation. Our
sample data managers don't really use the transactions for much,
so we'll be lazy and use strings for transactions.  The sample
data manager updates the state when we call ``tpc_vote``, after
calling ``commit``:


.. doctest::

   >>> t1 = '1'
   >>> rm.tpc_begin(t1)
   >>> rm.state, rm.delta
   (0, 1)
   >>> rm.commit(t1)
   >>> rm.tpc_vote(t1)
   >>> rm.state, rm.delta
   (1, 1)


Now if we call tpc_finish:

.. doctest::

   >>> rm.tpc_finish(t1)

Our changes are "permanent".  The state reflects the changes and the
delta has been reset to 0.

.. doctest::

   >>> rm.state, rm.delta
   (1, 0)


The ``tpc_begin`` Method
========================

Called by the transaction manager to ask the data manager to prepare to commit data.

.. doctest::

   >>> rm = DataManager()
   >>> rm.inc()
   >>> t1 = '1'
   >>> rm.tpc_begin(t1)
   >>> rm.tpc_vote(t1)
   >>> rm.tpc_finish(t1)
   >>> rm.state
   1
   >>> rm.inc()
   >>> t2 = '2'
   >>> rm.tpc_begin(t2)
   >>> rm.tpc_vote(t2)
   >>> rm.tpc_abort(t2)
   >>> rm.state
   1

It is an error to call tpc_begin more than once without completing
two-phase commit:

.. doctest::

   >>> rm.tpc_begin(t1)

   >>> rm.tpc_begin(t1)
   Traceback (most recent call last):
   ...
   ValueError: txn in state 'tpc_begin' but expected one of (None,)
   >>> rm.tpc_abort(t1)

If there was a preceeding savepoint, the transaction must match:

.. doctest::

   >>> rollback = rm.savepoint(t1)
   >>> rm.tpc_begin(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> rm.tpc_begin(t1)


The ``tpc_vote`` Method
=======================

Verify that a data manager can commit the transaction.

This is the last chance for a data manager to vote 'no'.  A
data manager votes 'no' by raising an exception.

Passed *transaction*, which is the `ITransaction` instance associated
with the transaction being committed.


The ``tpc_finish`` Method
=========================

Complete two-phase commit

.. doctest::

   >>> rm = DataManager()
   >>> rm.state
   0
   >>> rm.inc()

   We start two-phase commit by calling ``tpc_begin``, ``commit``, and ``tpc_vote``:

   >>> t1 = '1'
   >>> rm.tpc_begin(t1)
   >>> rm.commit(t1)
   >>> rm.tpc_vote(t1)

   We complete it by calling tpc_finish:

   >>> rm.tpc_finish(t1)
   >>> rm.state
   1

It is an error ro call tpc_finish without calling tpc_vote:

.. doctest::

   >>> rm.inc()
   >>> t2 = '2'
   >>> rm.tpc_begin(t2)
   >>> rm.tpc_finish(t2)
   Traceback (most recent call last):
   ...
   ValueError: txn in state 'tpc_begin' but expected one of ('tpc_vote',)

   >>> rm.tpc_abort(t2)  # clean slate

   >>> rm.tpc_begin(t2)
   >>> rm.tpc_vote(t2)
   >>> rm.tpc_finish(t2)

Of course, the transactions given to tpc_begin and tpc_finish must
be the same:

.. doctest::

   >>> rm.inc()
   >>> t3 = '3'
   >>> rm.tpc_begin(t3)
   >>> rm.tpc_vote(t3)
   >>> rm.tpc_finish(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '3')


The ``tpc_abort`` Method
========================

Abort a transaction during two-phase commit *after* ``tpc_vote`` has
been called.

Here, we will ignore the fact that this is only called after
``tpc_vote`` and simulate that using ``inc``.

.. doctest::

   >>> rm = DataManager()
   >>> rm.inc()
   >>> rm.state, rm.delta
   (0, 1)
   >>> t1 = '1'
   >>> rm.tpc_abort(t1)
   >>> rm.state, rm.delta
   (0, 0)

The abort method also throws away work done in savepoints:

.. doctest::

   >>> rm.inc()
   >>> r = rm.savepoint(t1)
   >>> rm.inc()
   >>> r = rm.savepoint(t1)
   >>> rm.state, rm.delta
   (0, 2)
   >>> rm.tpc_abort(t1)
   >>> rm.state, rm.delta
   (0, 0)

If savepoints are used, abort must be passed the same
transaction:

.. doctest::

   >>> rm.inc()
   >>> r = rm.savepoint(t1)
   >>> t2 = '2'
   >>> rm.tpc_abort(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> rm.tpc_abort(t1)

The abort method is also used to abort a two-phase commit:

.. doctest::

   >>> rm.inc()
   >>> rm.state, rm.delta
   (0, 1)
   >>> rm.tpc_begin(t1)
   >>> rm.state, rm.delta
   (0, 1)
   >>> rm.tpc_vote(t1)
   >>> rm.state, rm.delta
   (1, 1)
   >>> rm.tpc_abort(t1)
   >>> rm.state, rm.delta
   (0, 0)

Of course, the transactions passed to prepare and abort must
match:

.. doctest::

   >>> rm.tpc_begin(t1)
   >>> rm.tpc_abort(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> rm.tpc_abort(t1)

This should never fail.

The ``abort`` method
====================

The abort method can be called before two-phase commit to
throw away work done in the transaction:

.. doctest::

   >>> dm = DataManager()
   >>> dm.inc()
   >>> dm.state, dm.delta
   (0, 1)
   >>> t1 = '1'
   >>> dm.abort(t1)
   >>> dm.state, dm.delta
   (0, 0)

The abort method also throws away work done in savepoints:

.. doctest::

   >>> dm.inc()
   >>> r = dm.savepoint(t1)
   >>> dm.inc()
   >>> r = dm.savepoint(t1)
   >>> dm.state, dm.delta
   (0, 2)
   >>> dm.abort(t1)
   >>> dm.state, dm.delta
   (0, 0)

If savepoints are used, abort must be passed the same
transaction:

.. doctest::

   >>> dm.inc()
   >>> r = dm.savepoint(t1)
   >>> t2 = '2'
   >>> dm.abort(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> dm.abort(t1)

Of course, the transactions passed to abort must
match. (Since it's called before ``tpc_vote`` is called,
there might be no current transaction.)

.. doctest::

   >>> dm.tpc_begin(t1)
   >>> dm.abort(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> dm.abort(t1)


The ``commit`` method
=====================

Called after ``tpc_begin`` to make changes persistent and prepare for
voting.

.. doctest::

   >>> dm = DataManager()
   >>> dm.state
   0
   >>> dm.inc()

We start two-phase commit by calling ``tpc_begin``

.. doctest::

   >>> t1 = '1'
   >>> dm.tpc_begin(t1)

   We complete it by calling ``commit``, ``tpc_vote``, and ``tpc_finish``:

.. doctest::

   >>> dm.commit(t1)
   >>> dm.tpc_vote(t1)
   >>> dm.tpc_finish(t1)
   >>> dm.state
   1

It is an error to call commit without calling ``tpc_begin`` first:

.. doctest::

   >>> dm = DataManager()
   >>> t2 = '2'
   >>> dm.commit(t2)
   Traceback (most recent call last):
   ...
   TypeError: Not prepared to commit

If course, the transactions given to ``tpc_begin`` and commit must
be the same:

.. doctest::

   >>> dm = DataManager()
   >>> t3 = '3'
   >>> dm.tpc_begin(t3)
   >>> dm.commit(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '3')


The ``savepoint`` Method
========================

Provide the ability to rollback transaction state

Savepoints provide a way to:

 - Save partial transaction work. For some data managers, this
   could allow resources to be used more efficiently.

 - Provide the ability to revert state to a point in a
   transaction without aborting the entire transaction.  In
   other words, savepoints support partial aborts.

Savepoints don't use two-phase commit. If there are errors in
setting or rolling back to savepoints, the application should
abort the containing transaction.  This is *not* the
responsibility of the data manager.

Savepoints are always associated with a transaction. Any work
done in a savepoint's transaction is tentative until the
transaction is committed using two-phase commit.

.. doctest::

   >>> rm = DataManager()
   >>> rm.inc()
   >>> t1 = '1'
   >>> r = rm.savepoint(t1)
   >>> rm.state, rm.delta
   (0, 1)
   >>> rm.inc()
   >>> rm.state, rm.delta
   (0, 2)
   >>> r.rollback()
   >>> rm.state, rm.delta
   (0, 1)
   >>> rm.tpc_begin(t1)
   >>> rm.tpc_vote(t1)
   >>> rm.tpc_finish(t1)
   >>> rm.state, rm.delta
   (1, 0)

Savepoints must have the same transaction:

.. doctest::

   >>> r1 = rm.savepoint(t1)
   >>> rm.state, rm.delta
   (1, 0)
   >>> rm.inc()
   >>> rm.state, rm.delta
   (1, 1)
   >>> t2 = '2'
   >>> r2 = rm.savepoint(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> r2 = rm.savepoint(t1)
   >>> rm.inc()
   >>> rm.state, rm.delta
   (1, 2)

If we rollback to an earlier savepoint, we discard all work
done later:

.. doctest::

   >>> r1.rollback()
   >>> rm.state, rm.delta
   (1, 0)

and we can no longer rollback to the later savepoint:

.. doctest::

   >>> r2.rollback()
   Traceback (most recent call last):
   ...
   TypeError: ('Attempt to roll back to invalid save point', 3, 2)

We can roll back to a savepoint as often as we like:

.. doctest::

   >>> r1.rollback()
   >>> r1.rollback()
   >>> r1.rollback()
   >>> rm.state, rm.delta
   (1, 0)

   >>> rm.inc()
   >>> rm.inc()
   >>> rm.inc()
   >>> rm.state, rm.delta
   (1, 3)
   >>> r1.rollback()
   >>> rm.state, rm.delta
   (1, 0)

But we can't rollback to a savepoint after it has been
committed:

.. doctest::

   >>> rm.tpc_begin(t1)
   >>> rm.tpc_vote(t1)
   >>> rm.tpc_finish(t1)

   >>> r1.rollback()
   Traceback (most recent call last):
   ...
   TypeError: Attempt to rollback stale rollback
