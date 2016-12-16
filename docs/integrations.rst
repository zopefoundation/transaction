Transaction integrations / Data Manager Implentations
======================================================

The following packages have been integrated with the ``transaction``
package so that their transactions can be integerated with others.

`ZODB <http://www.zodb.org>`_
  ZODB was the original user of the ``transaction`` package.  Its
  transactions are controlled by by ``transaction`` and ZODB fullt
  implements the 2-phase commit protocol.
