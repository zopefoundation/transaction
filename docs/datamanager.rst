Writing a Data Manager
======================

Simple Data Manager
------------------

.. doctest::

   >>> from transaction.tests.examples import DataManager

This :class:`transaction.tests.examples.DataManager` class
provides a trivial data-manager implementation and docstrings to illustrate
the the protocol and to provide a tool for writing tests.

Our sample data manager has state that is updated through an inc
method and through transaction operations.


When we create a sample data manager:

.. doctest::

   >>> dm = DataManager()

It has two bits of state, state:

.. doctest::

   >>> dm.state
   0

and delta:

.. doctest::

   >>> dm.delta
   0

Both of which are initialized to 0.  state is meant to model
committed state, while delta represents tentative changes within a
transaction.  We change the state by calling inc:

.. doctest::

   >>> dm.inc()

which updates delta:

.. doctest::

   >>> dm.delta
   1

but state isn't changed until we commit the transaction:

.. doctest::

   >>> dm.state
   0

To commit the changes, we use 2-phase commit. We execute the first
stage by calling prepare.  We need to pass a transation. Our
sample data managers don't really use the transactions for much,
so we'll be lazy and use strings for transactions:

.. doctest::

   >>> t1 = '1'
   >>> dm.prepare(t1)

The sample data manager updates the state when we call prepare:

.. doctest::

   >>> dm.state
   1
   >>> dm.delta
   1

This is mainly so we can detect some affect of calling the methods.

Now if we call commit:

.. doctest::

   >>> dm.commit(t1)

Our changes are"permanent".  The state reflects the changes and the
delta has been reset to 0.

.. doctest::

   >>> dm.state
   1
   >>> dm.delta
   0

The :meth:`prepare` Method
----------------------------

Prepare to commit data

.. doctest::

   >>> dm = DataManager()
   >>> dm.inc()
   >>> t1 = '1'
   >>> dm.prepare(t1)
   >>> dm.commit(t1)
   >>> dm.state
   1
   >>> dm.inc()
   >>> t2 = '2'
   >>> dm.prepare(t2)
   >>> dm.abort(t2)
   >>> dm.state
   1

It is en error to call prepare more than once without an intervening
commit or abort:

.. doctest::

   >>> dm.prepare(t1)

   >>> dm.prepare(t1)
   Traceback (most recent call last):
   ...
   TypeError: Already prepared

   >>> dm.prepare(t2)
   Traceback (most recent call last):
   ...
   TypeError: Already prepared

   >>> dm.abort(t1)

If there was a preceeding savepoint, the transaction must match:

.. doctest::

   >>> rollback = dm.savepoint(t1)
   >>> dm.prepare(t2)
   Traceback (most recent call last):
   ,,,
   TypeError: ('Transaction missmatch', '2', '1')

   >>> dm.prepare(t1)

The :meth:`abort` method
--------------------------

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

The abort method is also used to abort a two-phase commit:

.. doctest::

   >>> dm.inc()
   >>> dm.state, dm.delta
   (0, 1)
   >>> dm.prepare(t1)
   >>> dm.state, dm.delta
   (1, 1)
   >>> dm.abort(t1)
   >>> dm.state, dm.delta
   (0, 0)

Of course, the transactions passed to prepare and abort must
match:

.. doctest::

   >>> dm.prepare(t1)
   >>> dm.abort(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> dm.abort(t1)



The :meth:`commit` method
---------------------------

Called to omplete two-phase commit

.. doctest::

   >>> dm = DataManager()
   >>> dm.state
   0
   >>> dm.inc()

We start two-phase commit by calling prepare:

.. doctest::

   >>> t1 = '1'
   >>> dm.prepare(t1)

   We complete it by calling commit:

.. doctest::

   >>> dm.commit(t1)
   >>> dm.state
   1

It is an error ro call commit without calling prepare first:

.. doctest::

   >>> dm.inc()
   >>> t2 = '2'
   >>> dm.commit(t2)
   Traceback (most recent call last):
   ...
   TypeError: Not prepared to commit

   >>> dm.prepare(t2)
   >>> dm.commit(t2)

If course, the transactions given to prepare and commit must
be the same:

.. doctest::

   >>> dm.inc()
   >>> t3 = '3'
   >>> dm.prepare(t3)
   >>> dm.commit(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '3')


The :meth:`savepoint` method
------------------------------

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

   >>> dm = DataManager()
   >>> dm.inc()
   >>> t1 = '1'
   >>> r = dm.savepoint(t1)
   >>> dm.state, dm.delta
   (0, 1)
   >>> dm.inc()
   >>> dm.state, dm.delta
   (0, 2)
   >>> r.rollback()
   >>> dm.state, dm.delta
   (0, 1)
   >>> dm.prepare(t1)
   >>> dm.commit(t1)
   >>> dm.state, dm.delta
   (1, 0)

Savepoints must have the same transaction:

.. doctest::

   >>> r1 = dm.savepoint(t1)
   >>> dm.state, dm.delta
   (1, 0)
   >>> dm.inc()
   >>> dm.state, dm.delta
   (1, 1)
   >>> t2 = '2'
   >>> r2 = dm.savepoint(t2)
   Traceback (most recent call last):
   ...
   TypeError: ('Transaction missmatch', '2', '1')

   >>> r2 = dm.savepoint(t1)
   >>> dm.inc()
   >>> dm.state, dm.delta
   (1, 2)

If we rollback to an earlier savepoint, we discard all work
done later:

.. doctest::

   >>> r1.rollback()
   >>> dm.state, dm.delta
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
   >>> dm.state, dm.delta
   (1, 0)

   >>> dm.inc()
   >>> dm.inc()
   >>> dm.inc()
   >>> dm.state, dm.delta
   (1, 3)
   >>> r1.rollback()
   >>> dm.state, dm.delta
   (1, 0)

But we can't rollback to a savepoint after it has been
committed:

.. doctest::

   >>> dm.prepare(t1)
   >>> dm.commit(t1)

   >>> r1.rollback()
   Traceback (most recent call last):
   ...
   TypeError: Attempt to rollback stale rollback
