.. Obelus documentation master file, created by
   sphinx-quickstart on Wed Sep 11 12:00:33 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


Obelus: Asterisk's best friend
==============================

Overview
""""""""

Obelus is a MIT-licensed Python library providing support for communication
with the `Asterisk <http://www.asterisk.org/>`_ telephony server.  It
supports the `Asterisk Manager Interface (AMI) <http://asteriskdocs.org/en/3rd_Edition/asterisk-book-html-chunk/asterisk-AMI.html>`_
and the `Asterisk Gateway Interface (AGI) <http://asteriskdocs.org/en/3rd_Edition/asterisk-book-html-chunk/AGI.html>`_.

Quick links
-----------

* Project page: https://pypi.python.org/pypi/obelus/
* Source code, issue tracker: https://bitbucket.org/optiflowsrd/obelus
* Documentation (incomplete): https://obelus.readthedocs.org

Features
--------

* Python 2 and Python 3 support.
* AMI, FastAGI and Async AGI support.
* Event-driven API friendly towards non-blocking ("async") network
  programming styles.
* :pep:`3156`-style protocol implementations.
* Framework-agnostic.
* Adapters for the `Tornado`_, `Twisted`_, `Tulip`_ network programming
  frameworks.
* Unit-tested.

Limitations
-----------

* The API is currently low-level: it abstracts away protocol syntax and
  communication sequences, but doesn't try to expose Asterisk concepts
  in a particular way.

Requirements
------------

* Python 2.7, 3.2 or later.

Optional requirements
^^^^^^^^^^^^^^^^^^^^^

* `Tornado`_, `Twisted`_ or `Tulip`_, if you want to use one of the
  corresponding adapters.


Documentation
"""""""""""""

.. toctree::
   guide
   apidocs

.. _Tornado: http://www.tornadoweb.org/
.. _Tulip: http://code.google.com/p/tulip/
.. _Twisted: http://www.twistedmatrix.com/

.. toctree::
   :maxdepth: 2

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

