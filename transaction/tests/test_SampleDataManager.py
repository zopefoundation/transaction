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

Used by the 'datamanaber' chapter in the Sphinx docs.
"""

class DataManager(object):
    """Sample data manager
    """
    def __init__(self):
        self.state = 0
        self.sp = 0
        self.transaction = None
        self.delta = 0
        self.prepared = False

    def inc(self, n=1):
        self.delta += n

    def prepare(self, transaction):
        if self.prepared:
            raise TypeError('Already prepared')
        self._checkTransaction(transaction)
        self.prepared = True
        self.transaction = transaction
        self.state += self.delta

    def _checkTransaction(self, transaction):
        if (transaction is not self.transaction
            and self.transaction is not None):
            raise TypeError("Transaction missmatch",
                            transaction, self.transaction)

    def abort(self, transaction):
        self._checkTransaction(transaction)
        if self.transaction is not None:
            self.transaction = None

        if self.prepared:
            self.state -= self.delta
            self.prepared = False

        self.delta = 0

    def commit(self, transaction):
        if not self.prepared:
            raise TypeError('Not prepared to commit')
        self._checkTransaction(transaction)
        self.delta = 0
        self.transaction = None
        self.prepared = False

    def savepoint(self, transaction):
        if self.prepared:
            raise TypeError("Can't get savepoint during two-phase commit")
        self._checkTransaction(transaction)
        self.transaction = transaction
        self.sp += 1
        return Rollback(self)


class Rollback(object):

    def __init__(self, dm):
        self.dm = dm
        self.sp = dm.sp
        self.delta = dm.delta
        self.transaction = dm.transaction

    def rollback(self):
        if self.transaction is not self.dm.transaction:
            raise TypeError("Attempt to rollback stale rollback")
        if self.dm.sp < self.sp:
            raise TypeError("Attempt to roll back to invalid save point",
                            self.sp, self.dm.sp)
        self.dm.sp = self.sp
        self.dm.delta = self.delta
