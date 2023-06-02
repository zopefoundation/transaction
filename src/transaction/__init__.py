############################################################################
#
# Copyright (c) 2001, 2002, 2004 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
############################################################################
"""``transaction`` module: Exported transaction functions.

"""

# isort: off

#: Default implementation of `~ITransaction`
from transaction._transaction import Transaction  # noqa: F401 unused import
#: Default implementation of `~ISavepoint`
from transaction._transaction import Savepoint  # noqa: F401 unused import
#: A single-threaded `~ITransactionManager`
from transaction._manager import TransactionManager  # noqa: F401 unused import
#: A thread-safe `~ITransactionManager`
from transaction._manager import ThreadTransactionManager

# NB: "with transaction:" does not work because they worked
# really hard to break looking up special methods like __enter__ and __exit__
# via getattr and getattribute; see http://bugs.python.org/issue12022.
# You must use ``with transaction.manager`` instead.

#: The default transaction manager (a `~.ThreadTransactionManager`). All other
#: functions in this module refer to this object.
manager = ThreadTransactionManager()
#: See `.ITransactionManager.get`
get = __enter__ = manager.get
#: See `.ITransactionManager.begin`
begin = manager.begin
#: See `.ITransactionManager.commit`
commit = manager.commit
#: See `.ITransactionManager.abort`
abort = manager.abort
__exit__ = manager.__exit__
#: See `.ITransactionManager.doom`
doom = manager.doom
#: See `.ITransactionManager.isDoomed`
isDoomed = manager.isDoomed
#: See `.ITransactionManager.savepoint`
savepoint = manager.savepoint
#: See `.ITransactionManager.attempts`
attempts = manager.attempts
