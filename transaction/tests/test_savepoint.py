##############################################################################
#
# Copyright (c) 2004 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Tests of savepoint feature

$Id$
"""
import unittest
from zope.testing import doctest


def testRollbackRollsbackDataManagersThatJoinedLater():
    """

A savepoint needs to not just rollback it's savepoints, but needs to
rollback savepoints for data managers that joined savepoints after the
savepoint:

    >>> import transaction
    >>> from transaction.tests import savepointsample
    >>> dm = savepointsample.SampleSavepointDataManager()
    >>> dm['name'] = 'bob'
    >>> sp1 = transaction.savepoint()
    >>> dm['job'] = 'geek'
    >>> sp2 = transaction.savepoint()
    >>> dm['salary'] = 'fun'    
    >>> dm2 = savepointsample.SampleSavepointDataManager()
    >>> dm2['name'] = 'sally'

    >>> 'name' in dm
    True
    >>> 'job' in dm
    True
    >>> 'salary' in dm
    True
    >>> 'name' in dm2
    True

    >>> sp1.rollback()

    >>> 'name' in dm
    True
    >>> 'job' in dm
    False
    >>> 'salary' in dm
    False
    >>> 'name' in dm2
    False

"""

def test_suite():
    return unittest.TestSuite((
        doctest.DocFileSuite('savepoint.txt'),
        doctest.DocTestSuite(),
        ))

# additional_tests is for setuptools "setup.py test" support
additional_tests = test_suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

