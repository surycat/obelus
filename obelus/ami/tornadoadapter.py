"""
AMI adapter for the Tornado network programming framework.
"""

try:
    import tornado
except ImportError:
    tornado = None

if not tornado:
    raise ImportError("tornado is required for this module to work: "
                      "http://www.tornadoweb.org/")

from ..tornadosupport import _BaseTornadoAdapter
from .protocol import AMIProtocol


class TornadoAMIAdapter(_BaseTornadoAdapter):
    """
    Adapter mixin to make an AMI protocol class compatible with Tornado
    streams.  Use in this way:

        class MyAMIProtocol(AMIProtocol, TornadoAdapter):
            pass

    (the inheritance order is important! TornadoAdapter should be
     specified last)

    At runtime, connect an IOStream to your Asterisk Manager endpoint,
    and call the protocol instance's bind_stream() method.
    """
    def connection_made(self, transport=None):
        """Placeholder for multiple inheritance."""

    def connection_lost(self, exc):
        """Placeholder for multiple inheritance."""


if __name__ == "__main__":
    import logging
    import socket

    from tornado.ioloop import IOLoop
    from tornado.iostream import IOStream

    from . import examplecli

    parser = examplecli.create_parser(
        description="Tornado-based AMI client example")

    options, args = examplecli.parse_args(parser)

    log = logging.getLogger(__name__)

    class CLIProtocol(examplecli.CLIProtocol, TornadoAMIAdapter):
        pass

    loop = IOLoop.instance()
    proto = CLIProtocol(loop, options)

    stream = IOStream(socket.socket(), loop)
    stream.connect((options.host, options.port),
                   lambda: proto.bind_stream(stream))

    try:
        loop.start()
    except KeyboardInterrupt:
        pass
