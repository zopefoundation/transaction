##############################################################################
#
# Copyright (c) 2004 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Sample objects for use in tests

"""


class DataManager(object):
    """ Sample data manager.

    Used by the 'datamanager' chapter in the Sphinx docs.
    """
    def __init__(self):
        self.state = 0
        self.sp = 0
        self.transaction = None
        self.delta = 0
        self.txn_state = None
        self.begun = False

    def _check_state(self, *ok_states):
        if self.txn_state not in ok_states:
            raise ValueError("txn in state %r but expected one of %r" %
                             (self.txn_state, ok_states))

    def _checkTransaction(self, transaction):
        if (transaction is not self.transaction
                and self.transaction is not None):
            raise TypeError("Transaction missmatch",
                            transaction, self.transaction)

    def inc(self, n=1):
        self.delta += n

    def tpc_begin(self, transaction):
        self._checkTransaction(transaction)
        self._check_state(None)
        self.transaction = transaction
        self.txn_state = 'tpc_begin'
        self.begun = True

    def tpc_vote(self, transaction):
        self._checkTransaction(transaction)
        self._check_state('tpc_begin')
        self.state += self.delta
        self.txn_state = 'tpc_vote'

    def tpc_finish(self, transaction):
        self._checkTransaction(transaction)
        self._check_state('tpc_vote')
        self.delta = 0
        self.transaction = None
        self.txn_state = None

    def tpc_abort(self, transaction):
        self._checkTransaction(transaction)
        if self.transaction is not None:
            self.transaction = None

        if self.txn_state == 'tpc_vote':
            self.state -= self.delta

        self.txn_state = None
        self.delta = 0

    def savepoint(self, transaction):
        if self.txn_state is not None:
            raise AssertionError("Can't get savepoint during two-phase commit")
        self._checkTransaction(transaction)
        self.transaction = transaction
        self.sp += 1
        return SavePoint(self)

    def abort(self, transaction):
        self._checkTransaction(transaction)
        if self.transaction is not None:
            self.transaction = None

        if self.begun:
            self.state -= self.delta
            self.begun = False

        self.delta = 0

    def commit(self, transaction):
        if not self.begun:
            raise TypeError('Not prepared to commit')
        self._checkTransaction(transaction)
        self.transaction = None


class SavePoint(object):

    def __init__(self, rm):
        self.rm = rm
        self.sp = rm.sp
        self.delta = rm.delta
        self.transaction = rm.transaction

    def rollback(self):
        if self.transaction is not self.rm.transaction:
            raise TypeError("Attempt to rollback stale rollback")
        if self.rm.sp < self.sp:
            raise TypeError("Attempt to roll back to invalid save point",
                            self.sp, self.rm.sp)
        self.rm.sp = self.sp
        self.rm.delta = self.delta

    def discard(self):
        "Does nothing."
