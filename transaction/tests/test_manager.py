import unittest

class TestTransactionManager(unittest.TestCase):
    def setUp(self):
        self.txn = DummyTransaction()
        self.begun = 0
        
    def _makeOne(self):
        from transaction._manager import TransactionManager
        return TransactionManager()

    def begin(self):
        self.begun += 1
        return self.txn

    def test_job_no_args(self):
        inst = self._makeOne()
        @inst.job
        def func(tx):
            pass
        self.assertEqual(func.__name__, 'func')

    def test_job_no_retries_no_exception(self):
        inst = self._makeOne()
        inst.begin = self.begin
        L = []
        @inst.job
        def func(tx):
            L.append(1)
        func()
        self.assertEqual(L, [1])
        self.assertEqual(self.begun, 1)
        self.assertEqual(self.txn.notes, ['func'])
        self.assertEqual(self.txn.committed, 1)

    def test_job_with_args(self):
        inst = self._makeOne()
        inst.begin = self.begin
        L = []
        @inst.job
        def func(tx, foo, bar=1):
            L.append((foo, bar))
        func('foo', bar=2)
        self.assertEqual(L, [('foo', 2)])
        self.assertEqual(self.begun, 1)
        self.assertEqual(self.txn.notes, ['func'])
        self.assertEqual(self.txn.committed, 1)
        
    def test_job_no_retries_no_exception_func_has_doc(self):
        inst = self._makeOne()
        inst.begin = self.begin
        L = []
        @inst.job
        def func(tx):
            """ doc\n a """
            L.append(1)
        func()
        self.assertEqual(L, [1])
        self.assertEqual(self.begun, 1)
        self.assertEqual(self.txn.notes, ['doc'])
        self.assertEqual(self.txn.committed, 1)
        
    def test_job_no_retries_with_retryable_exception_in_func(self):
        from transaction.interfaces import TransientError
        inst = self._makeOne()
        inst.begin = self.begin
        @inst.job
        def func(tx):
            raise TransientError
        self.assertRaises(TransientError, func)
        self.assertEqual(self.begun, 1)
        self.assertEqual(self.txn.aborted, 1)
        self.assertEqual(self.txn.notes, ['func'])

    def test_job_no_retries_with_retryable_exception_in_commit(self):
        from transaction.interfaces import TransientError
        inst = self._makeOne()
        inst.begin = self.begin
        self.txn.commitraises = TransientError
        L = []
        @inst.job
        def func(tx):
            L.append(1)
        self.assertRaises(TransientError, func)
        self.assertEqual(L, [1])
        self.assertEqual(self.begun, 1)
        self.assertEqual(self.txn.aborted, 1)
        self.assertEqual(self.txn.notes, ['func'])
        self.assertEqual(self.txn.committed, 1)

    def test_job_retries_with_retryable_exception_in_func(self):
        from transaction.interfaces import TransientError
        inst = self._makeOne()
        inst.begin = self.begin
        @inst.job(retries=2)
        def func(tx):
            if tx.aborted == 2:
                return
            raise TransientError
        func()
        self.assertEqual(self.begun, 3)
        self.assertEqual(self.txn.aborted, 2)
        self.assertEqual(self.txn.notes, 
                         ['func', 'func (retry: 1)', 'func (retry: 2)'])
        self.assertEqual(self.txn.committed, 1)

    def test_job_retries_with_retryable_exception_in_commit(self):
        from transaction.interfaces import TransientError
        inst = self._makeOne()
        inst.begin = self.begin
        def commit():
            if self.txn.aborted == 2:
                self.txn.committed += 1
                return
            raise TransientError
        self.txn.commit = commit
        L = []
        @inst.job(retries=2)
        def func(tx):
            L.append(1)
        func()
        self.assertEqual(L, [1, 1, 1])
        self.assertEqual(self.begun, 3)
        self.assertEqual(self.txn.aborted, 2)
        self.assertEqual(self.txn.notes, 
                         ['func', 'func (retry: 1)', 'func (retry: 2)'])
        self.assertEqual(self.txn.committed, 1)

    def test_as_decorator(self):
        L = []
        manager = self._makeOne()
        manager.begin = self.begin
        @manager.job()
        def func(tx):
            L.append(1)
        func()
        self.assertEqual(L, [1])
        self.assertEqual(self.begun, 1)
        self.assertEqual(self.txn.notes, ['func'])
        self.assertEqual(self.txn.committed, 1)
        
class TestAttempt(unittest.TestCase):
    def _makeOne(self, manager):
        from transaction._manager import Attempt
        return Attempt(manager)

    def test___enter__(self):
        manager = DummyManager()
        inst = self._makeOne(manager)
        inst.__enter__()
        self.assertTrue(manager.entered)

    def test___exit__no_exc_no_commit_exception(self):
        manager = DummyManager()
        inst = self._makeOne(manager)
        result = inst.__exit__(None, None, None)
        self.assertFalse(result)
        self.assertTrue(manager.committed)

    def test___exit__no_exc_nonretryable_commit_exception(self):
        manager = DummyManager(raise_on_commit=ValueError)
        inst = self._makeOne(manager)
        result = inst.__exit__(None, None, None)
        self.assertFalse(result)

    def test___exit__no_exc_abort_exception_after_nonretryable_commit_exc(self):
        manager = DummyManager(raise_on_abort=ValueError, 
                               raise_on_commit=KeyError)
        inst = self._makeOne(manager)
        self.assertRaises(ValueError, inst.__exit__, None, None, None)
        self.assertTrue(manager.committed)
        self.assertTrue(manager.aborted)
        
    def test___exit__no_exc_retryable_commit_exception(self):
        from transaction.interfaces import TransientError
        manager = DummyManager(raise_on_commit=TransientError)
        inst = self._makeOne(manager)
        result = inst.__exit__(None, None, None)
        self.assertTrue(result)
        self.assertTrue(manager.committed)
        self.assertTrue(manager.aborted)

    def test___exit__with_exception_value_retryable(self):
        from transaction.interfaces import TransientError
        manager = DummyManager()
        inst = self._makeOne(manager)
        result = inst.__exit__(TransientError, TransientError(), None)
        self.assertTrue(result)
        self.assertFalse(manager.committed)
        self.assertTrue(manager.aborted)

    def test___exit__with_exception_value_nonretryable(self):
        manager = DummyManager()
        inst = self._makeOne(manager)
        result = inst.__exit__(KeyError, KeyError(), None)
        self.assertFalse(result)
        self.assertFalse(manager.committed)
        self.assertTrue(manager.aborted)
        
class DummyManager(object):
    entered = False
    committed = False
    aborted = False
    
    def __init__(self, raise_on_commit=None, raise_on_abort=None):
        self.raise_on_commit = raise_on_commit
        self.raise_on_abort = raise_on_abort

    def _retryable(self, t, v):
        from transaction._manager import TransientError
        return issubclass(t, TransientError)
        
    def __enter__(self):
        self.entered = True

    def abort(self):
        self.aborted = True
        if self.raise_on_abort:
            raise self.raise_on_abort
        
    def commit(self):
        self.committed = True
        if self.raise_on_commit:
            raise self.raise_on_commit

class DummyTransaction(object):

    committed = 0
    aborted = 0
    commitraises = None
    
    def __init__(self):
        self.notes = []
        
    def note(self, note):
        self.notes.append(note)

    def commit(self):
        self.committed += 1
        if self.commitraises:
            raise self.commitraises

    def abort(self):
        self.aborted += 1
