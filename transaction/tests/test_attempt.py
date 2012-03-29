import unittest

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
