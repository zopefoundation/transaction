##############################################################################
#
# Copyright (c) 2001, 2002, 2005 Zope Foundation and Contributors.
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
"""Test transaction behavior for variety of cases.

I wrote these unittests to investigate some odd transaction
behavior when doing unittests of integrating non sub transaction
aware objects, and to insure proper txn behavior. these
tests test the transaction system independent of the rest of the
zodb.

you can see the method calls to a jar by passing the
keyword arg tracing to the modify method of a dataobject.
the value of the arg is a prefix used for tracing print calls
to that objects jar.

the number of times a jar method was called can be inspected
by looking at an attribute of the jar that is the method
name prefixed with a c (count/check).

i've included some tracing examples for tests that i thought
were illuminating as doc strings below.

TODO

    add in tests for objects which are modified multiple times,
    for example an object that gets modified in multiple sub txns.
"""
import unittest


class TransactionTests(unittest.TestCase):

    def _getTargetClass(self):
        from transaction._transaction import Transaction
        return Transaction

    def _makeOne(self, synchronizers=None, manager=None):
        return self._getTargetClass()(synchronizers, manager)

    def test_ctor_defaults(self):
        from transaction.weakset import WeakSet
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        from transaction import _transaction
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            t = self._makeOne()
        self.assertTrue(isinstance(t._synchronizers, WeakSet))
        self.assertEqual(len(t._synchronizers), 0)
        self.assertTrue(t._manager is None)
        self.assertTrue(t._savepoint2index is None)
        self.assertEqual(t._savepoint_index, 0)
        self.assertEqual(t._resources, [])
        self.assertEqual(t._adapters, {})
        self.assertEqual(t._voted, {})
        self.assertEqual(t._extension, {})
        self.assertTrue(t.log is logger)
        self.assertEqual(len(logger._log), 1)
        self.assertEqual(logger._log[0][0], 'DEBUG')
        self.assertEqual(logger._log[0][1], 'new transaction')
        self.assertTrue(t._failure_traceback is None)
        self.assertEqual(t._before_commit, [])
        self.assertEqual(t._after_commit, [])

    def test_ctor_w_syncs(self):
        from transaction.weakset import WeakSet
        synchs = WeakSet()
        t = self._makeOne(synchronizers=synchs)
        self.assertTrue(t._synchronizers is synchs)

    def test_isDoomed(self):
        from transaction._transaction import Status
        t = self._makeOne()
        self.assertFalse(t.isDoomed())
        t.status = Status.DOOMED
        self.assertTrue(t.isDoomed())

    def test_doom_active(self):
        from transaction._transaction import Status
        t = self._makeOne()
        t.doom()
        self.assertTrue(t.isDoomed())
        self.assertEqual(t.status, Status.DOOMED)

    def test_doom_invalid(self):
        from transaction._transaction import Status
        t = self._makeOne()
        for status in Status.COMMITTING, Status.COMMITTED, Status.COMMITFAILED:
            t.status = status
            self.assertRaises(ValueError, t.doom)

    def test_doom_already_doomed(self):
        from transaction._transaction import Status
        t = self._makeOne()
        t.status = Status.DOOMED
        self.assertTrue(t.isDoomed())
        self.assertEqual(t.status, Status.DOOMED)

    def test__prior_operation_failed(self):
        from transaction.interfaces import TransactionFailedError
        from transaction.tests.common import assertRaisesEx
        class _Traceback(object):
            def getvalue(self):
                return 'TRACEBACK'
        t = self._makeOne()
        t._failure_traceback = _Traceback()
        err = assertRaisesEx(TransactionFailedError, t._prior_operation_failed)
        self.assertTrue(str(err).startswith('An operation previously failed'))
        self.assertTrue(str(err).endswith( "with traceback:\n\nTRACEBACK"))

    def test_join_COMMITFAILED(self):
        from transaction.interfaces import TransactionFailedError
        from transaction._transaction import Status
        class _Traceback(object):
            def getvalue(self):
                return 'TRACEBACK'
        t = self._makeOne()
        t.status = Status.COMMITFAILED
        t._failure_traceback = _Traceback()
        self.assertRaises(TransactionFailedError, t.join, object())

    def test_join_COMMITTING(self):
        from transaction._transaction import Status
        t = self._makeOne()
        t.status = Status.COMMITTING
        self.assertRaises(ValueError, t.join, object())

    def test_join_COMMITTED(self):
        from transaction._transaction import Status
        t = self._makeOne()
        t.status = Status.COMMITTED
        self.assertRaises(ValueError, t.join, object())

    def test_join_DOOMED_non_preparing_wo_sp2index(self):
        from transaction._transaction import Status
        t = self._makeOne()
        t.status = Status.DOOMED
        resource = object()
        t.join(resource)
        self.assertEqual(t._resources, [resource])

    def test_join_ACTIVE_w_preparing_w_sp2index(self):
        from transaction._transaction import AbortSavepoint
        from transaction._transaction import DataManagerAdapter
        class _TSP(object):
            def __init__(self):
                self._savepoints = []
        class _DM(object):
            def prepare(self):
                pass
        t = self._makeOne()
        tsp = _TSP()
        t._savepoint2index = {tsp: object()}
        dm = _DM
        t.join(dm)
        self.assertEqual(len(t._resources), 1)
        dma = t._resources[0]
        self.assertTrue(isinstance(dma, DataManagerAdapter))
        self.assertTrue(t._resources[0]._datamanager is dm)
        self.assertEqual(len(tsp._savepoints), 1)
        self.assertTrue(isinstance(tsp._savepoints[0], AbortSavepoint))
        self.assertTrue(tsp._savepoints[0].datamanager is dma)
        self.assertTrue(tsp._savepoints[0].transaction is t)

    def test__unjoin_miss(self):
        tm = self._makeOne()
        tm._unjoin(object()) #no raise

    def test__unjoin_hit(self):
        t = self._makeOne()
        resource = object()
        t._resources.append(resource)
        t._unjoin(resource)
        self.assertEqual(t._resources, [])

    def test_savepoint_COMMITFAILED(self):
        from transaction.interfaces import TransactionFailedError
        from transaction._transaction import Status
        class _Traceback(object):
            def getvalue(self):
                return 'TRACEBACK'
        t = self._makeOne()
        t.status = Status.COMMITFAILED
        t._failure_traceback = _Traceback()
        self.assertRaises(TransactionFailedError, t.savepoint)

    def test_savepoint_empty(self):
        from weakref import WeakKeyDictionary
        from transaction import _transaction
        from transaction._transaction import Savepoint
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            t = self._makeOne()
        sp = t.savepoint()
        self.assertTrue(isinstance(sp, Savepoint))
        self.assertTrue(sp.transaction is t)
        self.assertEqual(sp._savepoints, [])
        self.assertEqual(t._savepoint_index, 1)
        self.assertTrue(isinstance(t._savepoint2index, WeakKeyDictionary))
        self.assertEqual(t._savepoint2index[sp], 1)

    def test_savepoint_non_optimistc_resource_wo_support(self):
        from transaction import _transaction
        from transaction._transaction import Status
        from transaction._compat import StringIO
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            t = self._makeOne()
        logger._clear()
        resource = object()
        t._resources.append(resource)
        self.assertRaises(TypeError, t.savepoint)
        self.assertEqual(t.status,  Status.COMMITFAILED)
        self.assertTrue(isinstance(t._failure_traceback, StringIO))
        self.assertTrue('TypeError' in t._failure_traceback.getvalue())
        self.assertEqual(len(logger._log), 2)
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(logger._log[0][1].startswith('Error in abort'))
        self.assertEqual(logger._log[1][0], 'error')
        self.assertTrue(logger._log[1][1].startswith('Error in tpc_abort'))

    def test__remove_and_invalidate_after_miss(self):
        from weakref import WeakKeyDictionary
        t = self._makeOne()
        t._savepoint2index = WeakKeyDictionary()
        class _SP(object):
            def __init__(self, t):
                self.transaction = t
        holdme = []
        for i in range(10):
            sp = _SP(t)
            holdme.append(sp) #prevent gc
            t._savepoint2index[sp] = i
        self.assertEqual(len(t._savepoint2index), 10)
        self.assertRaises(KeyError, t._remove_and_invalidate_after, _SP(t))
        self.assertEqual(len(t._savepoint2index), 10)

    def test__remove_and_invalidate_after_hit(self):
        from weakref import WeakKeyDictionary
        t = self._makeOne()
        t._savepoint2index = WeakKeyDictionary()
        class _SP(object):
            def __init__(self, t, index):
                self.transaction = t
                self._index = index
            def __lt__(self, other):
                return self._index < other._index
            def __repr__(self):
                return '_SP: %d' % self._index
        holdme = []
        for i in range(10):
            sp = _SP(t, i)
            holdme.append(sp) #prevent gc
            t._savepoint2index[sp] = i
        self.assertEqual(len(t._savepoint2index), 10)
        t._remove_and_invalidate_after(holdme[1])
        self.assertEqual(sorted(t._savepoint2index), sorted(holdme[:2]))

    def test__invalidate_all_savepoints(self):
        from weakref import WeakKeyDictionary
        t = self._makeOne()
        t._savepoint2index = WeakKeyDictionary()
        class _SP(object):
            def __init__(self, t, index):
                self.transaction = t
                self._index = index
            def __repr__(self):
                return '_SP: %d' % self._index
        holdme = []
        for i in range(10):
            sp = _SP(t, i)
            holdme.append(sp) #prevent gc
            t._savepoint2index[sp] = i
        self.assertEqual(len(t._savepoint2index), 10)
        t._invalidate_all_savepoints()
        self.assertEqual(list(t._savepoint2index), [])

    def test_register_wo_jar(self):
        class _Dummy(object):
            _p_jar = None
        t = self._makeOne()
        self.assertRaises(ValueError, t.register, _Dummy())

    def test_register_w_jar(self):
        class _Manager(object):
            pass
        mgr = _Manager()
        class _Dummy(object):
            _p_jar = mgr
        t = self._makeOne()
        dummy = _Dummy()
        t.register(dummy)
        resources = list(t._resources)
        self.assertEqual(len(resources), 1)
        adapter = resources[0]
        self.assertTrue(adapter.manager is mgr)
        self.assertTrue(dummy in adapter.objects)
        items = list(t._adapters.items())
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0][0] is mgr)
        self.assertTrue(items[0][1] is adapter)

    def test_register_w_jar_already_adapted(self):
        class _Adapter(object):
            def __init__(self):
                self.objects = []
        class _Manager(object):
            pass
        mgr = _Manager()
        class _Dummy(object):
            _p_jar = mgr
        t = self._makeOne()
        t._adapters[mgr] = adapter = _Adapter()
        dummy = _Dummy()
        t.register(dummy)
        self.assertTrue(dummy in adapter.objects)

    def test_note(self):
        t = self._makeOne()
        try:
            t.note('This is a note.')
            self.assertEqual(t.description, 'This is a note.')
            t.note('Another.')
            self.assertEqual(t.description, 'This is a note.\nAnother.')
        finally:
            t.abort()


class Test_oid_repr(unittest.TestCase):

    def _callFUT(self, oid):
        from transaction._transaction import oid_repr
        return oid_repr(oid)

    def test_as_nonstring(self):
        self.assertEqual(self._callFUT(123), '123')

    def test_as_string_not_8_chars(self):
        self.assertEqual(self._callFUT('a'), "'a'")

    def test_as_string_z64(self):
        s = '\0'*8
        self.assertEqual(self._callFUT(s), '0x00')

    def test_as_string_all_Fs(self):
        s = '\1'*8
        self.assertEqual(self._callFUT(s), '0x0101010101010101')


class MiscellaneousTests(unittest.TestCase):

    def test_BBB_join(self):
        # The join method is provided for "backward-compatability" with ZODB 4
        # data managers.
        from transaction import Transaction
        from transaction.tests.examples import DataManager
        from transaction._transaction import DataManagerAdapter
        # The argument to join must be a zodb4 data manager,
        # transaction.interfaces.IDataManager.
        t = Transaction()
        dm = DataManager()
        t.join(dm)
        # The end result is that a data manager adapter is one of the
        # transaction's objects:
        self.assertTrue(isinstance(t._resources[0], DataManagerAdapter))
        self.assertTrue(t._resources[0]._datamanager is dm)

    def test_bug239086(self):
        # The original implementation of thread transaction manager made
        # invalid assumptions about thread ids.
        import threading
        import transaction
        import transaction.tests.savepointsample as SPS
        dm = SPS.SampleSavepointDataManager()
        self.assertEqual(list(dm.keys()), [])

        class Sync:
             def __init__(self, label):
                 self.label = label
                 self.log = []
             def beforeCompletion(self, t):
                 self.log.append('%s %s' % (self.label, 'before'))
             def afterCompletion(self, t):
                 self.log.append('%s %s' % (self.label, 'after'))
             def newTransaction(self, t):
                 self.log.append('%s %s' % (self.label, 'new'))

        def run_in_thread(f):
            t = threading.Thread(target=f)
            t.start()
            t.join()

        sync = Sync(1)
        @run_in_thread
        def first():
            transaction.manager.registerSynch(sync)
            transaction.manager.begin()
            dm['a'] = 1
        self.assertEqual(sync.log, ['1 new'])

        @run_in_thread
        def second():
            transaction.abort() # should do nothing.
        self.assertEqual(sync.log, ['1 new'])
        self.assertEqual(list(dm.keys()), ['a'])

        dm = SPS.SampleSavepointDataManager()
        self.assertEqual(list(dm.keys()), [])

        @run_in_thread
        def third():
            dm['a'] = 1
        self.assertEqual(sync.log, ['1 new'])

        transaction.abort() # should do nothing
        self.assertEqual(list(dm.keys()), ['a'])

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TransactionTests),
        unittest.makeSuite(Test_oid_repr),
        unittest.makeSuite(MiscellaneousTests),
        ))
