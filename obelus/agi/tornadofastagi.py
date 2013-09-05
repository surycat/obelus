"""
FastAGI adapter for the Tornado network programming framework.
"""

try:
    import tornado
except ImportError:
    tornado = None

if not tornado:
    raise ImportError("tornado is required for this module to work: "
                      "http://www.tornadoweb.org/")

from tornado import netutil
try:
    from tornado.tcpserver import TCPServer
except ImportError:
    from tornado.netutil import TCPServer

from ..tornadosupport import TornadoAdapter


class FastAGIServer(TCPServer):
    """
    A TCPServer subclass that will delegate all incoming connections
    to a FastAGIExecutor instance.
    """

    def __init__(self, executor, *args, **kwargs):
        TCPServer.__init__(self, *args, **kwargs)
        self.executor = executor

    def handle_stream(self, stream, remote_addr):
        proto = self.executor.make_protocol()
        adapter = TornadoAdapter(proto)
        adapter.bind_stream(stream)


if __name__ == "__main__":
    from tornado.ioloop import IOLoop

    from .fastagi import FastAGIProtocol, FastAGIExecutor, TCP_PORT
    from .session import AGISession
    from . import examplecli

    parser = examplecli.create_parser(
        description="Tornado-based FastAGI server example")
    parser.add_argument('-p', '--port', type=int, default=TCP_PORT,
                        help='port to listen on')
    parser.add_argument('-L', '--listen', default='127.0.0.1',
                        help='address to listen on')

    options, args = examplecli.parse_args(parser)

    loop = IOLoop.instance()

    class CLIProtocol(examplecli.CLIProtocol, FastAGIProtocol):
        pass

    executor = FastAGIExecutor(CLIProtocol)
    server = FastAGIServer(executor, io_loop=loop)
    server.listen(args.port, args.listen)

    try:
        loop.start()
    except KeyboardInterrupt:
        pass
