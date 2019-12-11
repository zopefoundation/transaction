==================================
 ``transaction`` Documentation
==================================

A general transaction support library for Python.

The transaction package offers a two-phase commit protocol which allows
multiple backends of any kind to participate in a transaction and
commit their changes only if all of them can successfully do so. It also
offers support for savepoints, so that part of a transaction can be rolled
back without having to abort it completely.

There are already transaction backends for SQLAlchemy, ZODB, email, filesystem,
and others. in addition, there are packages like pyramid_tm, which allows all
the code in a web request to run inside of a transaction, and aborts the
transaction automatically if an error occurs. It's also not difficult to create your own backends if necessary.

.. rubric:: Additional Documentation

.. toctree::
   :maxdepth: 1

   changes
   convenience
   doom
   savepoint
   hooks
   datamanager
   integrations
   sqlalchemy
   api
   developer


Getting the transaction package
===============================

To install the transaction package you can use pip::

    $ pip install transaction

After this, the package can be imported in your Python code, but there are a
few things that we need to explain before doing that.


Using transactions
==================

At its simplest, the developer will use an existing transaction backend, and
will at most require to commit  or abort a transaction now and then. For
example:

.. code-block:: python
    :linenos:

    import transaction

    try:
        # some code that uses one or more backends
        .
        .
        .
        transaction.commit()
    except SomeError:
        transaction.abort()



Things you need to know about the transaction machinery
=======================================================

.. rubric:: Transactions


A consists of one or more operations that we want to perform as a
single action. It's an all or nothing proposition: either all the operations
that are part of the transaction are completed successfully or none of them
have any effect.

In the transaction package, a `transaction object <transaction.interfaces.ITransaction>`
represents a running transaction that can be committed or aborted in
the end.

.. rubric:: Transaction managers

Applications interact with a transaction using a `transaction manager
<transaction.interfaces.ITransactionManager>`, which is responsible for establishing the
transaction boundaries. Basically this means that it creates the
transactions and keeps track of the current one. Whenever an
application wants to use the transaction machinery, it gets the
current transaction from the transaction manager before starting any
operations

The default transaction manager, `transaction.manager`, is thread
local.  You use it as a global variable, but every thread has it's own
copy. [#wrapped]_

Application developers will most likely never need to create their own
transaction managers.

.. rubric:: Data Managers

A `data manager <transaction.interfaces.IDataManager>` handles the
interaction between the transaction manager and the data storage
mechanism used by the application, which can be an object storage like
the ZODB, a relational database, a file or any other storage mechanism
that the application needs to control.

The data manager provides a common interface for the transaction
manager to use while a transaction is running. To be part of a
specific transaction, a data manager has to `join
<transaction.interfaces.ITransaction.join>` it. Any number of data
managers can join a transaction, which means that you could for
example perform writing operations on a ZODB storage and a relational
database as part of the same transaction. The transaction manager will
make sure that both data managers can commit the transaction or none
of them does.

An application developer will need to write a data manager for each different
type of storage that the application uses. There are also third party data
managers that can be used instead.

.. rubric:: The two phase commit protocol

The transaction machinery uses a two phase commit protocol for coordinating all
participating data managers in a transaction. The two phases work like follows:

 1. The commit process is started.
 2. Each associated data manager prepares the changes to be persistent.
 3. Each data manager verifies that no errors or other exceptional conditions
    occurred during the attempt to persist the changes. If that happens, an
    exception should be raised. This is called 'voting'. A data manager votes
    'no' by raising an exception if something goes wrong; otherwise, its vote
    is counted as a 'yes'.
 4. If any of the associated data managers votes 'no', the transaction is
    aborted; otherwise, the changes are made permanent.

The two phase commit sequence requires that all the storages being used are
capable of rolling back or aborting changes.

.. rubric:: Savepoints

A savepoint allows `supported data managers
<transaction.interfaces.ISavepointDataManager>` to save work to their
storage without committing the full transaction. In other words, the
transaction will go on, but if a rollback is needed we can get back to
this point instead of starting all over.

Savepoints are also useful to free memory that would otherwise be used to keep
the whole state of the transaction. This can be very important when a
transaction attempts a large number of changes.


.. [#wrapped] The thread-local transaction manager,
   `transaction.manager` wraps a regular transaction manager. You can
   get the wrapped transaction manager using the ``manager``
   attribute. Implementers of data managers can use this **advanced**
   feature to allow graceful shutdown from a central/main thread, by
   having their ``close`` methods call
   `~.ITransactionManager.unregisterSynch` on the wrapped transaction
   manager they obtained when created or opened.
