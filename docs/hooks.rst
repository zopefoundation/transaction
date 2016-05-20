Hooking the Transaction Machinery
=================================

The :meth:`addBeforeCommitHook` Method
--------------------------------------

Let's define a hook to call, and a way to see that it was called.

.. doctest::

    >>> log = []
    >>> def reset_log():
    ...     del log[:]

    >>> def hook(arg='no_arg', kw1='no_kw1', kw2='no_kw2'):
    ...     log.append("arg %r kw1 %r kw2 %r" % (arg, kw1, kw2))

Now register the hook with a transaction.

.. doctest::

    >>> from transaction import begin
    >>> from transaction._compat import func_name
    >>> import transaction
    >>> t = begin()
    >>> t.addBeforeCommitHook(hook, '1')

We can see that the hook is indeed registered.

.. doctest::

    >>> [(func_name(hook), args, kws)
    ...  for hook, args, kws in t.getBeforeCommitHooks()]
    [('hook', ('1',), {})]

When transaction commit starts, the hook is called, with its
arguments.

.. doctest::

    >>> log
    []
    >>> t.commit()
    >>> log
    ["arg '1' kw1 'no_kw1' kw2 'no_kw2'"]
    >>> reset_log()

A hook's registration is consumed whenever the hook is called.  Since
the hook above was called, it's no longer registered:

.. doctest::

    >>> from transaction import commit
    >>> len(list(t.getBeforeCommitHooks()))
    0
    >>> commit()
    >>> log
    []

The hook is only called for a full commit, not for a savepoint.

.. doctest::

    >>> t = begin()
    >>> t.addBeforeCommitHook(hook, 'A', dict(kw1='B'))
    >>> dummy = t.savepoint()
    >>> log
    []
    >>> t.commit()
    >>> log
    ["arg 'A' kw1 'B' kw2 'no_kw2'"]
    >>> reset_log()

If a transaction is aborted, no hook is called.

.. doctest::

    >>> from transaction import abort
    >>> t = begin()
    >>> t.addBeforeCommitHook(hook, ["OOPS!"])
    >>> abort()
    >>> log
    []
    >>> commit()
    >>> log
    []

The hook is called before the commit does anything, so even if the
commit fails the hook will have been called.  To provoke failures in
commit, we'll add failing resource manager to the transaction.

.. doctest::

    >>> class CommitFailure(Exception):
    ...     pass
    >>> class FailingDataManager:
    ...     def tpc_begin(self, txn, sub=False):
    ...         raise CommitFailure('failed')
    ...     def abort(self, txn):
    ...         pass

    >>> t = begin()
    >>> t.join(FailingDataManager())

    >>> t.addBeforeCommitHook(hook, '2')

    >>> from transaction.tests.common import DummyFile
    >>> from transaction.tests.common import Monkey
    >>> from transaction.tests.common import assertRaisesEx
    >>> from transaction import _transaction
    >>> buffer = DummyFile()
    >>> with Monkey(_transaction, _TB_BUFFER=buffer):
    ...     err = assertRaisesEx(CommitFailure, t.commit)
    >>> log
    ["arg '2' kw1 'no_kw1' kw2 'no_kw2'"]
    >>> reset_log()

Let's register several hooks.

.. doctest::

    >>> t = begin()
    >>> t.addBeforeCommitHook(hook, '4', dict(kw1='4.1'))
    >>> t.addBeforeCommitHook(hook, '5', dict(kw2='5.2'))

They are returned in the same order by getBeforeCommitHooks.

.. doctest::

    >>> [(func_name(hook), args, kws)  #doctest: +NORMALIZE_WHITESPACE
    ...  for hook, args, kws in t.getBeforeCommitHooks()]
    [('hook', ('4',), {'kw1': '4.1'}),
    ('hook', ('5',), {'kw2': '5.2'})]

And commit also calls them in this order.

.. doctest::

    >>> t.commit()
    >>> len(log)
    2
    >>> log  #doctest: +NORMALIZE_WHITESPACE
    ["arg '4' kw1 '4.1' kw2 'no_kw2'",
    "arg '5' kw1 'no_kw1' kw2 '5.2'"]
    >>> reset_log()

While executing, a hook can itself add more hooks, and they will all
be called before the real commit starts.

.. doctest::

    >>> def recurse(txn, arg):
    ...     log.append('rec' + str(arg))
    ...     if arg:
    ...         txn.addBeforeCommitHook(hook, '-')
    ...         txn.addBeforeCommitHook(recurse, (txn, arg-1))

    >>> t = begin()
    >>> t.addBeforeCommitHook(recurse, (t, 3))
    >>> commit()
    >>> log  #doctest: +NORMALIZE_WHITESPACE
    ['rec3',
            "arg '-' kw1 'no_kw1' kw2 'no_kw2'",
    'rec2',
            "arg '-' kw1 'no_kw1' kw2 'no_kw2'",
    'rec1',
            "arg '-' kw1 'no_kw1' kw2 'no_kw2'",
    'rec0']
    >>> reset_log()

The :meth:`addAfterCommitHook` Method
--------------------------------------

Let's define a hook to call, and a way to see that it was called.

.. doctest::

    >>> log = []
    >>> def reset_log():
    ...     del log[:]

    >>> def hook(status, arg='no_arg', kw1='no_kw1', kw2='no_kw2'):
    ...     log.append("%r arg %r kw1 %r kw2 %r" % (status, arg, kw1, kw2))

Now register the hook with a transaction.

.. doctest::

    >>> from transaction import begin
    >>> from transaction._compat import func_name
    >>> t = begin()
    >>> t.addAfterCommitHook(hook, '1')

We can see that the hook is indeed registered.

.. doctest::


    >>> [(func_name(hook), args, kws)
    ...  for hook, args, kws in t.getAfterCommitHooks()]
    [('hook', ('1',), {})]

When transaction commit is done, the hook is called, with its
arguments.

.. doctest::

    >>> log
    []
    >>> t.commit()
    >>> log
    ["True arg '1' kw1 'no_kw1' kw2 'no_kw2'"]
    >>> reset_log()

A hook's registration is consumed whenever the hook is called.  Since
the hook above was called, it's no longer registered:

.. doctest::

    >>> from transaction import commit
    >>> len(list(t.getAfterCommitHooks()))
    0
    >>> commit()
    >>> log
    []

The hook is only called after a full commit, not for a savepoint.

.. doctest::

    >>> t = begin()
    >>> t.addAfterCommitHook(hook, 'A', dict(kw1='B'))
    >>> dummy = t.savepoint()
    >>> log
    []
    >>> t.commit()
    >>> log
    ["True arg 'A' kw1 'B' kw2 'no_kw2'"]
    >>> reset_log()

If a transaction is aborted, no hook is called.

.. doctest::

    >>> from transaction import abort
    >>> t = begin()
    >>> t.addAfterCommitHook(hook, ["OOPS!"])
    >>> abort()
    >>> log
    []
    >>> commit()
    >>> log
    []

The hook is called after the commit is done, so even if the
commit fails the hook will have been called.  To provoke failures in
commit, we'll add failing resource manager to the transaction.

.. doctest::

    >>> class CommitFailure(Exception):
    ...     pass
    >>> class FailingDataManager:
    ...     def tpc_begin(self, txn):
    ...         raise CommitFailure('failed')
    ...     def abort(self, txn):
    ...         pass

    >>> t = begin()
    >>> t.join(FailingDataManager())

    >>> t.addAfterCommitHook(hook, '2')
    >>> from transaction.tests.common import DummyFile
    >>> from transaction.tests.common import Monkey
    >>> from transaction.tests.common import assertRaisesEx
    >>> from transaction import _transaction
    >>> buffer = DummyFile()
    >>> with Monkey(_transaction, _TB_BUFFER=buffer):
    ...     err = assertRaisesEx(CommitFailure, t.commit)
    >>> log
    ["False arg '2' kw1 'no_kw1' kw2 'no_kw2'"]
    >>> reset_log()

Let's register several hooks.

.. doctest::

    >>> t = begin()
    >>> t.addAfterCommitHook(hook, '4', dict(kw1='4.1'))
    >>> t.addAfterCommitHook(hook, '5', dict(kw2='5.2'))

They are returned in the same order by getAfterCommitHooks.

.. doctest::

    >>> [(func_name(hook), args, kws)     #doctest: +NORMALIZE_WHITESPACE
    ...  for hook, args, kws in t.getAfterCommitHooks()]
    [('hook', ('4',), {'kw1': '4.1'}),
    ('hook', ('5',), {'kw2': '5.2'})]

And commit also calls them in this order.

.. doctest::

    >>> t.commit()
    >>> len(log)
    2
    >>> log  #doctest: +NORMALIZE_WHITESPACE
    ["True arg '4' kw1 '4.1' kw2 'no_kw2'",
    "True arg '5' kw1 'no_kw1' kw2 '5.2'"]
    >>> reset_log()

While executing, a hook can itself add more hooks, and they will all
be called before the real commit starts.

.. doctest::

    >>> def recurse(status, txn, arg):
    ...     log.append('rec' + str(arg))
    ...     if arg:
    ...         txn.addAfterCommitHook(hook, '-')
    ...         txn.addAfterCommitHook(recurse, (txn, arg-1))

    >>> t = begin()
    >>> t.addAfterCommitHook(recurse, (t, 3))
    >>> commit()
    >>> log  #doctest: +NORMALIZE_WHITESPACE
    ['rec3',
            "True arg '-' kw1 'no_kw1' kw2 'no_kw2'",
    'rec2',
            "True arg '-' kw1 'no_kw1' kw2 'no_kw2'",
    'rec1',
            "True arg '-' kw1 'no_kw1' kw2 'no_kw2'",
    'rec0']
    >>> reset_log()

If an after commit hook is raising an exception then it will log a
message at error level so that if other hooks are registered they
can be executed. We don't support execution dependencies at this level.

.. doctest::

    >>> from transaction import TransactionManager
    >>> from transaction.tests.test__manager import DataObject
    >>> mgr = TransactionManager()
    >>> do = DataObject(mgr)

    >>> def hookRaise(status, arg='no_arg', kw1='no_kw1', kw2='no_kw2'):
    ...     raise TypeError("Fake raise")

    >>> t = begin()

    >>> t.addAfterCommitHook(hook, ('-', 1))
    >>> t.addAfterCommitHook(hookRaise, ('-', 2))
    >>> t.addAfterCommitHook(hook, ('-', 3))
    >>> commit()

    >>> log
    ["True arg '-' kw1 1 kw2 'no_kw2'", "True arg '-' kw1 3 kw2 'no_kw2'"]

    >>> reset_log()

Test that the associated transaction manager has been cleaned up when
after commit hooks are registered

.. doctest::

    >>> mgr = TransactionManager()
    >>> do = DataObject(mgr)

    >>> t = begin()
    >>> t._manager._txn is not None
    True

    >>> t.addAfterCommitHook(hook, ('-', 1))
    >>> commit()

    >>> log
    ["True arg '-' kw1 1 kw2 'no_kw2'"]

    >>> t._manager._txn is not None
    False

    >>> reset_log()
