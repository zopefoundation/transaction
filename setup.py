##############################################################################
#
# Copyright (c) 2007 Zope Foundation and Contributors.
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
import os
from setuptools import setup, find_packages

version = '2.3.0'
here = os.path.abspath(os.path.dirname(__file__))


def _read_file(filename):
    with open(os.path.join(here, filename)) as f:
        return f.read()


README = _read_file('README.rst') + '\n\n' + _read_file('CHANGES.rst')

tests_require = ['mock']

setup(name='transaction',
      version=version,
      description='Transaction management for Python',
      long_description=README,
      classifiers=[
          "Development Status :: 6 - Mature",
          "License :: OSI Approved :: Zope Public License",
          "Programming Language :: Python",
          "Topic :: Database",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Operating System :: Microsoft :: Windows",
          "Operating System :: Unix",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.4",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: Implementation :: CPython",
          "Programming Language :: Python :: Implementation :: PyPy",
          "Framework :: ZODB",
      ],
      author="Zope Corporation",
      author_email="zodb-dev@zope.org",
      url="https://github.com/zopefoundation/transaction",
      license="ZPL 2.1",
      platforms=["any"],
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite="transaction.tests",
      tests_require=tests_require,
      install_requires=[
          'zope.interface',
      ],
      extras_require={
          'docs': ['Sphinx', 'repoze.sphinx.autointerface'],
          'test': tests_require,
          'testing': ['nose', 'coverage'] + tests_require,
      },
      entry_points="""\
      """
      )
