Using transactions with SQLAlchemy
==================================

Now that we got the terminology out of the way, let's show how to use this
package in a Python application. One of the most popular ways of using the
transaction package is to combine transactions from the ZODB with a relational
database backend. Likewise, one of the most popular ways of communicating with
a relational database in Python is to use the SQLAlchemy Object-Relational
Mapper. Let's forget about the ZODB for the moment and show how one could use
the transaction module in a Python application that needs to talk to a
relational database.

Installing SQLAlchemy
---------------------

Installing SQLAlchemy is as easy as installing any Python package available on
PyPi::

    $ pip install sqlalchemy

This will install the package in your Python environment. You'll need to set up
a relational database that you can use to work out the examples in the
following sections. SQLAlchemy supports most relational backends that you may
have heard of, but the simplest thing to do is to use SQLite, since it doesn't
require a separate Python driver. You'll have to make sure that the operating
system packages required for using SQLite are present, though.

If you want to use another database, make sure you install the required
system packages and drivers in addition to the database. For information about
which databases are supported and where you can find the drivers, consult
http://www.sqlalchemy.org/docs/core/engines.html#supported-dbapis.

Choosing a data manager
-----------------------

Hopefully, at this point SQLAlchemy and SQLite (or other database if you are
feeling adventurous) are installed. To use this combination with the transaction
package, we need a data manager that knows how to talk to SQLAlchemy so that the
appropriate SQL commands are sent to SQLite whenever an event in the transaction
life-cycle occurs.

Fortunately for us, there is already a package that does this on PyPI, so it's
just a matter of installing it on our system. The package is called
zope.sqlalchemy, but despite its name it doesn't depend on any zope packages
other than zope.interface. By now you already know how to install it::

    $ pip install zope.sqlalchemy

You can now create Python applications that use the transaction module to
control any SQLAlchemy-supported relational backend.

A simple demonstration
----------------------

It's time to show how to use SQLAlchemy together with the transaction package.
To avoid lengthy digressions, knowledge of how SQLAlchemy works is assumed. If
you are not familiar with that, reading the tutorial at
http://www.sqlalchemy.org/docs/orm/tutorial.html will give you a good
enough background to understand what follows.

After installing the required packages, you may wish to follow along the
examples using the Python interpreter where you installed them. The first step
is to create an engine:

.. code-block:: python
    :linenos:

    >>> from sqlalchemy import create_engine
    >>> engine = create_engine('sqlite:///:memory:')

This will connect us to the database. The connection string shown here is for
SQLite, if you set up a different database you will need to look up the correct
connection string syntax for it.

The next step is to define a class that will be mapped to a table in the
relational database. SQLAlchemy's declarative syntax allows us to do that
easily:

.. code-block:: python
    :linenos:

    >>> from sqlalchemy import Column, Integer, String
    >>> from sqlalchemy.ext.declarative import declarative_base
    >>> Base = declarative_base()
    >>> class User(Base):
    >>>     __tablename__ = 'users'
    ...
    ...    id = Column(Integer, primary_key=True)
    ...    name = Column(String)
    ...    fullname = Column(String)
    ...    password = Column(String)
    ...
    >>> Base.metadata.create_all(engine)

The User class is now mapped to the table named 'users'. The create_all method
in line 12 creates the table in case it doesn't exist already.

We can now create a session and integrate the zope.sqlalchemy data manager with
it so that we can use the transaction machinery. This is done by passing a
Session Extension when creating the SQLAlchemy session:

.. code-block:: python
    :linenos:

    >>> from sqlalchemy.orm import sessionmaker
    >>> from zope.sqlalchemy import ZopeTransactionExtension
    >>> Session = sessionmaker(bind=engine, extension=ZopeTransactionExtension())
    >>> session = Session()

In line 3, we create a session class that is bound to the engine that we set up
earlier. Notice how we pass the ZopeTransactionExtension using the extension
parameter. This extension connects the SQLAlchemy session with the data manager
provided by zope.sqlalchemy.

In line 4 we create a session. Under the hood, the ZopeTransactionExtension
makes sure that the current transaction is joined by the zope.sqlalchemy data
manager, so it's not necessary to explicitly join the transaction in our code.

Finally, we are able to put some data inside our new table and commit the
transaction:

.. code-block:: python
    :linenos:

    >>> import transaction
    >>> session.add(User(id=1, name='John', fullname='John Smith', password='123'))
    >>> transaction.commit()

Since the transaction was already joined by the zope.sqlalchemy data manager,
we can just call commit and the transaction is correctly committed. As you can
see, the integration between SQLAlchemy and the transaction machinery is pretty
transparent.

Aborting transactions
---------------------

Of course, when using the transaction machinery you can also abort or rollback
a transaction. An example follows:

.. code-block:: python
    :linenos:

    >>> session = Session()
    >>> john = session.query(User).all()[0]
    >>> john.fullname
    u'John Smith'
    >>> john.fullname = 'John Q. Public'
    >>> john.fullname
    u'John Q. Public'
    >>> transaction.abort()

We need a new transaction for this example, so a new session is created. Since
the old transaction had ended with the commit, creating a new session joins it
to the current transaction, which will be a new one as well.

We make a query just to show that our user's fullname is 'John Smith', then we
change that to 'John Q. Public'. When the transaction is aborted in line 8,
the name is reverted to the old value.

If we create a new session and query the table for our old friend John, we'll
see that the old value was indeed preserved because of the abort:

.. code-block:: python
    :linenos:

    >>> session = Session()
    >>> john = session.query(User).all()[0]
    >>> john.fullname
    u'John Smith'

Savepoints
----------

A nice feature offered by many transactional backends is the existence of
savepoints. These allow in effect to save the changes that we have made at the
current point in a transaction, but without committing the transaction. If
eventually we need to rollback a future operation, we can use the savepoint to
return to the "safe" state that we had saved.

Unfortunately not every database supports savepoints and SQLite is precisely
one of those that doesn't, which means that in order to be able to test this
functionality you will have to install another database, like PostgreSQL. Of
course, you can also just take our word that it really works, so suit yourself.

Let's see how a savepoint would work using PostgreSQL. First we'll import
everything and setup the same table we used in our SQLite examples:

.. code-block:: python
    :linenos:

    >>> from sqlalchemy import create_engine
    >>> engine = create_engine('postgresql://postgres@127.0.0.1:5432')
    >>> from sqlalchemy import Column, Integer, String
    >>> from sqlalchemy.ext.declarative import declarative_base
    >>> Base = declarative_base()
    >>> Base.metadata.create_all(engine)
    >>> class User(Base):
    ...     __tablename__ = 'users'
    ...     id = Column(Integer, primary_key=True)
    ...     name = Column(String)
    ...     fullname = Column(String)
    ...     password = Column(String)
    ...
    >>> Base.metadata.create_all(engine)
    >>> from sqlalchemy.orm import sessionmaker
    >>> from zope.sqlalchemy import ZopeTransactionExtension
    >>> Session = sessionmaker(bind=engine, extension=ZopeTransactionExtension())

We are now ready to create and use a savepoint:

.. code-block:: python
    :linenos:

    >>> import transaction
    >>> session = Session()
    >>> session.add(User(id=1, name='John', fullname='John Smith', password='123'))
    >>> sp = transaction.savepoint()

Everything should look familiar until line 4, where we create a savepoint and
assign it to the sp variable. If we never need to rollback, this will not be
used, but if course we have to hold on to it in case we do.

Now, we'll add a second user:

.. code-block:: python
    :linenos:

    >>> session.add(User(id=2, name='John', fullname='John Watson', password='123'))
    >>> [o.fullname for o in session.query(User).all()]
    [u'John Smith', u'John Watson']

The new user has been added. We have not committed or aborted yet, but suppose
we encounter an error condition that requires us to get rid of the new user,
but not the one we added first. This is where the savepoint comes handy:

.. code-block:: python
    :linenos:

    >>> sp.rollback()
    >>> [o.fullname for o in session.query(User).all()]
    [u'John Smith']
    >>> transaction.commit()

As you can see, we just call the rollback method and we are back to where we
wanted. The transaction can then be committed and the data that we decided to
keep will be saved.

Managing more than one backend
==============================

Going through the previous section's examples, experienced users of any
powerful enough relational backend might have been thinking, "wait, my database
already can do that by itself. I can always commit or rollback when I want to,
so what's the advantage of using this machinery?"

The answer is that if you are using a single backend and it already supports
savepoints, you really don't need a transaction manager. The transaction
machinery can still be useful with a single backend if it doesn't support
transactions. A data manager can be written to add this support. There are
existent packages that do this for files stored in a file system or for email
sending, just to name a few examples.

However, the real power of the transaction manager is the ability to combine
two or more of these data managers in a single transaction. Say you need to
capture data from a form into a relational database and send email only on
transaction commit, that's a good use case for the transaction package.

We will illustrate this by showing an example of coordinating transactions to
a relational database and a ZODB client.

The first thing to do is set up the relational database, using the code that
we've seen before:

.. code-block:: python
    :linenos:

    >>> from sqlalchemy import create_engine
    >>> engine = create_engine('postgresql://postgres@127.0.0.1:5432')
    >>> from sqlalchemy import Column, Integer, String
    >>> from sqlalchemy.ext.declarative import declarative_base
    >>> Base = declarative_base()
    >>> Base.metadata.create_all(engine)
    >>> class User(Base):
    ...     __tablename__ = 'users'
    ...     id = Column(Integer, primary_key=True)
    ...     name = Column(String)
    ...     fullname = Column(String)
    ...     password = Column(String)
    ...
    >>> Base.metadata.create_all(engine)
    >>> from sqlalchemy.orm import sessionmaker
    >>> from zope.sqlalchemy import ZopeTransactionExtension
    >>> Session = sessionmaker(bind=engine, extension=ZopeTransactionExtension())

Now, let's set up a ZODB connection (you might need to install the ZODB first):

.. code-block:: python
    :linenos:

    >>> from ZODB import DB, FileStorage

    >>> storage = FileStorage.FileStorage('test.fs')
    >>> db = DB(storage)
    >>> connection = db.open()
    >>> root = connection.root()

We're ready for adding a user to the relational database table. Right after that,
we add some data to the ZODB using the user name as key:

.. code-block:: python
    :linenos:

    >>> import transaction
    >>> session.add(User(id=1, name='John', fullname='John Smith', password='123'))
    >>> root['John'] = 'some data that goes into the object database'

Since both the ZopeTransactionExtension and the ZODB connection join the
transaction automatically, we can just make the changes we want and be ready to
commit the transaction immediately.

.. code-block:: python

    >>> transaction.commit()

Again, both the SQLAlchemy and the ZODB data managers joined the transaction, so
that we can commit the transaction and both backends save the data. If there's a
problem with one of the backends, the transaction is aborted in both regardless
of the state of the other. It's also possible to abort the transaction manually,
of course, causing a rollback on both backends as well.
