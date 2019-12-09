=========================================================
 Transaction integrations / Data Manager Implementations
=========================================================

The following packages have been integrated with the ``transaction``
package so that their transactions can be integerated with others.

`ZODB <http://www.zodb.org>`_

  ZODB was the original user of the ``transaction`` package.  Its
  transactions are controlled by ``transaction`` and ZODB fully
  implements the 2-phase commit protocol.

`SQLAlchemy <http://www.sqlalchemy.org>`_

  An Object Relational Mapper for Python, SQLAlchemy can use
  `zope.sqlalchemy
  <https://github.com/zopefoundation/zope.sqlalchemy>`_ to have its
  transactions integrated with others.

`repoze.sendmail <http://docs.repoze.org/sendmail/narr.html>`_

  repoze.sendmail allows coupling the sending of email messages with a
  transaction,  using the Zope transaction manager. This allows
  messages to only be sent out when and if a transaction is committed,
  preventing users from receiving notifications about events which may
  not have completed successfully.
