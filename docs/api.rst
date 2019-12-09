==================================
 :mod:`transaction` API Reference
==================================

Interfaces
==========

.. module::  transaction.interfaces

.. autointerface:: ITransactionManager

.. autointerface:: ITransaction

.. autointerface:: IDataManager

.. autointerface:: ISavepointDataManager

.. autointerface:: IRetryDataManager

.. autointerface:: IDataManagerSavepoint

.. autointerface:: ISavepoint

.. autointerface:: ISynchronizer

Exceptions
----------

.. autoclass:: TransactionError

.. autoclass:: TransactionFailedError

.. autoclass:: DoomedTransaction

.. autoclass:: TransientError

.. autoclass:: InvalidSavepointRollbackError

.. autoclass:: NoTransaction

.. autoclass:: AlreadyInTransaction

API Objects
===========

.. module:: transaction._transaction

.. autoclass:: Transaction

.. autoclass:: Savepoint

.. module:: transaction._manager

.. autoclass:: TransactionManager

   .. automethod:: __enter__

      Alias for :meth:`get`

   .. automethod:: __exit__

      On error, aborts the current transaction.  Otherwise, commits.

.. autoclass:: ThreadTransactionManager
