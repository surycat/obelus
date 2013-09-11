
Obelus: Asterisk's best friend
==============================

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


Examples
--------

AMI client
^^^^^^^^^^

Several example AMI clients are available for different frameworks::

   $ python -m obelus.ami.tornadoadapter -h
   $ python -m obelus.ami.tulipadapter -h
   $ python -m obelus.ami.twistedadapter -h

FastAGI server
^^^^^^^^^^^^^^

Several example FastAGI servers are available for different frameworks::

   $ python -m obelus.agi.tornadofastagi -h
   $ python -m obelus.agi.tulipfastagi -h

Study the source codes for these modules for more information about
how to re-use the Obelus protocol classes in your own application.


Development
-----------

Running the test suite
^^^^^^^^^^^^^^^^^^^^^^

To run the test suite with a single Python version, run::

   $ pythonX.Y -m obelus.test

On Python versions before 3.3, you will need to install the
`mock <https://pypi.python.org/pypi/mock/>`_ library.

To run the test suite on all supported interpreters, install
`tox <http://testrun.org/tox/>`_ and run::

   $ tox


FAQ
---

Why "Obelus"?
^^^^^^^^^^^^^

An `obelus <http://en.wikipedia.org/wiki/Obelus>`_ is a typographical
character, a bit like an asterisk.


.. _Tornado: http://www.tornadoweb.org/
.. _Tulip: http://code.google.com/p/tulip/
.. _Twisted: http://www.twistedmatrix.com/

