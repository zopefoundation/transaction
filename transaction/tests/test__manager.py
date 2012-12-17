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
import unittest


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


def positive_id(obj):
    """Return id(obj) as a non-negative integer."""
    import struct
    _ADDRESS_MASK = 256 ** struct.calcsize('P')

    result = id(obj)
    if result < 0:
        result += _ADDRESS_MASK
        assert result > 0
    return result


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TransactionManagerTests),
    ))
