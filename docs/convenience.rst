=================================
 Transaction convenience support
=================================

with support
============

We can now use the with statement to define transaction boundaries.

.. doctest::

    >>> import transaction.tests.savepointsample
    >>> dm = transaction.tests.savepointsample.SampleSavepointDataManager()
    >>> list(dm.keys())
    []

We can use it with a manager:

.. doctest::

    >>> with transaction.manager as t:
    ...     dm['z'] = 3
    ...     t.note(u'test 3')

    >>> dm['z']
    3

    >>> dm.last_note == 'test 3'
    True

    >>> with transaction.manager: #doctest ELLIPSIS
    ...     dm['z'] = 4
    ...     xxx
    Traceback (most recent call last):
    ...
    NameError: ... name 'xxx' is not defined

    >>> dm['z']
    3

On Python 2, you can also abbreviate ``with transaction.manager:`` as ``with
transaction:``.  This does not work on Python 3 (see
http://bugs.python.org/issue12022).

Retries
=======

Commits can fail for transient reasons, especially conflicts.
Applications will often retry transactions some number of times to
overcome transient failures.  This typically looks something like::

    for i in range(3):
        try:
           with transaction.manager:
               ... some something ...
        except SomeTransientException:
           continue
        else:
           break

This is rather ugly and easy to get wrong.

Transaction managers provide two helpers for this case.

Running and retrying functions as transactions
----------------------------------------------

The first helper runs a function as a transaction::

    def do_somthing():
        "Do something"
        ... some something ...

    transaction.manager.run(do_somthing)

You can also use this as a decorator, which executes the decorated
function immediately [#decorator-executes]_::

    @transaction.manager.run
    def _():
        "Do something"
        ... some something ...

The transaction manager ``run`` method will run the function and
return the results. If the function raises a ``TransientError``, the
function will be retried a configurable number of times, 3 by
default. Any other exceptions will be raised.

The function name (if it isn't ``'_'``) and docstring, if any, are
added to the transaction description.

You can pass an integer number of times to try to the ``run`` method::

    transaction.manager.run(do_somthing, 9)

    @transaction.manager.run(9)
    def _():
        "Do something"
        ... some something ...

The default number of times to try is 3.

Retrying code blocks using a attempt iterator
---------------------------------------------

An older helper for running transactions uses an iterator of attempts::

  for attempt in transaction.manager.attempts():
      with attempt as t:
          ... some something ...


This runs the code block until it runs without a transient error or
until the number of attempts is exceeded.  By default, it tries 3
times, but you can pass a number of attempts::

  for attempt in transaction.manager.attempts(9):
      with attempt as t:
          ... some something ...

.. [#decorator-executes] Some people find this easier to read, even
   though the result isn't a decorated function, but rather the result of
   calling it in a transaction.  The function name ``_`` is used here to
   emphasize that the function is essentially being used as an anonymous
   function.
