
Development
===========

Getting set up
--------------

Getting the source code
"""""""""""""""""""""""

Obelus is developed using `Mercurial <http://mercurial.selenic.com/>`_
and its source respository is hosted at
`BitBucket <https://bitbucket.org/optiflowsrd/obelus>`_.

To make a local clone of the repository, use::

   $ hg clone https://bitbucket.org/optiflowsrd/obelus

Coding conventions
""""""""""""""""""

Obelus follows the :pep:`8` coding style.  Read it!

Regression tests
""""""""""""""""

The automated test suite is hosted in the :mod:`obelus.test` package.
It uses the standard :py:mod:`unittest` module as well as the third-party
`mock <http://pypi.python.org/pypi/mock/>`_ library (bundled as
:py:mod:`unittest.mock` starting from Python 3.3).

You can run the test suite simply by invoking the :mod:`obelus.test`
package::

   $ python -m obelus.test

(various options are available, such as ``-v`` to print each test name
as it is run; use ``-h`` to list available options)

Documentation
"""""""""""""

The documentation uses `Sphinx <http://sphinx-doc.org/>`_ and resides
inside the ``docs`` directory.  To build it, install Sphinx, go inside
the ``docs`` directory and type::

   $ make html

The result will be available in ``docs/_build/html``.

Code coverage testing
"""""""""""""""""""""

To measure which parts of the code are covered by the test suite, use
the supplied ``run_coverage.py`` script (the
`coverage <https://pypi.python.org/pypi/coverage/>`_ library must be
installed).  HTML-formatted results are then available inside the
``htmlcov`` directory: point your browser to the ``index.html`` file
inside that directory.

All-in-one integration testing: tox
"""""""""""""""""""""""""""""""""""

It is actually possible to automate all the above by using the
`tox <http://testrun.org/tox/>`_ utility.  Tox will create a series of
local environments, fetch the required dependencies for each of them
and run the desired command inside each of them.  Currently, the
actions ran by tox include:

* running the test suite under Python 2.7, 3.2 and 3.3
* running the test suite with code coverage enabled, so as to create
  the coverage report in ``htmlcov``
* building the documentation and making the result available in
  ``docs/_build/html``

(this is all described in the ``tox.ini`` file at the root of the source
tree)

All you have to do is to type this single command::

   $ tox

Note that you can select a single "environment" (or action) to run; for
example, to only re-build the docs, type::

   $ tox -e docs


Contributing
------------

Contributions are welcome.  The ecosystem of Python Asterisk libraries
is currently fragmented; Obelus' design ambitions to achieve reusability
in more contexts than the usual per-framework, per-programming style
segregation.

If you have **code** to contribute (either a new feature, an enhancement or
a bug fix), you can fork the repository on `BitBucket`_ and create a pull
request with your changes.

If you want to contribute **documentation**, you can either use the same
workflow as for code or (for small changes) open an issue on the tracker
with your suggested changes.

If you want to **discuss** a potential change or problem, please either
create an issue on the `issue tracker <https://bitbucket.org/optiflowsrd/obelus/issues>`_
or contact the author by e-mail.

Guidelines
""""""""""

Here are some formal guidelines for code changes:

* Your change must have unit tests for it
* Your code must respect :pep:`8` and the general coding style of the
  library
* Your code must be compatible with Python 2.7, 3.2 and later (running
  ``tox`` helps ensure that, see above)
* Your code must not break existing tests.

There are also some design principles which new code should abide by:

* Global state is shunned, because it limits the library's flexibility
  and also because it makes testing more painful.

* Actual I/O (input / output) should be separated into specialized modules
  or objects, such as the existing :ref:`adapters <adapters>`.

* The core classes should be event-driven, and never block waiting on
  external events.

Avenues for development
"""""""""""""""""""""""

If you are looking for ideas or wondering what is currently lacking, here
are a bunch of suggestions:

* Add high-level methods to :class:`obelus.agi.AGISession` exposing the
  various AGI commands (as pyst does).

* Develop unit tests for the Tornado and Twisted adapters.

* Make the CLI examples more featureful.

* Investigate if :class:`obelus.common.Handler` can be made to resemble
  :pep:`3156` Futures (perhaps by reusing Tornado's
  `_DummyFuture <https://github.com/facebook/tornado/blob/master/tornado/concurrent.py>`_
  implementation?).

* Investigate if :class:`obelus.common.Handler` can be integrated into
  Tornado and Twisted coroutines (this may or may not be the same question
  as the previous one).

