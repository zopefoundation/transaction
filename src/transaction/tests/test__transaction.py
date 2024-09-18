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
import os
import unittest
import warnings


class TransactionTests(unittest.TestCase):

    def _getTargetClass(self):
        from transaction._transaction import Transaction
        return Transaction

    def _makeOne(self, synchronizers=None, manager=None):
        return self._getTargetClass()(synchronizers, manager)

    def test_verifyImplements_ITransaction(self):
        from zope.interface.verify import verifyClass

        from transaction.interfaces import ITransaction
        verifyClass(ITransaction, self._getTargetClass())

    def test_verifyProvides_ITransaction(self):
        from zope.interface.verify import verifyObject

        from transaction.interfaces import ITransaction
        verifyObject(ITransaction, self._makeOne())

    def test_ctor_defaults(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        from transaction.weakset import WeakSet
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        self.assertIsInstance(txn._synchronizers, WeakSet)
        self.assertEqual(len(txn._synchronizers), 0)
        self.assertIsNone(txn._manager)
        self.assertEqual(txn.user, "")
        self.assertEqual(txn.description, "")
        self.assertIsNone(txn._savepoint2index)
        self.assertEqual(txn._savepoint_index, 0)
        self.assertEqual(txn._resources, [])
        self.assertEqual(txn._adapters, {})
        self.assertEqual(txn._voted, {})
        self.assertEqual(txn.extension, {})
        self.assertIs(txn._extension, txn.extension)  # legacy
        self.assertIs(txn.log, logger)
        self.assertEqual(len(logger._log), 1)
        self.assertEqual(logger._log[0][0], 'debug')
        self.assertEqual(logger._log[0][1], 'new transaction')
        self.assertIsNone(txn._failure_traceback)
        self.assertEqual(txn._before_commit, [])
        self.assertEqual(txn._after_commit, [])

    def test_ctor_w_syncs(self):
        from transaction.weakset import WeakSet
        synchs = WeakSet()
        txn = self._makeOne(synchronizers=synchs)
        self.assertIs(txn._synchronizers, synchs)

    def test_isDoomed(self):
        from transaction._transaction import Status
        txn = self._makeOne()
        self.assertFalse(txn.isDoomed())
        txn.status = Status.DOOMED
        self.assertTrue(txn.isDoomed())

    def test_doom_active(self):
        from transaction._transaction import Status
        txn = self._makeOne()
        txn.doom()
        self.assertTrue(txn.isDoomed())
        self.assertEqual(txn.status, Status.DOOMED)

    def test_doom_invalid(self):
        from transaction._transaction import Status
        txn = self._makeOne()
        for status in Status.COMMITTING, Status.COMMITTED, Status.COMMITFAILED:
            txn.status = status
            self.assertRaises(ValueError, txn.doom)

    def test_doom_already_doomed(self):
        from transaction._transaction import Status
        txn = self._makeOne()
        txn.status = Status.DOOMED
        txn.doom()
        self.assertTrue(txn.isDoomed())
        self.assertEqual(txn.status, Status.DOOMED)

    def test__prior_operation_failed(self):
        from transaction.interfaces import TransactionFailedError

        class _Traceback:
            def getvalue(self):
                return 'TRACEBACK'
        txn = self._makeOne()
        txn._failure_traceback = _Traceback()
        with self.assertRaises(TransactionFailedError) as exc:
            txn._prior_operation_failed()
        err = exc.exception
        self.assertTrue(str(err).startswith('An operation previously failed'))
        self.assertTrue(str(err).endswith("with traceback:\n\nTRACEBACK"))

    def test_join_COMMITFAILED(self):
        from transaction._transaction import Status
        from transaction.interfaces import TransactionFailedError

        class _Traceback:
            def getvalue(self):
                return 'TRACEBACK'
        txn = self._makeOne()
        txn.status = Status.COMMITFAILED
        txn._failure_traceback = _Traceback()
        self.assertRaises(TransactionFailedError, txn.join, object())

    def test_join_COMMITTING(self):
        from transaction._transaction import Status
        txn = self._makeOne()
        txn.status = Status.COMMITTING
        self.assertRaises(ValueError, txn.join, object())

    def test_join_COMMITTED(self):
        from transaction._transaction import Status
        txn = self._makeOne()
        txn.status = Status.COMMITTED
        self.assertRaises(ValueError, txn.join, object())

    def test_join_DOOMED_non_preparing_wo_sp2index(self):
        from transaction._transaction import Status
        txn = self._makeOne()
        txn.status = Status.DOOMED
        resource = object()
        txn.join(resource)
        self.assertEqual(txn._resources, [resource])

    def test__unjoin_miss(self):
        txn = self._makeOne()
        txn._unjoin(object())  # no raise

    def test__unjoin_hit(self):
        txn = self._makeOne()
        resource = object()
        txn._resources.append(resource)
        txn._unjoin(resource)
        self.assertEqual(txn._resources, [])

    def test_savepoint_COMMITFAILED(self):
        from transaction._transaction import Status
        from transaction.interfaces import TransactionFailedError

        class _Traceback:
            def getvalue(self):
                return 'TRACEBACK'
        txn = self._makeOne()
        txn.status = Status.COMMITFAILED
        txn._failure_traceback = _Traceback()
        self.assertRaises(TransactionFailedError, txn.savepoint)

    def test_savepoint_empty(self):
        from weakref import WeakKeyDictionary

        from transaction import _transaction
        from transaction._transaction import Savepoint
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        sp = txn.savepoint()
        self.assertIsInstance(sp, Savepoint)
        self.assertIs(sp.transaction, txn)
        self.assertEqual(sp._savepoints, [])
        self.assertEqual(txn._savepoint_index, 1)
        self.assertIsInstance(txn._savepoint2index, WeakKeyDictionary)
        self.assertEqual(txn._savepoint2index[sp], 1)

    def test_savepoint_non_optimistc_resource_wo_support(self):
        from io import StringIO

        from transaction import _transaction
        from transaction._transaction import Status
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        resource = object()
        txn._resources.append(resource)
        self.assertRaises(TypeError, txn.savepoint)
        self.assertEqual(txn.status, Status.COMMITFAILED)
        self.assertIsInstance(txn._failure_traceback, StringIO)
        self.assertIn('TypeError', txn._failure_traceback.getvalue())
        self.assertEqual(len(logger._log), 2)
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(logger._log[0][1].startswith('Error in abort'))
        self.assertEqual(logger._log[1][0], 'error')
        self.assertTrue(logger._log[1][1].startswith('Error in tpc_abort'))

    def test__remove_and_invalidate_after_miss(self):
        from weakref import WeakKeyDictionary
        txn = self._makeOne()
        txn._savepoint2index = WeakKeyDictionary()

        class _SP:
            def __init__(self, txn):
                self.transaction = txn
        holdme = []
        for i in range(10):
            sp = _SP(txn)
            holdme.append(sp)  # prevent gc
            txn._savepoint2index[sp] = i
        self.assertEqual(len(txn._savepoint2index), 10)
        self.assertRaises(KeyError, txn._remove_and_invalidate_after, _SP(txn))
        self.assertEqual(len(txn._savepoint2index), 10)

    def test__remove_and_invalidate_after_hit(self):
        from weakref import WeakKeyDictionary
        txn = self._makeOne()
        txn._savepoint2index = WeakKeyDictionary()

        class _SP:
            def __init__(self, txn, index):
                self.transaction = txn
                self._index = index

            def __lt__(self, other):
                return self._index < other._index

            def __repr__(self):  # pragma: no cover
                return '_SP: %d' % self._index
        holdme = []
        for i in range(10):
            sp = _SP(txn, i)
            holdme.append(sp)  # prevent gc
            txn._savepoint2index[sp] = i
        self.assertEqual(len(txn._savepoint2index), 10)
        txn._remove_and_invalidate_after(holdme[1])
        self.assertEqual(sorted(txn._savepoint2index), sorted(holdme[:2]))

    def test__invalidate_all_savepoints(self):
        from weakref import WeakKeyDictionary
        txn = self._makeOne()
        txn._savepoint2index = WeakKeyDictionary()

        class _SP:
            def __init__(self, txn, index):
                self.transaction = txn
                self._index = index

            def __repr__(self):  # pragma: no cover
                return '_SP: %d' % self._index
        holdme = []
        for i in range(10):
            sp = _SP(txn, i)
            holdme.append(sp)  # prevent gc
            txn._savepoint2index[sp] = i
        self.assertEqual(len(txn._savepoint2index), 10)
        txn._invalidate_all_savepoints()
        self.assertEqual(list(txn._savepoint2index), [])

    def test_commit_DOOMED(self):
        from transaction._transaction import Status
        from transaction.interfaces import DoomedTransaction
        txn = self._makeOne()
        txn.status = Status.DOOMED
        self.assertRaises(DoomedTransaction, txn.commit)

    def test_commit_COMMITFAILED(self):
        from transaction._transaction import Status
        from transaction.interfaces import TransactionFailedError

        class _Traceback:
            def getvalue(self):
                return 'TRACEBACK'
        txn = self._makeOne()
        txn.status = Status.COMMITFAILED
        txn._failure_traceback = _Traceback()
        self.assertRaises(TransactionFailedError, txn.commit)

    def test_commit_wo_savepoints_wo_hooks_wo_synchronizers(self):
        from transaction import _transaction
        from transaction._transaction import Status
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class _Mgr:
            def __init__(self, txn):
                self._txn = txn

            def free(self, txn):
                assert txn is self._txn
                self._txn = None
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            logger._clear()
            mgr = txn._manager = _Mgr(txn)
            txn.commit()
        self.assertEqual(txn.status, Status.COMMITTED)
        self.assertIsNone(mgr._txn)
        self.assertEqual(logger._log[0][0], 'debug')
        self.assertEqual(logger._log[0][1], 'commit')

    def test_commit_w_savepoints(self):
        from weakref import WeakKeyDictionary

        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class _SP:
            def __init__(self, txn, index):
                self.transaction = txn
                self._index = index

            def __repr__(self):  # pragma: no cover
                return '_SP: %d' % self._index
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._savepoint2index = WeakKeyDictionary()
            holdme = []
            for i in range(10):
                sp = _SP(txn, i)
                holdme.append(sp)  # prevent gc
                txn._savepoint2index[sp] = i
            logger._clear()
            txn.commit()
        self.assertEqual(list(txn._savepoint2index), [])

    def test_commit_w_beforeCommitHooks(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked1, _hooked2 = [], []

        def _hook1(*args, **kw):
            _hooked1.append((args, kw))

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._before_commit.append((_hook1, ('one',), {'uno': 1}))
            txn._before_commit.append((_hook2, (), {}))
            logger._clear()
            txn.commit()
        self.assertEqual(_hooked1, [(('one',), {'uno': 1})])
        self.assertEqual(_hooked2, [((), {})])
        self.assertEqual(txn._before_commit, [])

    def test_commit_w_synchronizers(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        from transaction.weakset import WeakSet

        class _Synch:
            _before = _after = False

            def beforeCompletion(self, txn):
                self._before = txn

            def afterCompletion(self, txn):
                self._after = txn
        synchs = [_Synch(), _Synch(), _Synch()]
        ws = WeakSet()
        for synch in synchs:
            ws.add(synch)
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne(synchronizers=ws)
            logger._clear()
            txn.commit()
        for synch in synchs:
            self.assertIs(synch._before, txn)
            self.assertIs(synch._after, txn)

    def test_commit_w_afterCommitHooks(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked1, _hooked2 = [], []

        def _hook1(*args, **kw):
            _hooked1.append((args, kw))

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._after_commit.append((_hook1, ('one',), {'uno': 1}))
            txn._after_commit.append((_hook2, (), {}))
            logger._clear()
            txn.commit()
        self.assertEqual(_hooked1, [((True, 'one',), {'uno': 1})])
        self.assertEqual(_hooked2, [((True,), {})])
        self.assertEqual(txn._after_commit, [])
        self.assertEqual(txn._resources, [])

    def test_commit_error_w_afterCompleteHooks(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class BrokenResource:
            def sortKey(self):
                return 'zzz'

            def tpc_begin(self, txn):
                raise ValueError('test')
        broken = BrokenResource()
        resource = Resource('aaa')
        _hooked1, _hooked2 = [], []

        def _hook1(*args, **kw):
            _hooked1.append((args, kw))

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._after_commit.append((_hook1, ('one',), {'uno': 1}))
            txn._after_commit.append((_hook2, (), {}))
            txn._resources.append(broken)
            txn._resources.append(resource)
            logger._clear()
            self.assertRaises(ValueError, txn.commit)
        self.assertEqual(_hooked1, [((False, 'one',), {'uno': 1})])
        self.assertEqual(_hooked2, [((False,), {})])
        self.assertEqual(txn._after_commit, [])
        self.assertTrue(resource._b)
        self.assertFalse(resource._c)
        self.assertFalse(resource._v)
        self.assertFalse(resource._f)
        self.assertTrue(resource._a)
        self.assertTrue(resource._x)

    def test_commit_error_w_synchronizers(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        from transaction.weakset import WeakSet

        class _Synch:
            _before = _after = False

            def beforeCompletion(self, txn):
                self._before = txn

            def afterCompletion(self, txn):
                self._after = txn
        synchs = [_Synch(), _Synch(), _Synch()]
        ws = WeakSet()
        for synch in synchs:
            ws.add(synch)

        class BrokenResource:
            def sortKey(self):
                return 'zzz'

            def tpc_begin(self, txn):
                raise ValueError('test')
        broken = BrokenResource()
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne(synchronizers=ws)
            logger._clear()
            txn._resources.append(broken)
            self.assertRaises(ValueError, txn.commit)
        for synch in synchs:
            self.assertIs(synch._before, txn)
            self.assertIs(synch._after, txn)  # called in _cleanup

    def test_commit_clears_resources(self):
        class DM:
            tpc_begin = commit = tpc_finish = tpc_vote = lambda s, txn: True

        dm = DM()
        txn = self._makeOne()
        txn.join(dm)
        self.assertEqual(txn._resources, [dm])
        txn.commit()
        self.assertEqual(txn._resources, [])

    def test_getBeforeCommitHooks_empty(self):
        txn = self._makeOne()
        self.assertEqual(list(txn.getBeforeCommitHooks()), [])

    def test_addBeforeCommitHook(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addBeforeCommitHook(_hook, ('one',), dict(uno=1))
        self.assertEqual(list(txn.getBeforeCommitHooks()),
                         [(_hook, ('one',), {'uno': 1})])

    def test_callBeforeCommitHook_w_error(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _calls = []

        def _hook(*args, **kw):
            _calls.append((args, kw))

        def _hook_err(*args, **kw):
            raise ValueError()

        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn.addBeforeCommitHook(_hook, ('one',), dict(uno=1))
        txn.addBeforeCommitHook(_hook_err, ('two',), dict(dos=2))
        txn.addBeforeCommitHook(_hook, ('three',), dict(tres=3))
        # only first hook gets called, and instead of logging the error,
        # the exception is raised
        self.assertRaises(ValueError, txn._callBeforeCommitHooks)
        self.assertEqual(_calls, [(('one',), {'uno': 1})])
        self.assertEqual(len(logger._log), 0)

    def test_addBeforeCommitHook_w_kws(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addBeforeCommitHook(_hook, ('one',))
        self.assertEqual(list(txn.getBeforeCommitHooks()),
                         [(_hook, ('one',), {})])

    def test_getAfterCommitHooks_empty(self):
        txn = self._makeOne()
        self.assertEqual(list(txn.getAfterCommitHooks()), [])

    def test_addAfterCommitHook(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addAfterCommitHook(_hook, ('one',), dict(uno=1))
        self.assertEqual(list(txn.getAfterCommitHooks()),
                         [(_hook, ('one',), {'uno': 1})])

    def test_addAfterCommitHook_wo_kws(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addAfterCommitHook(_hook, ('one',))
        self.assertEqual(list(txn.getAfterCommitHooks()),
                         [(_hook, ('one',), {})])

    def test_callAfterCommitHook_w_error(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked2 = []

        def _hook1(*args, **kw):
            raise ValueError()

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn.addAfterCommitHook(_hook1, ('one',))
        txn.addAfterCommitHook(_hook2, ('two',), dict(dos=2))
        txn._callAfterCommitHooks()
        # second hook gets called even if first raises
        self.assertEqual(_hooked2, [((True, 'two',), {'dos': 2})])
        self.assertEqual(len(logger._log), 1)
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(logger._log[0][1].startswith("Error in hook"))

    def test_callAfterCommitHook_w_abort(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked2 = []

        def _hook1(*args, **kw):
            raise ValueError()

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn.addAfterCommitHook(_hook1, ('one',))
        txn.addAfterCommitHook(_hook2, ('two',), dict(dos=2))
        txn._callAfterCommitHooks()
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(logger._log[0][1].startswith("Error in hook"))

    def test__commitResources_normal(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        resources = [Resource('bbb'), Resource('aaa')]
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn._resources.extend(resources)
        txn._commitResources()
        self.assertEqual(len(txn._voted), 2)
        for r in resources:
            self.assertTrue(r._b and r._c and r._v and r._f)
            self.assertFalse(r._a and r._x)
            self.assertIn(id(r), txn._voted)
        self.assertEqual(len(logger._log), 2)
        self.assertEqual(logger._log[0][0], 'debug')
        self.assertEqual(logger._log[0][1], 'commit Resource: aaa')
        self.assertEqual(logger._log[1][0], 'debug')
        self.assertEqual(logger._log[1][1], 'commit Resource: bbb')

    def test__commitResources_error_in_tpc_begin(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        resources = [Resource('bbb', 'tpc_begin'), Resource('aaa')]
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn._resources.extend(resources)
        self.assertRaises(ValueError, txn._commitResources)
        for r in resources:
            if r._key == 'aaa':
                self.assertTrue(r._b)
            else:
                self.assertFalse(r._b)
            self.assertFalse(r._c and r._v and r._f)
            self.assertTrue(r._a and r._x)
        self.assertEqual(len(logger._log), 0)

    def test__commitResources_error_in_afterCompletion(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class _Synchronizers:
            def __init__(self, res):
                self._res = res

            def map(self, func):
                for res in self._res:
                    func(res)
        resources = [Resource('bbb', 'tpc_begin'),
                     Resource('aaa', 'afterCompletion')]
        sync = _Synchronizers(resources)
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne(sync)
        logger._clear()
        txn._resources.extend(resources)
        self.assertRaises(ValueError, txn._commitResources)
        for r in resources:
            if r._key == 'aaa':
                self.assertTrue(r._b)
            else:
                self.assertFalse(r._b)
            self.assertFalse(r._c and r._v and r._f)
            self.assertTrue(r._a and r._x)
        self.assertEqual(len(logger._log), 0)
        self.assertTrue(resources[0]._after)
        self.assertFalse(resources[1]._after)

    def test__commitResources_error_in_commit(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        resources = [Resource('bbb', 'commit'), Resource('aaa')]
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn._resources.extend(resources)
        self.assertRaises(ValueError, txn._commitResources)
        for r in resources:
            self.assertTrue(r._b)
            if r._key == 'aaa':
                self.assertTrue(r._c)
            else:
                self.assertFalse(r._c)
            self.assertFalse(r._v and r._f)
            self.assertTrue(r._a and r._x)
        self.assertEqual(len(logger._log), 1)
        self.assertEqual(logger._log[0][0], 'debug')
        self.assertEqual(logger._log[0][1], 'commit Resource: aaa')

    def test__commitResources_error_in_tpc_vote(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        resources = [Resource('bbb', 'tpc_vote'), Resource('aaa')]
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn._resources.extend(resources)
        self.assertRaises(ValueError, txn._commitResources)
        self.assertEqual(len(txn._voted), 1)
        for r in resources:
            self.assertTrue(r._b and r._c)
            if r._key == 'aaa':
                self.assertIn(id(r), txn._voted)
                self.assertTrue(r._v)
                self.assertFalse(r._f)
                self.assertFalse(r._a)
                self.assertTrue(r._x)
            else:
                self.assertNotIn(id(r), txn._voted)
                self.assertFalse(r._v)
                self.assertFalse(r._f)
                self.assertTrue(r._a and r._x)
        self.assertEqual(len(logger._log), 2)
        self.assertEqual(logger._log[0][0], 'debug')
        self.assertEqual(logger._log[0][1], 'commit Resource: aaa')
        self.assertEqual(logger._log[1][0], 'debug')
        self.assertEqual(logger._log[1][1], 'commit Resource: bbb')

    def test__commitResources_error_in_tpc_finish(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        resources = [Resource('bbb', 'tpc_finish'), Resource('aaa')]
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn._resources.extend(resources)
        self.assertRaises(ValueError, txn._commitResources)
        for r in resources:
            self.assertTrue(r._b and r._c and r._v)
            self.assertIn(id(r), txn._voted)
            if r._key == 'aaa':
                self.assertTrue(r._f)
            else:
                self.assertFalse(r._f)
            self.assertFalse(r._a and r._x)  # no cleanup if tpc_finish raises
        self.assertEqual(len(logger._log), 3)
        self.assertEqual(logger._log[0][0], 'debug')
        self.assertEqual(logger._log[0][1], 'commit Resource: aaa')
        self.assertEqual(logger._log[1][0], 'debug')
        self.assertEqual(logger._log[1][1], 'commit Resource: bbb')
        self.assertEqual(logger._log[2][0], 'critical')
        self.assertTrue(logger._log[2][1].startswith(
                        'A storage error occurred'))

    def test_abort_wo_savepoints_wo_hooks_wo_synchronizers(self):
        from transaction import _transaction
        from transaction._transaction import Status
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class _Mgr:
            def __init__(self, txn):
                self._txn = txn

            def free(self, txn):
                assert txn is self._txn
                self._txn = None
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            logger._clear()
            mgr = txn._manager = _Mgr(txn)
            txn.abort()
        self.assertEqual(txn.status, Status.ACTIVE)
        self.assertIsNone(mgr._txn)
        self.assertEqual(logger._log[0][0], 'debug')
        self.assertEqual(logger._log[0][1], 'abort')

    def test_abort_w_savepoints(self):
        from weakref import WeakKeyDictionary

        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class _SP:
            def __init__(self, txn, index):
                self.transaction = txn
                self._index = index

            def __repr__(self):  # pragma: no cover
                return '_SP: %d' % self._index
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._savepoint2index = WeakKeyDictionary()
            holdme = []
            for i in range(10):
                sp = _SP(txn, i)
                holdme.append(sp)  # prevent gc
                txn._savepoint2index[sp] = i
            logger._clear()
            txn.abort()
        self.assertEqual(list(txn._savepoint2index), [])

    def test_abort_w_beforeCommitHooks(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked1, _hooked2 = [], []

        def _hook1(*args, **kw):
            raise AssertionError("Not called")

        def _hook2(*args, **kw):
            raise AssertionError("Not called")
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._before_commit.append((_hook1, ('one',), {'uno': 1}))
            txn._before_commit.append((_hook2, (), {}))
            logger._clear()
            txn.abort()
        self.assertEqual(_hooked1, [])
        self.assertEqual(_hooked2, [])
        # Hooks are not called but cleared on abort
        self.assertEqual(list(txn.getBeforeCommitHooks()), [])
        self.assertIsNone(txn._manager)

    def test_abort_w_synchronizers(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        test = self

        class _Synch:
            _before = _after = None

            def beforeCompletion(self, txn):
                self._before = txn
                txn.set_data(self, 42)
                test.assertIsNotNone(txn._manager)

            def afterCompletion(self, txn):
                self._after = txn
                # data is accessible afterCompletion,
                # but the transaction is not current anymore.
                test.assertEqual(42, txn.data(self))
                test.assertIsNone(txn._manager)

        class _BadSynch(_Synch):
            def afterCompletion(self, txn):
                _Synch.afterCompletion(self, txn)
                raise SystemExit

        # Ensure iteration order
        class Synchs:
            synchs = [_Synch(), _Synch(), _Synch(), _BadSynch()]

            def map(self, func):
                for s in self.synchs:
                    func(s)

        logger = DummyLogger()

        class Manager:
            txn = None

            def free(self, txn):
                test.assertIs(txn, self.txn)
                self.txn = None

        manager = Manager()
        synchs = Synchs()

        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne(synchronizers=synchs, manager=manager)
            manager.txn = txn
            logger._clear()
            with self.assertRaises(SystemExit):
                txn.abort()

        for synch in synchs.synchs:
            self.assertIs(synch._before, txn)
            self.assertIs(synch._after, txn)

        # And everything was cleaned up despite raising the bad
        # exception
        self.assertIsNone(txn._manager)
        self.assertIsNot(txn._synchronizers, synchs)
        self.assertIsNone(manager.txn)

    def test_abort_w_afterCommitHooks(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked1, _hooked2 = [], []

        def _hook1(*args, **kw):
            raise AssertionError("Not called")

        def _hook2(*args, **kw):
            raise AssertionError("Not called")
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._after_commit.append((_hook1, ('one',), {'uno': 1}))
            txn._after_commit.append((_hook2, (), {}))
            logger._clear()
            txn.abort()
        # Hooks are not called but cleared on abort
        self.assertEqual(_hooked1, [])
        self.assertEqual(_hooked2, [])
        self.assertEqual(list(txn.getAfterCommitHooks()), [])
        self.assertEqual(txn._resources, [])
        self.assertIsNone(txn._manager)

    def test_abort_error_w_afterCommitHooks(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class BrokenResource:
            def sortKey(self):
                raise AssertionError("Not called")

            def abort(self, txn):
                raise ValueError('test')
        broken = BrokenResource()
        aaa = Resource('aaa')
        broken2 = BrokenResource()
        _hooked1, _hooked2 = [], []

        def _hook1(*args, **kw):
            raise AssertionError("Not called")

        def _hook2(*args, **kw):
            raise AssertionError("Not called")
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
            txn._after_commit.append((_hook1, ('one',), {'uno': 1}))
            txn._after_commit.append((_hook2, (), {}))
            txn._resources.append(aaa)
            txn._resources.append(broken)
            txn._resources.append(broken2)
            logger._clear()
            self.assertRaises(ValueError, txn.abort)
        # Hooks are not called but cleared on abort
        self.assertEqual(_hooked1, [])
        self.assertEqual(_hooked2, [])
        self.assertEqual(list(txn.getAfterCommitHooks()), [])
        self.assertTrue(aaa._a)
        self.assertFalse(aaa._x)
        self.assertIsNone(txn._manager)

    def test_abort_error_w_synchronizers(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        from transaction.weakset import WeakSet

        class _Synch:
            _before = _after = False

            def beforeCompletion(self, txn):
                self._before = txn

            def afterCompletion(self, txn):
                self._after = txn
        synchs = [_Synch(), _Synch(), _Synch()]
        ws = WeakSet()
        for synch in synchs:
            ws.add(synch)

        class BrokenResource:
            def sortKey(self):
                raise AssertionError("Should not be called")

            def abort(self, txn):
                raise ValueError('test')
        broken = BrokenResource()
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            t = self._makeOne(synchronizers=ws)
            logger._clear()
            t._resources.append(broken)
            self.assertRaises(ValueError, t.abort)
        for synch in synchs:
            self.assertIs(synch._before, t)
            self.assertIs(synch._after, t)  # called in _cleanup
        self.assertIsNot(t._synchronizers, ws)

    def test_abort_synchronizer_error_w_resources(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey

        class _Synch:
            _before = _after = False

            def beforeCompletion(self, txn):
                self._before = txn

            def afterCompletion(self, txn):
                self._after = txn

        class _BadSynch(_Synch):
            def beforeCompletion(self, txn):
                _Synch.beforeCompletion(self, txn)
                raise SystemExit

        # Ensure iteration order
        class Synchs:
            synchs = [_Synch(), _Synch(), _Synch(), _BadSynch()]

            def map(self, func):
                for s in self.synchs:
                    func(s)

        resource = Resource('a')
        logger = DummyLogger()
        synchs = Synchs()
        with Monkey(_transaction, _LOGGER=logger):
            t = self._makeOne(synchronizers=synchs)
            logger._clear()
            t._resources.append(resource)
            with self.assertRaises(SystemExit):
                t.abort()

        for synch in synchs.synchs:
            self.assertIs(synch._before, t)
            self.assertIs(synch._after, t)  # called in _cleanup
        self.assertIsNot(t._synchronizers, synchs)
        self.assertTrue(resource._a)

    def test_abort_clears_resources(self):
        class DM:
            def abort(self, txn):
                return True

        dm = DM()
        txn = self._makeOne()
        txn.join(dm)
        self.assertEqual(txn._resources, [dm])
        txn.abort()
        self.assertEqual(txn._resources, [])

    def test_getBeforeAbortHooks_empty(self):
        txn = self._makeOne()
        self.assertEqual(list(txn.getBeforeAbortHooks()), [])

    def test_addBeforeAbortHook(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addBeforeAbortHook(_hook, ('one',), dict(uno=1))
        self.assertEqual(list(txn.getBeforeAbortHooks()),
                         [(_hook, ('one',), {'uno': 1})])

    def test_addBeforeAbortHook_w_kws(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addBeforeAbortHook(_hook, ('one',))
        self.assertEqual(list(txn.getBeforeAbortHooks()),
                         [(_hook, ('one',), {})])

    def test_getAfterAbortHooks_empty(self):
        txn = self._makeOne()
        self.assertEqual(list(txn.getAfterAbortHooks()), [])

    def test_addAfterAbortHook(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addAfterAbortHook(_hook, ('one',), dict(uno=1))
        self.assertEqual(list(txn.getAfterAbortHooks()),
                         [(_hook, ('one',), {'uno': 1})])

    def test_addAfterAbortHook_wo_kws(self):
        def _hook(*args, **kw):
            raise AssertionError("Not called")
        txn = self._makeOne()
        txn.addAfterAbortHook(_hook, ('one',))
        self.assertEqual(list(txn.getAfterAbortHooks()),
                         [(_hook, ('one',), {})])

    def test_callBeforeAbortHook_w_error(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked2 = []

        def _hook1(*args, **kw):
            raise ValueError()

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn.addBeforeAbortHook(_hook1, ('one',))
        txn.addBeforeAbortHook(_hook2, ('two',), dict(dos=2))
        txn._callBeforeAbortHooks()
        # second hook gets called even if first raises
        self.assertEqual(_hooked2, [(('two',), {'dos': 2})])
        self.assertEqual(len(logger._log), 1)
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(logger._log[0][1].startswith("Error in hook"))

    def test_callBeforeAbortHook_w_abort(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked2 = []

        def _hook1(*args, **kw):
            raise ValueError()

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        txn.addBeforeAbortHook(_hook1, ('one',))
        txn.addBeforeAbortHook(_hook2, ('two',), dict(dos=2))
        txn._callBeforeAbortHooks()
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(logger._log[0][1].startswith("Error in hook"))

    def test_callAfterAbortHook_w_abort_error(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked2 = []

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        r = Resource("r", "abort")
        txn.join(r)
        txn.addAfterAbortHook(_hook2, ('two',), dict(dos=2))
        txn._callAfterAbortHooks()
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(
            logger._log[0][1].startswith("Error in abort() on manager"))

    def test_callAfterAbortHook_w_error_w_abort_error(self):
        from transaction import _transaction
        from transaction.tests.common import DummyLogger
        from transaction.tests.common import Monkey
        _hooked2 = []

        def _hook1(*args, **kw):
            raise ValueError()

        def _hook2(*args, **kw):
            _hooked2.append((args, kw))  # pragma: no cover
        logger = DummyLogger()
        with Monkey(_transaction, _LOGGER=logger):
            txn = self._makeOne()
        logger._clear()
        r = Resource("r", "abort")
        txn.join(r)
        txn.addAfterAbortHook(_hook1, ('one',), dict(dos=1))
        txn.addAfterAbortHook(_hook2, ('two',), dict(dos=2))
        with self.assertRaises(ValueError):
            txn._callAfterAbortHooks()
        self.assertEqual(logger._log[0][0], 'error')
        self.assertTrue(
            logger._log[0][1].startswith("Error in abort() on manager"))

    def test_abort_w_abortHooks(self):
        comm = []
        txn = self._makeOne()

        def bah():
            comm.append("before")

        def aah():
            comm.append("after")
        txn.addAfterAbortHook(aah)
        txn.addBeforeAbortHook(bah)
        txn.abort()
        self.assertEqual(comm, ["before", "after"])
        self.assertEqual(list(txn.getBeforeAbortHooks()), [])
        self.assertEqual(list(txn.getAfterAbortHooks()), [])

    def test_commit_w_abortHooks(self):
        comm = []
        txn = self._makeOne()

        def bah():
            comm.append("before")  # pragma: no cover

        def aah():
            comm.append("after")  # pragma: no cover
        txn.addAfterAbortHook(aah)
        txn.addBeforeAbortHook(bah)
        txn.commit()
        self.assertEqual(comm, [])  # not called
        # but cleared
        self.assertEqual(list(txn.getBeforeAbortHooks()), [])
        self.assertEqual(list(txn.getAfterAbortHooks()), [])

    def test_commit_w_error_w_abortHooks(self):
        comm = []
        txn = self._makeOne()

        def bah():
            comm.append("before")  # pragma: no cover

        def aah():
            comm.append("after")  # pragma: no cover
        txn.addAfterAbortHook(aah)
        txn.addBeforeAbortHook(bah)
        r = Resource("aaa", "tpc_vote")
        txn.join(r)
        with self.assertRaises(ValueError):
            txn.commit()
        self.assertEqual(comm, [])  # not called
        # not cleared
        self.assertEqual(list(txn.getBeforeAbortHooks()), [(bah, (), {})])
        self.assertEqual(list(txn.getAfterAbortHooks()), [(aah, (), {})])

    def test_note(self):
        txn = self._makeOne()
        try:
            txn.note('This is a note.')
            self.assertEqual(txn.description, 'This is a note.')
            txn.note('Another.')
            self.assertEqual(txn.description, 'This is a note.\nAnother.')
        finally:
            txn.abort()

    def test_note_bytes(self):
        txn = self._makeOne()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            txn.note(b'haha')
            self.assertNonTextDeprecationWarning(w)
            self.assertEqual(txn.description, 'haha')

    def test_note_None(self):
        txn = self._makeOne()
        self.assertEqual('', txn.description)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            txn.note(None)
            self.assertFalse(w)
        self.assertEqual(txn.description, '')

    def test_note_42(self):
        txn = self._makeOne()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            txn.note(42)
            self.assertNonTextDeprecationWarning(w)
            self.assertEqual(txn.description, '42')

    def assertNonTextDeprecationWarning(self, w):
        [w] = w
        self.assertEqual(
            (DeprecationWarning, "Expected text",
             os.path.splitext(__file__)[0]),
            (w.category, str(w.message), os.path.splitext(w.filename)[0]),
        )

    def test_description_bytes(self):
        txn = self._makeOne()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            txn.description = b'haha'
            self.assertNonTextDeprecationWarning(w)
            self.assertEqual(txn.description, 'haha')

    def test_description_42(self):
        txn = self._makeOne()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            txn.description = 42
            self.assertNonTextDeprecationWarning(w)
            self.assertEqual(txn.description, '42')

    def test_description_None(self):
        txn = self._makeOne()
        self.assertEqual('', txn.description)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            txn.description = None
            self.assertFalse(w)
        self.assertEqual(txn.description, '')

    def test_setUser_default_path(self):
        txn = self._makeOne()
        txn.setUser('phreddy')
        self.assertEqual(txn.user, '/ phreddy')

    def test_setUser_explicit_path(self):
        txn = self._makeOne()
        txn.setUser('phreddy', '/bedrock')
        self.assertEqual(txn.user, '/bedrock phreddy')

    def test_user_w_none(self):
        txn = self._makeOne()
        txn.user = 'phreddy'
        with self.assertRaises(ValueError):
            txn.user = None  # raises
        self.assertEqual(txn.user, 'phreddy')

    def _test_user_non_text(self, user, path, expect, both=False):
        txn = self._makeOne()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            if path:
                txn.setUser(user, path)
            else:
                if path is None:
                    txn.setUser(user)
                else:
                    txn.user = user

            if both:
                self.assertNonTextDeprecationWarning(w[:1])
                self.assertNonTextDeprecationWarning(w[1:])
            else:
                self.assertNonTextDeprecationWarning(w)

        self.assertEqual(expect, txn.user)

    def test_user_non_text(self, user=b'phreddy', path=b'/bedrock',
                           expect="/bedrock phreddy", both=True):
        self._test_user_non_text(b'phreddy', b'/bedrock',
                                 "/bedrock phreddy", True)
        self._test_user_non_text(b'phreddy', None, '/ phreddy')
        self._test_user_non_text(b'phreddy', False, 'phreddy')
        self._test_user_non_text(b'phreddy', '/bedrock', '/bedrock phreddy')
        self._test_user_non_text('phreddy', b'/bedrock', '/bedrock phreddy')
        self._test_user_non_text('phreddy', 2, '2 phreddy')
        self._test_user_non_text(1, '/bedrock', '/bedrock 1')
        self._test_user_non_text(1, 2, '2 1', True)

    def test_setExtendedInfo_single(self):
        txn = self._makeOne()
        txn.setExtendedInfo('frob', 'qux')
        self.assertEqual(txn.extension, {'frob': 'qux'})
        self.assertIs(txn._extension, txn._extension)  # legacy

    def test_setExtendedInfo_multiple(self):
        txn = self._makeOne()
        txn.setExtendedInfo('frob', 'qux')
        txn.setExtendedInfo('baz', 'spam')
        txn.setExtendedInfo('frob', 'quxxxx')
        self.assertEqual(txn._extension, {'frob': 'quxxxx', 'baz': 'spam'})
        self.assertIs(txn._extension, txn._extension)  # legacy

    def test__extension_settable(self):
        # Because ZEO sets it. I'll fix ZEO, but maybe something else will
        # break
        txn = self._makeOne()
        txn._extension = dict(baz='spam')
        txn.setExtendedInfo('frob', 'qux')
        self.assertEqual(txn.extension, {'frob': 'qux', 'baz': 'spam'})

    def test_data(self):
        txn = self._makeOne()

        # Can't get data that wasn't set:
        with self.assertRaises(KeyError) as c:
            txn.data(self)
        self.assertEqual(c.exception.args, (self,))

        data = dict(a=1)
        txn.set_data(self, data)
        self.assertEqual(txn.data(self), data)

        # Can't get something we haven't stored.
        with self.assertRaises(KeyError) as c:
            txn.data(data)
        self.assertEqual(c.exception.args, (data,))

        # When the transaction ends, data are discarded:
        txn.commit()
        with self.assertRaises(KeyError) as c:
            txn.data(self)
        self.assertEqual(c.exception.args, (self,))

    def test_isRetryableError_w_transient_error(self):
        from transaction._manager import TransactionManager
        from transaction.interfaces import TransientError
        txn = self._makeOne(manager=TransactionManager())
        txn._manager._txn = txn
        self.assertTrue(txn.isRetryableError(TransientError()))

    def test_isRetryableError_w_transient_subclass(self):
        from transaction._manager import TransactionManager
        from transaction.interfaces import TransientError

        class _Derived(TransientError):
            pass
        txn = self._makeOne(manager=TransactionManager())
        txn._manager._txn = txn
        self.assertTrue(txn.isRetryableError(_Derived()))

    def test_isRetryableError_w_normal_exception_no_resources(self):
        from transaction._manager import TransactionManager
        txn = self._makeOne(manager=TransactionManager())
        txn._manager._txn = txn
        self.assertFalse(txn.isRetryableError(Exception()))

    def test_isRetryableError_w_normal_exception_w_resource_voting_yes(self):
        from transaction._manager import TransactionManager

        class _Resource:
            def should_retry(self, err):
                return True
        txn = self._makeOne(manager=TransactionManager())
        txn._manager._txn = txn
        txn._resources.append(_Resource())
        self.assertTrue(txn.isRetryableError(Exception()))

    def test_isRetryableError_w_multiple(self):
        from transaction._manager import TransactionManager

        class _Resource:
            _should = True

            def should_retry(self, err):
                return self._should
        txn = self._makeOne(manager=TransactionManager())
        txn._manager._txn = txn
        res1 = _Resource()
        res1._should = False
        res2 = _Resource()
        txn._resources.append(res1)
        txn._resources.append(res2)
        self.assertTrue(txn.isRetryableError(Exception()))


class Test_rm_key(unittest.TestCase):

    def _callFUT(self, oid):
        from transaction._transaction import rm_key
        return rm_key(oid)

    def test_miss(self):
        self.assertIsNone(self._callFUT(object()))

    def test_hit(self):
        self.assertEqual(self._callFUT(Resource('zzz')), 'zzz')


class SavepointTests(unittest.TestCase):

    def _getTargetClass(self):
        from transaction._transaction import Savepoint
        return Savepoint

    def _makeOne(self, txn, optimistic, *resources):
        return self._getTargetClass()(txn, optimistic, *resources)

    def test_ctor_w_savepoint_oblivious_resource_non_optimistic(self):
        txn = object()
        resource = object()
        self.assertRaises(TypeError, self._makeOne, txn, False, resource)

    def test_ctor_w_savepoint_oblivious_resource_optimistic(self):
        from transaction._transaction import NoRollbackSavepoint
        txn = object()
        resource = object()
        sp = self._makeOne(txn, True, resource)
        self.assertEqual(len(sp._savepoints), 1)
        self.assertIsInstance(sp._savepoints[0], NoRollbackSavepoint)
        self.assertIs(sp._savepoints[0].datamanager, resource)

    def test_ctor_w_savepoint_aware_resources(self):
        class _Aware:
            def savepoint(self):
                return self
        txn = object()
        one = _Aware()
        another = _Aware()
        sp = self._makeOne(txn, True, one, another)
        self.assertEqual(len(sp._savepoints), 2)
        self.assertIsInstance(sp._savepoints[0], _Aware)
        self.assertIs(sp._savepoints[0], one)
        self.assertIsInstance(sp._savepoints[1], _Aware)
        self.assertIs(sp._savepoints[1], another)

    def test_valid_wo_transacction(self):
        sp = self._makeOne(None, True, object())
        self.assertFalse(sp.valid)

    def test_valid_w_transacction(self):
        sp = self._makeOne(object(), True, object())
        self.assertTrue(sp.valid)

    def test_rollback_w_txn_None(self):
        from transaction.interfaces import InvalidSavepointRollbackError
        txn = None

        class _Aware:
            def savepoint(self):
                return self
        resource = _Aware()
        sp = self._makeOne(txn, False, resource)
        self.assertRaises(InvalidSavepointRollbackError, sp.rollback)

    def test_rollback_w_sp_error(self):
        class _TXN:
            _sarce = False
            _raia = None

            def _saveAndRaiseCommitishError(self):
                import sys

                self._sarce = True
                _, v, tb = sys.exc_info()
                raise v.with_traceback(tb)

            def _remove_and_invalidate_after(self, sp):
                self._raia = sp

        class _Broken:
            def rollback(self):
                raise ValueError()
        _broken = _Broken()

        class _GonnaRaise:
            def savepoint(self):
                return _broken
        txn = _TXN()
        resource = _GonnaRaise()
        sp = self._makeOne(txn, False, resource)
        self.assertRaises(ValueError, sp.rollback)
        self.assertIs(txn._raia, sp)
        self.assertTrue(txn._sarce)


class AbortSavepointTests(unittest.TestCase):

    def _getTargetClass(self):
        from transaction._transaction import AbortSavepoint
        return AbortSavepoint

    def _makeOne(self, datamanager, transaction):
        return self._getTargetClass()(datamanager, transaction)

    def test_ctor(self):
        dm = object()
        txn = object()
        asp = self._makeOne(dm, txn)
        self.assertIs(asp.datamanager, dm)
        self.assertIs(asp.transaction, txn)

    def test_rollback(self):
        class _DM:
            _aborted = None

            def abort(self, txn):
                self._aborted = txn

        class _TXN:
            _unjoined = None

            def _unjoin(self, datamanager):
                self._unjoin = datamanager
        dm = _DM()
        txn = _TXN()
        asp = self._makeOne(dm, txn)
        asp.rollback()
        self.assertIs(dm._aborted, txn)
        self.assertIs(txn._unjoin, dm)


class NoRollbackSavepointTests(unittest.TestCase):

    def _getTargetClass(self):
        from transaction._transaction import NoRollbackSavepoint
        return NoRollbackSavepoint

    def _makeOne(self, datamanager):
        return self._getTargetClass()(datamanager)

    def test_ctor(self):
        dm = object()
        nrsp = self._makeOne(dm)
        self.assertIs(nrsp.datamanager, dm)

    def test_rollback(self):
        dm = object()
        nrsp = self._makeOne(dm)
        self.assertRaises(TypeError, nrsp.rollback)


class MiscellaneousTests(unittest.TestCase):

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

            def beforeCompletion(self, txn):
                raise AssertionError("Not called")

            def afterCompletion(self, txn):
                raise AssertionError("Not called")

            def newTransaction(self, txn):
                self.log.append('{} {}'.format(self.label, 'new'))

        def run_in_thread(f):
            txn = threading.Thread(target=f)
            txn.start()
            txn.join()

        sync = Sync(1)

        @run_in_thread
        def _():
            transaction.manager.registerSynch(sync)
            transaction.manager.begin()
            dm['a'] = 1
        self.assertEqual(sync.log, ['1 new'])

        @run_in_thread
        def _2():
            transaction.abort()  # should do nothing.
        self.assertEqual(sync.log, ['1 new'])
        self.assertEqual(list(dm.keys()), ['a'])

        dm = SPS.SampleSavepointDataManager()
        self.assertEqual(list(dm.keys()), [])

        @run_in_thread
        def _3():
            dm['a'] = 1
        self.assertEqual(sync.log, ['1 new'])

        transaction.abort()  # should do nothing
        self.assertEqual(list(dm.keys()), ['a'])

    def test_gh5(self):
        from transaction import _transaction

        buffer = _transaction._makeTracebackBuffer()

        s = 'ąčę'
        buffer.write(s)

        buffer.seek(0)
        self.assertEqual(buffer.read(), s)


class Resource:
    _b = _c = _v = _f = _a = _x = _after = False

    def __init__(self, key, error=None):
        self._key = key
        self._error = error

    def __repr__(self):
        return 'Resource: %s' % self._key

    def sortKey(self):
        return self._key

    def tpc_begin(self, txn):
        if self._error == 'tpc_begin':
            raise ValueError()
        self._b = True

    def commit(self, txn):
        if self._error == 'commit':
            raise ValueError()
        self._c = True

    def tpc_vote(self, txn):
        if self._error == 'tpc_vote':
            raise ValueError()
        self._v = True

    def tpc_finish(self, txn):
        if self._error == 'tpc_finish':
            raise ValueError()
        self._f = True

    def abort(self, txn):
        if self._error == 'abort':
            raise AssertionError("Not called in that state")
        self._a = True

    def tpc_abort(self, txn):
        if self._error == 'tpc_abort':
            raise AssertionError("Not called in that state")
        self._x = True

    def afterCompletion(self, txn):
        if self._error == 'afterCompletion':
            raise ValueError()
        self._after = True
