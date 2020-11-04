##############################################################################
#
# Copyright (c) 2012 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################
import mock
import unittest

import zope.interface.verify

from .. import interfaces


class TransactionManagerTests(unittest.TestCase):

    def _getTargetClass(self):
        from transaction import TransactionManager
        return TransactionManager

    def _makeOne(self):
        return self._getTargetClass()()

    def _makePopulated(self):
        mgr = self._makeOne()
        sub1 = DataObject(mgr)
        sub2 = DataObject(mgr)
        sub3 = DataObject(mgr)
        nosub1 = DataObject(mgr, nost=1)
        return mgr, sub1, sub2, sub3, nosub1

    def test_interface(self):
        zope.interface.verify.verifyObject(interfaces.ITransactionManager,
                                           self._makeOne())

    def test_ctor(self):
        tm = self._makeOne()
        self.assertTrue(tm._txn is None)
        self.assertEqual(len(tm._synchs), 0)

    def test_begin_wo_existing_txn_wo_synchs(self):
        from transaction._transaction import Transaction
        tm = self._makeOne()
        tm.begin()
        self.assertTrue(isinstance(tm._txn, Transaction))

    def test_begin_wo_existing_txn_w_synchs(self):
        from transaction._transaction import Transaction
        tm = self._makeOne()
        synch = DummySynch()
        tm.registerSynch(synch)
        tm.begin()
        self.assertTrue(isinstance(tm._txn, Transaction))
        self.assertTrue(tm._txn in synch._txns)

    def test_begin_w_existing_txn(self):
        class Existing(object):
            _aborted = False

            def abort(self):
                self._aborted = True
        tm = self._makeOne()
        tm._txn = txn = Existing()
        tm.begin()
        self.assertFalse(tm._txn is txn)
        self.assertTrue(txn._aborted)

    def test_get_wo_existing_txn(self):
        from transaction._transaction import Transaction
        tm = self._makeOne()
        txn = tm.get()
        self.assertTrue(isinstance(txn, Transaction))

    def test_get_w_existing_txn(self):
        class Existing(object):
            _aborted = False

            def abort(self):
                raise AssertionError("This is not actually called")
        tm = self._makeOne()
        tm._txn = txn = Existing()
        self.assertIs(tm.get(), txn)

    def test_free_w_other_txn(self):
        from transaction._transaction import Transaction
        tm = self._makeOne()
        txn = Transaction()
        tm.begin()
        self.assertRaises(ValueError, tm.free, txn)

    def test_free_w_existing_txn(self):
        class Existing(object):
            _aborted = False

            def abort(self):
                raise AssertionError("This is not actually called")
        tm = self._makeOne()
        tm._txn = txn = Existing()
        tm.free(txn)
        self.assertIsNone(tm._txn)

    def test_registerSynch(self):
        tm = self._makeOne()
        synch = DummySynch()
        tm.registerSynch(synch)
        self.assertEqual(len(tm._synchs), 1)
        self.assertTrue(synch in tm._synchs)

    def test_unregisterSynch(self):
        tm = self._makeOne()
        synch1 = DummySynch()
        synch2 = DummySynch()
        self.assertFalse(tm.registeredSynchs())
        tm.registerSynch(synch1)
        self.assertTrue(tm.registeredSynchs())
        tm.registerSynch(synch2)
        self.assertTrue(tm.registeredSynchs())
        tm.unregisterSynch(synch1)
        self.assertTrue(tm.registeredSynchs())
        self.assertEqual(len(tm._synchs), 1)
        self.assertFalse(synch1 in tm._synchs)
        self.assertTrue(synch2 in tm._synchs)
        tm.unregisterSynch(synch2)
        self.assertFalse(tm.registeredSynchs())

    def test_clearSynchs(self):
        tm = self._makeOne()
        synch1 = DummySynch()
        synch2 = DummySynch()
        tm.registerSynch(synch1)
        tm.registerSynch(synch2)
        tm.clearSynchs()
        self.assertEqual(len(tm._synchs), 0)

    def test_isDoomed_wo_existing_txn(self):
        tm = self._makeOne()
        self.assertFalse(tm.isDoomed())
        tm._txn.doom()
        self.assertTrue(tm.isDoomed())

    def test_isDoomed_w_existing_txn(self):
        class Existing(object):
            _doomed = False

            def isDoomed(self):
                return self._doomed
        tm = self._makeOne()
        tm._txn = txn = Existing()
        self.assertFalse(tm.isDoomed())
        txn._doomed = True
        self.assertTrue(tm.isDoomed())

    def test_doom(self):
        tm = self._makeOne()
        txn = tm.get()
        self.assertFalse(txn.isDoomed())
        tm.doom()
        self.assertTrue(txn.isDoomed())
        self.assertTrue(tm.isDoomed())

    def test_commit_w_existing_txn(self):
        class Existing(object):
            _committed = False

            def commit(self):
                self._committed = True
        tm = self._makeOne()
        tm._txn = txn = Existing()
        tm.commit()
        self.assertTrue(txn._committed)

    def test_abort_w_existing_txn(self):
        class Existing(object):
            _aborted = False

            def abort(self):
                self._aborted = True
        tm = self._makeOne()
        tm._txn = txn = Existing()
        tm.abort()
        self.assertTrue(txn._aborted)

    def test_as_context_manager_wo_error(self):
        class _Test(object):
            _committed = False
            _aborted = False

            def commit(self):
                self._committed = True

            def abort(self):
                raise AssertionError("This should not be called")
        tm = self._makeOne()
        with tm:
            tm._txn = txn = _Test()
        self.assertTrue(txn._committed)
        self.assertFalse(txn._aborted)

    def test_as_context_manager_w_error(self):
        class _Test(object):
            _committed = False
            _aborted = False

            def commit(self):
                raise AssertionError("This should not be called")

            def abort(self):
                self._aborted = True
        tm = self._makeOne()

        with self.assertRaises(ZeroDivisionError):
            with tm:
                tm._txn = txn = _Test()
                raise ZeroDivisionError()

        self.assertFalse(txn._committed)
        self.assertTrue(txn._aborted)

    def test_savepoint_default(self):
        class _Test(object):
            _sp = None

            def savepoint(self, optimistic):
                self._sp = optimistic
        tm = self._makeOne()
        tm._txn = txn = _Test()
        tm.savepoint()
        self.assertFalse(txn._sp)

    def test_savepoint_explicit(self):
        class _Test(object):
            _sp = None

            def savepoint(self, optimistic):
                self._sp = optimistic
        tm = self._makeOne()
        tm._txn = txn = _Test()
        tm.savepoint(True)
        self.assertTrue(txn._sp)

    def test_attempts_w_invalid_count(self):
        tm = self._makeOne()
        self.assertRaises(ValueError, list, tm.attempts(0))
        self.assertRaises(ValueError, list, tm.attempts(-1))
        self.assertRaises(ValueError, list, tm.attempts(-10))

    def test_attempts_w_valid_count(self):
        tm = self._makeOne()
        found = list(tm.attempts(1))
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0] is tm)

    def test_attempts_stop_on_success(self):
        tm = self._makeOne()

        i = 0
        for attempt in tm.attempts():
            with attempt:
                i += 1

        self.assertEqual(i, 1)

    def test_attempts_retries(self):
        import transaction.interfaces

        class Retry(transaction.interfaces.TransientError):
            pass

        tm = self._makeOne()
        i = 0
        for attempt in tm.attempts(4):
            with attempt:
                i += 1
                if i < 4:
                    raise Retry

        self.assertEqual(i, 4)

    def test_attempts_retries_but_gives_up(self):
        import transaction.interfaces

        class Retry(transaction.interfaces.TransientError):
            pass

        tm = self._makeOne()
        i = 0

        with self.assertRaises(Retry):
            for attempt in tm.attempts(4):
                with attempt:
                    i += 1
                    raise Retry

        self.assertEqual(i, 4)

    def test_attempts_propigates_errors(self):
        tm = self._makeOne()
        with self.assertRaises(ValueError):
            for attempt in tm.attempts(4):
                with attempt:
                    raise ValueError

    def test_attempts_defer_to_dm(self):
        import transaction.tests.savepointsample

        class DM(transaction.tests.savepointsample.SampleSavepointDataManager):
            def should_retry(self, e):
                if 'should retry' in str(e):
                    return True

        ntry = 0
        dm = transaction.tests.savepointsample.SampleSavepointDataManager()
        dm2 = DM()
        with transaction.manager:
            dm2['ntry'] = 0

        for attempt in transaction.manager.attempts():
            with attempt:
                ntry += 1
                dm['ntry'] = ntry
                dm2['ntry'] = ntry
                if ntry % 3:
                    raise ValueError('we really should retry this')

        self.assertEqual(ntry, 3)

    def test_attempts_w_default_count(self):
        from transaction._manager import Attempt
        tm = self._makeOne()
        found = list(tm.attempts())
        self.assertEqual(len(found), 3)
        for attempt in found[:-1]:
            self.assertTrue(isinstance(attempt, Attempt))
            self.assertTrue(attempt.manager is tm)
        self.assertTrue(found[-1] is tm)

    def test_run(self):
        import transaction.interfaces

        class Retry(transaction.interfaces.TransientError):
            pass

        tm = self._makeOne()
        i = [0, None]

        @tm.run()
        def meaning():
            """Nice doc"""
            i[0] += 1
            i[1] = tm.get()
            if i[0] < 3:
                raise Retry
            return 42

        self.assertEqual(i[0], 3)
        self.assertEqual(meaning, 42)
        self.assertEqual(i[1].description, "meaning\n\nNice doc")

    def test_run_no_name_explicit_tries(self):
        import transaction.interfaces

        class Retry(transaction.interfaces.TransientError):
            pass

        tm = self._makeOne()
        i = [0, None]

        @tm.run(4)
        def _():
            """Nice doc"""
            i[0] += 1
            i[1] = tm.get()
            if i[0] < 4:
                raise Retry

        self.assertEqual(i[0], 4)
        self.assertEqual(i[1].description, "Nice doc")

    def test_run_pos_tries(self):
        tm = self._makeOne()

        with self.assertRaises(ValueError):
            tm.run(0)(lambda: None)
        with self.assertRaises(ValueError):
            @tm.run(-1)
            def _():
                raise AssertionError("Never called")

    def test_run_stop_on_success(self):
        tm = self._makeOne()
        i = [0, None]

        @tm.run()
        def meaning():
            i[0] += 1
            i[1] = tm.get()
            return 43

        self.assertEqual(i[0], 1)
        self.assertEqual(meaning, 43)
        self.assertEqual(i[1].description, "meaning")

    def test_run_retries_but_gives_up(self):
        import transaction.interfaces

        class Retry(transaction.interfaces.TransientError):
            pass

        tm = self._makeOne()
        i = [0]

        with self.assertRaises(Retry):
            @tm.run()
            def _():
                i[0] += 1
                raise Retry

        self.assertEqual(i[0], 3)

    def test_run_propigates_errors(self):
        tm = self._makeOne()
        with self.assertRaises(ValueError):
            @tm.run
            def _():
                raise ValueError

    def test_run_defer_to_dm(self):
        import transaction.tests.savepointsample

        class DM(transaction.tests.savepointsample.SampleSavepointDataManager):
            def should_retry(self, e):
                if 'should retry' in str(e):
                    return True

        ntry = [0]
        dm = transaction.tests.savepointsample.SampleSavepointDataManager()
        dm2 = DM()
        with transaction.manager:
            dm2['ntry'] = 0

        @transaction.manager.run
        def _():
            ntry[0] += 1
            dm['ntry'] = ntry[0]
            dm2['ntry'] = ntry[0]
            if ntry[0] % 3:
                raise ValueError('we really should retry this')

        self.assertEqual(ntry[0], 3)

    def test_run_callable_with_bytes_doc(self):
        import transaction

        class Callable(object):

            def __init__(self):
                self.__doc__ = b'some bytes'
                self.__name__ = b'more bytes'

            def __call__(self):
                return 42

        result = transaction.manager.run(Callable())
        self.assertEqual(result, 42)

    def test__retryable_w_transient_error(self):
        from transaction.interfaces import TransientError
        tm = self._makeOne()
        self.assertTrue(tm._retryable(TransientError, object()))

    def test__retryable_w_transient_subclass(self):
        from transaction.interfaces import TransientError

        class _Derived(TransientError):
            pass
        tm = self._makeOne()
        self.assertTrue(tm._retryable(_Derived, object()))

    def test__retryable_w_normal_exception_no_resources(self):
        tm = self._makeOne()
        self.assertFalse(tm._retryable(Exception, object()))

    def test__retryable_w_normal_exception_w_resource_voting_yes(self):
        class _Resource(object):
            def should_retry(self, err):
                return True
        tm = self._makeOne()
        tm.get()._resources.append(_Resource())
        self.assertTrue(tm._retryable(Exception, object()))

    def test__retryable_w_multiple(self):
        class _Resource(object):
            _should = True

            def should_retry(self, err):
                return self._should
        tm = self._makeOne()
        res1 = _Resource()
        res1._should = False
        res2 = _Resource()
        tm.get()._resources.append(res1)
        tm.get()._resources.append(res2)
        self.assertTrue(tm._retryable(Exception, object()))

    # basic tests with two sub trans jars
    # really we only need one, so tests for
    # sub1 should identical to tests for sub2
    def test_commit_normal(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
        sub1.modify()
        sub2.modify()

        mgr.commit()

        assert sub1._p_jar.ccommit_sub == 0
        assert sub1._p_jar.ctpc_finish == 1

    def test_abort_normal(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
        sub1.modify()
        sub2.modify()

        mgr.abort()

        assert sub2._p_jar.cabort == 1

    # repeat adding in a nonsub trans jars

    def test_commit_w_nonsub_jar(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
        nosub1.modify()

        mgr.commit()

        assert nosub1._p_jar.ctpc_finish == 1

    def test_abort_w_nonsub_jar(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
        nosub1.modify()

        mgr.abort()

        assert nosub1._p_jar.ctpc_finish == 0
        assert nosub1._p_jar.cabort == 1

    ###
    # Failure Mode Tests
    #
    # ok now we do some more interesting
    # tests that check the implementations
    # error handling by throwing errors from
    # various jar methods
    ###

    # first the recoverable errors

    def test_abort_w_broken_jar(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
            sub1._p_jar = BasicJar(errors='abort')
            nosub1.modify()
            sub1.modify(nojar=1)
            sub2.modify()
            try:
                mgr.abort()
            except TestTxnException:
                pass

        assert nosub1._p_jar.cabort == 1
        assert sub2._p_jar.cabort == 1

    def test_commit_w_broken_jar_commit(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
            sub1._p_jar = BasicJar(errors='commit')
            nosub1.modify()
            sub1.modify(nojar=1)
            try:
                mgr.commit()
            except TestTxnException:
                pass

        assert nosub1._p_jar.ctpc_finish == 0
        assert nosub1._p_jar.ccommit == 1
        assert nosub1._p_jar.ctpc_abort == 1

    def test_commit_w_broken_jar_tpc_vote(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
            sub1._p_jar = BasicJar(errors='tpc_vote')
            nosub1.modify()
            sub1.modify(nojar=1)
            try:
                mgr.commit()
            except TestTxnException:
                pass

        assert nosub1._p_jar.ctpc_finish == 0
        assert nosub1._p_jar.ccommit == 1
        assert nosub1._p_jar.ctpc_abort == 1
        assert sub1._p_jar.ctpc_abort == 1

    def test_commit_w_broken_jar_tpc_begin(self):
        # ok this test reveals a bug in the TM.py
        # as the nosub tpc_abort there is ignored.

        # nosub calling method tpc_begin
        # nosub calling method commit
        # sub calling method tpc_begin
        # sub calling method abort
        # sub calling method tpc_abort
        # nosub calling method tpc_abort
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
            sub1._p_jar = BasicJar(errors='tpc_begin')
            nosub1.modify()
            sub1.modify(nojar=1)
            try:
                mgr.commit()
            except TestTxnException:
                pass

        assert nosub1._p_jar.ctpc_abort == 1
        assert sub1._p_jar.ctpc_abort == 1

    def test_commit_w_broken_jar_tpc_abort_tpc_vote(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            mgr, sub1, sub2, sub3, nosub1 = self._makePopulated()
            sub1._p_jar = BasicJar(errors=('tpc_abort', 'tpc_vote'))
            nosub1.modify()
            sub1.modify(nojar=1)
            try:
                mgr.commit()
            except TestTxnException:
                pass

        assert nosub1._p_jar.ctpc_abort == 1

    def test_notify_transaction_late_comers(self):
        # If a datamanager registers for synchonization after a
        # transaction has started, we should call newTransaction so it
        # can do necessry setup.
        import mock
        from .. import TransactionManager
        manager = TransactionManager()
        sync1 = mock.MagicMock()
        manager.registerSynch(sync1)
        sync1.newTransaction.assert_not_called()
        t = manager.begin()
        sync1.newTransaction.assert_called_with(t)
        sync2 = mock.MagicMock()
        manager.registerSynch(sync2)
        sync2.newTransaction.assert_called_with(t)

        # for, um, completeness
        t.commit()
        for s in sync1, sync2:
            s.beforeCompletion.assert_called_with(t)
            s.afterCompletion.assert_called_with(t)

    def test_unregisterSynch_on_transaction_manager_from_serparate_thread(
            self):
        # We should be able to get the underlying manager of the thread manager
        # and call methods from other threads.
        import threading
        import transaction

        started = threading.Event()
        stopped = threading.Event()

        synchronizer = self

        class Runner(threading.Thread):

            def __init__(self):
                threading.Thread.__init__(self)
                self.manager = transaction.manager.manager
                self.setDaemon(True)
                self.start()

            def run(self):
                self.manager.registerSynch(synchronizer)
                started.set()
                stopped.wait()

        runner = Runner()
        started.wait()
        runner.manager.unregisterSynch(synchronizer)
        stopped.set()
        runner.join(1)

    # The lack of the method below caused a test failure in one run
    #   -- caused indirectly by the failure of another test (this
    #   indicates that the tests in this suite are not fully isolated).
    #   However, defining the methods below reduced the "test coverage"
    #   once the initial test failure has been fixed.
    #   We therefore comment them out.
    #
    # the preceeding test (maybe others as well) registers `self` as
    # synchronizer; satisfy the `ISynchronizer` requirements
    #
    # def newTransaction(self, transaction):
    #     pass
    #
    # beforeCompletion = afterCompletion = newTransaction


class TestThreadTransactionManager(unittest.TestCase):

    def test_interface(self):
        import transaction
        zope.interface.verify.verifyObject(interfaces.ITransactionManager,
                                           transaction.manager)

    def test_sync_registration_thread_local_manager(self):
        import transaction

        sync = mock.MagicMock()
        sync2 = mock.MagicMock()
        self.assertFalse(transaction.manager.registeredSynchs())
        transaction.manager.registerSynch(sync)
        self.assertTrue(transaction.manager.registeredSynchs())
        transaction.manager.registerSynch(sync2)
        self.assertTrue(transaction.manager.registeredSynchs())
        t = transaction.begin()
        sync.newTransaction.assert_called_with(t)
        transaction.abort()
        sync.beforeCompletion.assert_called_with(t)
        sync.afterCompletion.assert_called_with(t)
        transaction.manager.unregisterSynch(sync)
        self.assertTrue(transaction.manager.registeredSynchs())
        transaction.manager.unregisterSynch(sync2)
        self.assertFalse(transaction.manager.registeredSynchs())
        sync.reset_mock()
        transaction.begin()
        transaction.abort()
        sync.newTransaction.assert_not_called()
        sync.beforeCompletion.assert_not_called()
        sync.afterCompletion.assert_not_called()

        self.assertFalse(transaction.manager.registeredSynchs())
        transaction.manager.registerSynch(sync)
        transaction.manager.registerSynch(sync2)
        t = transaction.begin()
        sync.newTransaction.assert_called_with(t)
        self.assertTrue(transaction.manager.registeredSynchs())
        transaction.abort()
        sync.beforeCompletion.assert_called_with(t)
        sync.afterCompletion.assert_called_with(t)
        transaction.manager.clearSynchs()
        self.assertFalse(transaction.manager.registeredSynchs())
        sync.reset_mock()
        transaction.begin()
        transaction.abort()
        sync.newTransaction.assert_not_called()
        sync.beforeCompletion.assert_not_called()
        sync.afterCompletion.assert_not_called()

    def test_explicit_thread_local_manager(self):
        import transaction.interfaces

        self.assertFalse(transaction.manager.explicit)
        transaction.abort()
        transaction.manager.explicit = True
        self.assertTrue(transaction.manager.explicit)
        with self.assertRaises(transaction.interfaces.NoTransaction):
            transaction.abort()
        transaction.manager.explicit = False
        transaction.abort()


class AttemptTests(unittest.TestCase):

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
        self.assertRaises(ValueError, inst.__exit__, None, None, None)
        self.assertTrue(manager.committed)
        self.assertTrue(manager.aborted)

    def test___exit__no_exc_abort_exception_after_nonretryable_commit_exc(
            self):
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
        self.assertRaises(KeyError, inst.__exit__, KeyError, KeyError(), None)
        self.assertFalse(manager.committed)
        self.assertTrue(manager.aborted)

    def test_explicit_mode(self):
        from .. import TransactionManager
        from ..interfaces import AlreadyInTransaction, NoTransaction

        tm = TransactionManager()
        self.assertFalse(tm.explicit)

        tm = TransactionManager(explicit=True)
        self.assertTrue(tm.explicit)
        for name in 'get', 'commit', 'abort', 'doom', 'isDoomed', 'savepoint':
            with self.assertRaises(NoTransaction):
                getattr(tm, name)()

        t = tm.begin()
        with self.assertRaises(AlreadyInTransaction):
            tm.begin()

        self.assertTrue(t is tm.get())

        self.assertFalse(tm.isDoomed())
        tm.doom()
        self.assertTrue(tm.isDoomed())
        tm.abort()

        for name in 'get', 'commit', 'abort', 'doom', 'isDoomed', 'savepoint':
            with self.assertRaises(NoTransaction):
                getattr(tm, name)()

        t = tm.begin()
        self.assertFalse(tm.isDoomed())
        with self.assertRaises(AlreadyInTransaction):
            tm.begin()
        tm.savepoint()
        tm.commit()


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


class DataObject:

    def __init__(self, transaction_manager, nost=0):
        self.transaction_manager = transaction_manager
        self.nost = nost
        self._p_jar = None

    def modify(self, nojar=0, tracing=0):
        if not nojar:
            if self.nost:
                self._p_jar = BasicJar(tracing=tracing)
            else:
                self._p_jar = BasicJar(tracing=tracing)
        self.transaction_manager.get().join(self._p_jar)


class TestTxnException(Exception):
    pass


class BasicJar(object):

    def __init__(self, errors=(), tracing=0):
        if not isinstance(errors, tuple):
            errors = errors,
        self.errors = errors
        self.tracing = tracing
        self.cabort = 0
        self.ccommit = 0
        self.ctpc_begin = 0
        self.ctpc_abort = 0
        self.ctpc_vote = 0
        self.ctpc_finish = 0
        self.cabort_sub = 0
        self.ccommit_sub = 0

    def __repr__(self):
        return "<%s %X %s>" % (self.__class__.__name__,
                               positive_id(self),
                               self.errors)

    def sortKey(self):
        # All these jars use the same sort key, and Python's list.sort()
        # is stable.  These two
        return self.__class__.__name__

    def check(self, method):
        if self.tracing:  # pragma: no cover
            print('%s calling method %s' % (str(self.tracing), method))

        if method in self.errors:
            raise TestTxnException("error %s" % method)

    # basic jar txn interface

    def abort(self, *args):
        self.check('abort')
        self.cabort += 1

    def commit(self, *args):
        self.check('commit')
        self.ccommit += 1

    def tpc_begin(self, txn, sub=0):
        self.check('tpc_begin')
        self.ctpc_begin += 1

    def tpc_vote(self, *args):
        self.check('tpc_vote')
        self.ctpc_vote += 1

    def tpc_abort(self, *args):
        self.check('tpc_abort')
        self.ctpc_abort += 1

    def tpc_finish(self, *args):
        self.check('tpc_finish')
        self.ctpc_finish += 1


class DummySynch(object):
    def __init__(self):
        self._txns = set()

    def newTransaction(self, txn):
        self._txns.add(txn)


def positive_id(obj):
    """Return id(obj) as a non-negative integer."""
    import struct
    _ADDRESS_MASK = 256 ** struct.calcsize('P')

    result = id(obj)
    if result < 0:  # pragma: no cover
        # Happens...on old 32-bit systems?
        result += _ADDRESS_MASK
        assert result > 0
    return result
