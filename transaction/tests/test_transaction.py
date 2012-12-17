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


class DummyFile(object):
    def __init__(self):
        self._lines = []
    def write(self, text):
        self._lines.append(text)
    def writelines(self, lines):
        self._lines.extend(lines)

class Monkey(object):
    # context-manager for replacing module names in the scope of a test.
    def __init__(self, module, **kw):
        self.module = module
        self.to_restore = dict([(key, getattr(module, key)) for key in kw])
        for key, value in kw.items():
            setattr(module, key, value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for key, value in self.to_restore.items():
            setattr(self.module, key, value)

def assertRaisesEx(e_type, checked, *args, **kw):
    try:
        checked(*args, **kw)
    except e_type as e:
        return e
    assert(0, "Didn't raise: %s" % e_type.__name__)

def positive_id(obj):
    """Return id(obj) as a non-negative integer."""
    import struct
    _ADDRESS_MASK = 256 ** struct.calcsize('P')

    result = id(obj)
    if result < 0:
        result += _ADDRESS_MASK
        assert result > 0
    return result

class TransactionManagerTests(unittest.TestCase):

    def _makeDM(self):
        from transaction import TransactionManager
        mgr = TransactionManager()
        sub1 = DataObject(mgr)
        sub2 = DataObject(mgr)
        sub3 = DataObject(mgr)
        nosub1 = DataObject(mgr, nost=1)
        return mgr, sub1, sub2, sub3, nosub1

    # basic tests with two sub trans jars
    # really we only need one, so tests for
    # sub1 should identical to tests for sub2
    def testTransactionCommit(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        sub1.modify()
        sub2.modify()

        mgr.commit()

        assert sub1._p_jar.ccommit_sub == 0
        assert sub1._p_jar.ctpc_finish == 1

    def testTransactionAbort(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        sub1.modify()
        sub2.modify()

        mgr.abort()

        assert sub2._p_jar.cabort == 1

    def testTransactionNote(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        t = mgr.get()

        t.note('This is a note.')
        self.assertEqual(t.description, 'This is a note.')
        t.note('Another.')
        self.assertEqual(t.description, 'This is a note.\nAnother.')

        t.abort()


    # repeat adding in a nonsub trans jars

    def testNSJTransactionCommit(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        nosub1.modify()

        mgr.commit()

        assert nosub1._p_jar.ctpc_finish == 1

    def testNSJTransactionAbort(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        nosub1.modify()

        mgr.abort()

        assert nosub1._p_jar.ctpc_finish == 0
        assert nosub1._p_jar.cabort == 1


    ### Failure Mode Tests
    #
    # ok now we do some more interesting
    # tests that check the implementations
    # error handling by throwing errors from
    # various jar methods
    ###

    # first the recoverable errors

    def testExceptionInAbort(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        sub1._p_jar = BasicJar(errors='abort')

        nosub1.modify()
        sub1.modify(nojar=1)
        sub2.modify()

        try:
            mgr.abort()
        except TestTxnException: pass

        assert nosub1._p_jar.cabort == 1
        assert sub2._p_jar.cabort == 1

    def testExceptionInCommit(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        sub1._p_jar = BasicJar(errors='commit')

        nosub1.modify()
        sub1.modify(nojar=1)

        try:
            mgr.commit()
        except TestTxnException: pass

        assert nosub1._p_jar.ctpc_finish == 0
        assert nosub1._p_jar.ccommit == 1
        assert nosub1._p_jar.ctpc_abort == 1

    def testExceptionInTpcVote(self):

        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        sub1._p_jar = BasicJar(errors='tpc_vote')

        nosub1.modify()
        sub1.modify(nojar=1)

        try:
            mgr.commit()
        except TestTxnException: pass

        assert nosub1._p_jar.ctpc_finish == 0
        assert nosub1._p_jar.ccommit == 1
        assert nosub1._p_jar.ctpc_abort == 1
        assert sub1._p_jar.ctpc_abort == 1

    def testExceptionInTpcBegin(self):
        # ok this test reveals a bug in the TM.py
        # as the nosub tpc_abort there is ignored.

        # nosub calling method tpc_begin
        # nosub calling method commit
        # sub calling method tpc_begin
        # sub calling method abort
        # sub calling method tpc_abort
        # nosub calling method tpc_abort
        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        sub1._p_jar = BasicJar(errors='tpc_begin')

        nosub1.modify()
        sub1.modify(nojar=1)

        try:
            mgr.commit()
        except TestTxnException:
            pass

        assert nosub1._p_jar.ctpc_abort == 1
        assert sub1._p_jar.ctpc_abort == 1

    def testExceptionInTpcAbort(self):
        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
        sub1._p_jar = BasicJar(errors=('tpc_abort', 'tpc_vote'))

        nosub1.modify()
        sub1.modify(nojar=1)

        try:
            mgr.commit()
        except TestTxnException:
            pass

        assert nosub1._p_jar.ctpc_abort == 1

    # last test, check the hosing mechanism

##    def testHoserStoppage(self):
##        # It's hard to test the "hosed" state of the database, where
##        # hosed means that a failure occurred in the second phase of
##        # the two phase commit.  It's hard because the database can
##        # recover from such an error if it occurs during the very first
##        # tpc_finish() call of the second phase.

##        mgr, sub1, sub2, sub3, nosub1 = self._makeDM()
##        for obj in sub1, sub2:
##            j = HoserJar(errors='tpc_finish')
##            j.reset()
##            obj._p_jar = j
##            obj.modify(nojar=1)

##        try:
##            transaction.commit()
##        except TestTxnException:
##            pass

##        self.assert_(Transaction.hosed)

##        sub2.modify()

##        try:
##            transaction.commit()
##        except Transaction.POSException.TransactionError:
##            pass
##        else:
##            self.fail("Hosed Application didn't stop commits")


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
        from transaction.tests.SampleDataManager import DataManager
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
        def first():
            dm['a'] = 1
        self.assertEqual(sync.log, ['1 new'])

        transaction.abort() # should do nothing
        self.assertEqual(list(dm.keys()), ['a'])


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

class BasicJar:

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
        if self.tracing:
            print('%s calling method %s'%(str(self.tracing),method))

        if method in self.errors:
            raise TestTxnException("error %s" % method)

    ## basic jar txn interface

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

class HoserJar(BasicJar):

    # The HoserJars coordinate their actions via the class variable
    # committed.  The check() method will only raise its exception
    # if committed > 0.

    committed = 0

    def reset(self):
        # Calling reset() on any instance will reset the class variable.
        HoserJar.committed = 0

    def check(self, method):
        if HoserJar.committed > 0:
            BasicJar.check(self, method)

    def tpc_finish(self, *args):
        self.check('tpc_finish')
        self.ctpc_finish += 1
        HoserJar.committed += 1


def hook():
    pass


def test_suite():
    from doctest import DocTestSuite
    suite = unittest.TestSuite((
        DocTestSuite(),
        unittest.makeSuite(TransactionManagerTests),
        unittest.makeSuite(Test_oid_repr),
        unittest.makeSuite(MiscellaneousTests),
        ))

    return suite

# additional_tests is for setuptools "setup.py test" support
additional_tests = test_suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
