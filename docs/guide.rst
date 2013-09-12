
User's Guide
============

Philosophy
----------

Obelus, as a network programming library, doesn't want to be tied to
a particular framework.  Some people want to use `Twisted`_, others
`Tornado`_, others `Tulip`_.  The solution is to provide APIs that
are framework-agnostic.  Everyone can then write their own adapters,
though Obelus provides a couple of them
(:class:`~obelus.tornadosupport.TornadoAdapter`,
:class:`~obelus.twistedsupport.TwistedAdapter`).

Still, to avoid inventing yet another API, it was decided to settle
on :pep:`3156`-like protocols.

.. note::
   `Tulip`_ doesn't need any adapter: Obelus protocols can be used
   directly.


Bytes and strings
"""""""""""""""""

As a library that works both under Python 2 and Python 3, Obelus has
to be careful about its bytes / test separation model.  Since Asterisk
itself doesn't seem very careful in this regard, the following choice
was made:

* Under Python 2, all text and data is represented using the :class:`str`
  class.

* Under Python 3, binary data (going in and out of protocols) uses
  :class:`bytes` objects, but all high-level data (such as command and
  action names and parameters) uses :class:`str` objects.  An utf-8
  encoding is implied by default, but this can be changed.  Encoding
  and decoding is handled by the protocols.


Futures, promises... handlers
"""""""""""""""""""""""""""""

Non-blocking network programming usually revolves around passing and
invoking callbacks.  To abstract that notion, Obelus defines a
:class:`~obelus.common.Handler` class.  When a library function performing
an operation returns a handler, you can set its
:attr:`~obelus.common.Handler.on_result` and
:attr:`~obelus.common.Handler.on_exception` attributes to functions which
will be called with the successful or exceptional result of the operation,
respectively.


Protocols and transports
""""""""""""""""""""""""

.. note::
   This section is only useful if you are writing your own protocol
   adapter, rather than using one of the provided ones.

A protocol is a class (or instance) implementing a particular network
protocol.  Obelus provides :class:`~obelus.ami.AMIProtocol` and
:class:`~obelus.agi.AGIProtocol`.  Protocols don't do any I/O on their
own: they don't need any socket or file-like object.  Rather, they use
event-driven programming and callbacks.

Here are the standard event-driven methods on a protocol:

.. method:: data_received(data)

   Signal that *data* has been received and should be processed by
   the protocol.  Note that the protocol may only buffer the data,
   if e.g. it is incomplete.

   *data* should be a bytestring.

.. method:: connection_made(transport)

   Signal the protocol that the connection is established, and can
   be accessed (written to, or closed) using the given *transport*
   object.

.. method:: connection_lost(exc)

   Signal the protocol that the connection is lost, for whatever
   reason.  If *exc* is not None, it is an exception instance
   giving information about the error that marked the connection lost.


Here are the methods which should be implemented by a transport
(which is generally also your adapter instance):

.. method:: write(data)

   Write the *data* (a bytestring) on the underlying connection.

.. method:: close()

   Close the underlying connection.

.. seealso::
   "Bidirectional Stream Transports" and "Stream Protocols"
   in :pep:`3156`.


Writing an adapter
""""""""""""""""""

An adapter should implement the two required transport methods
(:meth:`write`, :meth:`close`), and be able to call the three
aforementioned protocol methods (:meth:`connection_made`,
:meth:`data_received`, :meth:`connection_lost`).


Asterisk Management Interface
-----------------------------

The :abbr:`AMI (Asterisk Management Interface)` allows you to connect
to a well-known TCP port on your Asterisk server.  You can then emit
commands ("actions") to it, receive response and asynchronous events
sent by the server.

You can interact with the AMI using the :class:`obelus.ami.AMIProtocol`.

To send actions, call the :meth:`~obelus.ami.AMIProtocol.send_action`
method.  To listen to specific events, call the
:meth:`~obelus.ami.AMIProtocol.register_event_handler` method.

.. note::
   The first action you'll send should be the ``login`` action with
   appropriate ``username`` and ``secret`` headers.

.. note::
   What actions you can emit and what events you can receive depends
   on the Asterisk configuration (especially the manager.conf file).
   Please consult the Asterisk docs.

.. seealso::
   Unofficial `Asterisk manager API <http://www.voip-info.org/wiki/view/Asterisk+manager+API>`_
   documentation at voip-info.org.


Making calls
""""""""""""

The :class:`obelus.ami.CallManager` class helps you originate calls
using an :class:`~obelus.ami.AMIProtocol` instance and track their status
changes.


Asterisk Gateway Interface
--------------------------

The :abbr:`AGI (Asterisk Gateway Interface)` works in reverse.  You cannot
"connect" using the AGI to your Asterisk instance.  Rather, Asterisk will
initiate an AGI communication whenever its dialplan tells it to do so.

AGI is a very simple command / response protocol.  The AGI-implementing
application can only send commands, to which Asterisk replies when it has
finished.  No events cannot be notified.  Furthermore, an AGI communication
happens on a well-defined channel (in the Asterisk sense) and cannot cross
that boundary.

There are several ways an AGI communication can be initiated by Asterisk,
depending on its configuration:

* By executing a script on the filesystem, like a Web server would
  execute a CGI script (hence the name).  The communication is carried
  over stdin and stdout, until either end closes the pipe.  This is
  "traditional" AGI or *AGI* in short.

* By contacting a TCP server listening on a given host and port.  If
  the server accepts the incoming connection, the communication is
  carried over the resulting TCP connection, until the connection is
  terminated by either end.  This is called *"FastAGI"* (by analogy
  with FastCGI, perhaps).

* By encapsulating the AGI communication over a series of AMI events
  and actions.  This is called *"Async AGI"*.

Obelus provides support for FastAGI and Async AGI (using
:class:`~obelus.agi.AsyncAGIExecutor`).


.. _Tornado: http://www.tornadoweb.org/
.. _Tulip: http://code.google.com/p/tulip/
.. _Twisted: http://www.twistedmatrix.com/
