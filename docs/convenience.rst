Transaction convenience support
===============================

(We *really* need to write proper documentation for the transaction
 package, but I don't want to block the conveniences documented here
 for that.)

with support
------------

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
    ...     t.note('test 3')

    >>> dm['z']
    3

    >>> dm.last_note
    'test 3'

    >>> with transaction.manager: #doctest ELLIPSIS
    ...     dm['z'] = 4
    ...     xxx
    Traceback (most recent call last):
    ...
    NameError: ... name 'xxx' is not defined

    >>> dm['z']
    3

On Python 2, you can also abbreviate ``with transaction.manager:`` as ``with
transaction:``.  This does not work on Python 3 (see see
http://bugs.python.org/issue12022).

Retries
-------

Commits can fail for transient reasons, especially conflicts.
Applications will often retry transactions some number of times to
overcome transient failures.  This typically looks something like:

.. doctest::

    for i in range(3):
        try:
           with transaction.manager:
               ... some something ...
        except SomeTransientException:
           contine
        else:
           break

This is rather ugly.

Transaction managers provide a helper for this case. To show this,
we'll use a contrived example:

.. doctest::

    >>> ntry = 0
    >>> with transaction.manager:
    ...      dm['ntry'] = 0

    >>> import transaction.interfaces
    >>> class Retry(transaction.interfaces.TransientError):
    ...     pass

    >>> for attempt in transaction.manager.attempts():
    ...     with attempt as t:
    ...         t.note('test')
    ...         print("%s %s" % (dm['ntry'], ntry))
    ...         ntry += 1
    ...         dm['ntry'] = ntry
    ...         if ntry % 3:
    ...             raise Retry(ntry)
    0 0
    0 1
    0 2

The raising of a subclass of TransientError is critical here. It's
what signals that the transaction should be retried.  It is generally
up to the data manager to signal that a transaction should try again
by raising a subclass of TransientError (or TransientError itself, of
course).

You shouldn't make any assumptions about the object returned by the
iterator.  (It isn't a transaction or transaction manager, as far as
you know. :)  If you use the ``as`` keyword in the ``with`` statement,
a transaction object will be assigned to the variable named.

By default, it tries 3 times. We can tell it how many times to try:

.. doctest::

    >>> for attempt in transaction.manager.attempts(2):
    ...     with attempt:
    ...         ntry += 1
    ...         if ntry % 3:
    ...             raise Retry(ntry)
    Traceback (most recent call last):
    ...
    Retry: 5

It it doesn't succeed in that many times, the exception will be
propagated.

Of course, other errors are propagated directly:

.. doctest::

    >>> ntry = 0
    >>> for attempt in transaction.manager.attempts():
    ...     with attempt:
    ...         ntry += 1
    ...         if ntry == 3:
    ...             raise ValueError(ntry)
    Traceback (most recent call last):
    ...
    ValueError: 3

We can use the default transaction manager:

.. doctest::

    >>> for attempt in transaction.attempts():
    ...     with attempt as t:
    ...         t.note('test')
    ...         print("%s %s" % (dm['ntry'], ntry))
    ...         ntry += 1
    ...         dm['ntry'] = ntry
    ...         if ntry % 3:
    ...             raise Retry(ntry)
    3 3
    3 4
    3 5

Sometimes, a data manager doesn't raise exceptions directly, but
wraps other other systems that raise exceptions outside of it's
control.  Data  managers can provide a should_retry method that takes
an exception instance and returns True if the transaction should be
attempted again.

.. doctest::

    >>> class DM(transaction.tests.savepointsample.SampleSavepointDataManager):
    ...     def should_retry(self, e):
    ...         if 'should retry' in str(e):
    ...             return True

    >>> ntry = 0
    >>> dm2 = DM()
    >>> with transaction.manager:
    ...     dm2['ntry'] = 0
    >>> for attempt in transaction.manager.attempts():
    ...     with attempt:
    ...         print("%s %s" % (dm['ntry'], ntry))
    ...         ntry += 1
    ...         dm['ntry'] = ntry
    ...         dm2['ntry'] = ntry
    ...         if ntry % 3:
    ...             raise ValueError('we really should retry this')
    6 0
    6 1
    6 2

    >>> dm2['ntry']
    3
