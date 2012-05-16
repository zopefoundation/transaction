:mod:`transaction` API Reference
================================

Interfaces
----------

.. module::  transaction.interfaces

.. autointerface:: ITransactionManager
   :members:
   :member-order: bysource

.. autointerface:: ITransaction
   :members:
   :member-order: bysource

.. autointerface:: IDataManager
   :members:
   :member-order: bysource

.. autointerface:: ISavepointDataManager
   :members:
   :member-order: bysource

.. autointerface:: IDataManagerSavepoint
   :members:
   :member-order: bysource

.. autointerface:: ISavepoint
   :members:
   :member-order: bysource

.. autoclass:: InvalidSavepointRollbackError
   :members:
   :member-order: bysource

.. autointerface:: ISynchronizer
   :members:
   :member-order: bysource

.. autoclass:: TransactionError
   :members:
   :member-order: bysource

.. autoclass:: TransactionFailedError
   :members:
   :member-order: bysource

.. autoclass:: DoomedTransaction
   :members:
   :member-order: bysource

.. autoclass:: TransientError
   :members:
   :member-order: bysource

API Objects
-----------

.. module:: transaction._transaction

.. autoclass:: Transaction
   :members:
   :member-order: bysource

.. autoclass:: Savepoint
   :members:
   :member-order: bysource

.. module:: transaction._manager

.. autoclass:: TransactionManager
   :members:
   :member-order: bysource

   .. automethod:: __enter__

      Alias for :meth:`get`

   .. automethod:: __exit__

      On error, aborts the current transaction.  Otherwise, commits.
.. autoclass:: ThreadTransactionManager
   :members:
   :member-order: bysource
