=========
 Changes
=========

4.1 (unreleased)
================

- Nothing changed yet.


4.0 (2023-11-13)
================

- Drop support for Python 2.7, 3.5, 3.6.

- Drop support for deprecated ``python setup.py test.``.

- Add support for Python 3.12.

- Add preliminary support for Python 3.13a2.


3.1.0 (2023-03-17)
==================

- Add support for Python 3.9, 3.10, 3.11.


3.0.1 (2020-12-11)
==================

- Exception raised by a before commit hook is no longer hidden.  No
  further commit hooks are called and exception is propagated to
  the caller of ``commit()``. See
  `#95 <https://github.com/zopefoundation/transaction/pull/95>`_.


3.0.0 (2019-12-11)
==================

- Drop support for Python 3.4.

- Add support for Python 3.8.

- Drop support for legacy transaction APIs including
  ``Transaction.register()`` and old ZODB3-style datamanagers. See
  `issue 89
  <https://github.com/zopefoundation/transaction/issues/89>`_.

- ``TransactionManager.run`` now commits/aborts the transaction
  "active" after the execution of *func* (and no longer the initial
  transaction which might already have been committed/aborted by *func*)
  (`#58 <https://github.com/zopefoundation/transaction/issues/58>`_).

  It aborts the transaction now for all exceptions raised by *func* - even
  if it is only an instance of `BaseException` but not of `Exception`,
  such as e.g. a ``SystemExit`` or ``KeyboardInterupt`` exception.

- Support abort hooks (symmetrically to commit hooks)
  (`#77 <https://github.com/zopefoundation/transaction/issues/77>`_).

- Make Transaction drop references to its hooks, manager,
  synchronizers and data after a successful ``commit()`` and after
  *any* ``abort()``. This helps avoid potential cyclic references. See
  `issue 82 <https://github.com/zopefoundation/transaction/issues/82>`_.

- Allow synchronizers to access ``Transaction.data()`` when their
  ``afterCompletion`` method is called while aborting a transaction.

- Make it safe to call ``Transaction.abort()`` more than once. The
  second and subsequent calls are no-ops. Previously a
  ``ValueError(Foreign transaction)`` would be raised.

2.4.0 (2018-10-23)
==================

- Changed the implementation of ThreadTransactionManager to be a
  thread.local that wraps a TransactionManager rather than a
  thread.local that inherits from TransactionManager. It now exposes a
  manager attribute that allows access to the wrapped transaction
  manager to allow cross thread calls. See `issue 68
  <https://github.com/zopefoundation/transaction/pull/68>`_.


2.3.0 (2018-10-19)
==================

- Add support for Python 3.7.

- Reach 100% test coverage.

- Fix ``transaction.manager.run`` formatting transaction notes when
  given a mix of byte and text strings, such as can happen in Python 2
  with ``unicode_literals``.

2.2.1 (2018-03-27)
==================

- Make documentation index more user friendly; move old docs to developer
  section.

- Don't crash when printing tracebacks in IPython on Python 2.
  (This addresses https://github.com/zopefoundation/transaction/issues/5.)


2.2.0 (2018-02-27)
==================

- Add support for Python 3.6.

- Drop support for Python 3.3.

- Add ``isRetryableError`` to the
  ``transaction.interfaces.ITransaction`` interface to allow external
  systems to query whether an exception is retryable (transient) by
  any of the attached data managers. Any
  ``transaction.interfaces.TransientError`` is considered retryable
  but a data manager may also consider other exceptions on a
  per-instance basis.

  See https://github.com/zopefoundation/transaction/pull/38


2.1.2 (2017-03-11)
==================

- To avoid leaking memory, don't include unexpected value in warnings
  about non-text transaction meta data.


2.1.1 (2017-03-11)
==================

- For backward compatibility, relax the requirements that transaction
  meta data (user or description) be text:

  - If None is assigned, the assignment is ignored.

  - If a non-text value is assigned, a warning is issued and the value
    is converted to text. If the value is a binary string, it will be
    decoded with the UTF-8 encoding the ``replace`` error policy.


2.1.0 (2017-02-08)
==================

Added a transaction-manager explicit mode. Explicit mode makes some
kinds of application bugs easier to detect and potentially allows data
managers to manage resources more efficiently.

(This addresses https://github.com/zopefoundation/transaction/issues/35.)

2.0.3 (2016-11-17)
==================

- The user and description fields must now be set with text (unicode)
  data.  Previously, if bytes were provided, they'd be decoded as
  ASCII.  It was decided that this would lead to bugs that were hard
  to test for.

  Also, the transaction meta-data field, ``extended_info`` has been
  renamed to ``extension``.

2.0.2 (2016-11-13)
==================

- Fixed: Some legacy applications expect the transaction _extension
  attribute to be mutable and it wasn't.

2.0.1 (2016-11-11)
==================

- The transaction ``user`` and ``description`` attributes are now
  defined to be text (unicode) as opposed to Python the ``str`` type.

- Added the ``extended_info`` transaction attribute which contains
  transaction meta data.  (The ``_extension`` attribute is retained as
  an alias for backward compatibility.)

  The transaction interface, ``ITransaction``, now requires
  ``extended_info`` keys to be text (unicode) and values to be
  JSON-serializable.

- Removed setUser from ITransaction.  We'll keep the method
  indefinitely, but it's unseemly in ITransaction. :)

The main purpose of these changes is to tighten up the text
specification of user, description and extended_info keys, and to give
us more flexibility in the future for serializing extended info.  It's
possible that these changes will be breaking, so we're also increasing
the major version number.

1.7.0 (2016-11-08)
==================

- Added a transaction-manager ``run`` method for running a function as a
  transaction, retrying as necessary on transient errors.

- Fixed the transaction manager ``attempts`` method. It didn't stop
  repeating when there wasn't an error.

- Corrected ITransaction by removing beforeCommitHook (which is no longer
  implemented) and removing 'self' from two methods.

1.6.1 (2016-06-10)
==================

- Fixed: Synchonizers that registered with transaction managers when
  transactions were in progress didn't have their newTransaction
  methods called to let them know of the in-progress transactions.

1.6.0 (2016-05-21)
==================

- New transaction API for storing data on behalf of objects, such as
  data managers.

- Drop references to data managers joined to a transaction when it is
  committed or aborted.

1.5.0 (2016-05-05)
==================

- Drop support for Python 2.6 and 3.2.

- Add support for Python 3.5.

- Added APIs for interogating and clearing internal state to support
  client tests.

1.4.4 (2015-05-19)
==================

- Use the standard ``valuerefs()`` method rather than relying on
  implementation details of ``WeakValueDictionary`` in ``WeakSet``.

- Add support for PyPy3.

- Require 100% branch coverage (in addition to 100% statement coverage).

1.4.3 (2014-03-20)
==================

- Add support for Python 3.4.

1.4.2 (skipped)
===============

- Released in error as 1.4.3.

1.4.1 (2013-02-20)
==================

- Document that values returned by ``sortKey`` must be strings, in order
  to guarantee total ordering.

- Fix occasional RuntimeError: dictionary changed size during iteration errors
  in transaction.weakset on Python 3.

1.4.0 (2013-01-03)
==================

- Updated Trove classifiers.

1.4.0b1 (2012-12-18)
====================

- Converted existing doctests into Sphinx documentation (snippets are
  exercised via 'tox').

- 100% unit test coverage.

- Backward incompatibility:   raise ValueError rather than AssertionError
  for runtime errors:

  - In ``Transaction.doom`` if the transaction is in a non-doomable state.

  - In ``TransactionManager.attempts`` if passed a non-positive value.

  - In ``TransactionManager.free`` if passed a foreign transaction.

- Declared support for Python 3.3 in ``setup.py``, and added ``tox`` testing.

- When a non-retryable exception was raised as the result of a call to
  ``transaction.manager.commit`` within the "attempts" machinery, the
  exception was not reraised properly.  Symptom: an unrecoverable exception
  such as ``Unsupported: Storing blobs in <somestorage> is not supported.``
  would be swallowed inappropriately.

1.3.0 (2012-05-16)
==================

- Added Sphinx API docuementation.

- Added explicit support for PyPy.

- Dropped use of Python3-impatible ``zope.interface.implements`` class
  advisor in favor of ``zope.interface.implementer`` class decorator.

- Added support for continuous integration using ``tox`` and ``jenkins``.

- Added ``setup.py docs`` alias (installs ``Sphinx`` and dependencies).

- Added ``setup.py dev`` alias (runs ``setup.py develop`` plus installs
  ``nose`` and ``coverage``).

- Python 3.3 compatibility.

- Fix "for attempt in transaction.attempts(x)" machinery, which would not
  retry a transaction if its implicit call to ``.commit()`` itself raised a
  transient error.  Symptom: seeing conflict errors even though you thought
  you were retrying some number of times via the "attempts" machinery (the
  first attempt to generate an exception during commit would cause that
  exception to be raised).

1.2.0 (2011-12-05)
==================

New Features:

- Python 3.2 compatibility.

- Dropped Python 2.4 and 2.5 compatibility (use 1.1.1 if you need to use
  "transaction" under these Python versions).

1.1.1 (2010-09-16)
==================

Bug Fixes:

- Code in ``_transaction.py`` held on to local references to traceback
  objects after calling ``sys.exc_info()`` to get one, causing
  potential reference leakages.

- Fixed ``hexlify`` NameError in ``transaction._transaction.oid_repr``
  and add test.

1.1.0 (1010-05-12)
==================

New Features:

- Transaction managers and the transaction module can be used with the
  with statement to define transaction boundaries, as in::

     with transaction:
         ... do some things ...

  See transaction/tests/convenience.txt for more details.

- There is a new iterator function that automates dealing with
  transient errors (such as ZODB confict errors). For example, in::

     for attempt in transaction.attempts(5):
         with attempt:
             ... do some things ..

  If the work being done raises transient errors, the transaction will
  be retried up to 5 times.

  See transaction/tests/convenience.txt for more details.

Bugs fixed:

- Fixed a bug that caused extra commit calls to be made on data
  managers under certain special circumstances.

  https://mail.zope.org/pipermail/zodb-dev/2010-May/013329.html

- When threads were reused, transaction data could leak accross them,
  causing subtle application bugs.

  https://bugs.launchpad.net/zodb/+bug/239086

1.0.1 (2010-05-07)
==================

- LP #142464:  remove double newline between log entries:  it makes doing
  smarter formatting harder.

- Updated tests to remove use of deprecated ``zope.testing.doctest``.

1.0.0 (2009-07-24)
==================

- Fix test that incorrectly relied on the order of a list that was generated
  from a dict.

- Remove crufty DEPENDENCIES.cfg left over from zpkg.

1.0a1 (2007-12-18)
==================

- Initial release, branched from ZODB trunk on 2007-11-08 (aka
  "3.9.0dev").

- Remove (deprecated) support for beforeCommitHook alias to
  addBeforeCommitHook.

- Add weakset tests.

- Remove unit tests that depend on ZODB.tests.utils from
  test_transaction (these are actually integration tests).
