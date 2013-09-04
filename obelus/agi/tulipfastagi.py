"""
Adapter for the Tulip network programming framework.
"""

try:
    import tulip
except ImportError:
    tulip = None

if not tulip:
    raise ImportError("tulip is required for this module to work: "
                      "http://code.google.com/p/tulip/")


class TulipFastAGIAdapter(tulip.Protocol):
    """
    Adapter mixin to make an AGI protocol class usable as a Tulip
    Protocol.  Use in this way:

        class MyAMIProtocol(AGIProtocol, TulipFastAGIAdapter):
            pass

    (the inheritance order is important! TulipFastAGIAdapter should be
     specified last)
    """

    def connection_made(self, transport):
        self.transport = transport
        super(TulipFastAGIAdapter, self).connection_made(transport)
        self.bind_session()

    def connection_lost(self, exc):
        self.unbind_session()

    def write(self, data):
        self.transport.write(data)

    def close_connection(self):
        self.transport.close()


if __name__ == "__main__":
    import logging
    import signal

    from .fastagi import FastAGIExecutor, TCP_PORT
    from .protocol import AGIProtocol
    from .session import AGISession
    from . import examplecli

    parser = examplecli.create_parser(
        description="Tornado-based FastAGI server example")
    parser.add_argument('-p', '--port', type=int, default=TCP_PORT,
                        help='port to listen on')
    parser.add_argument('-L', '--listen', default='127.0.0.1',
                        help='address to listen on')

    options, args = examplecli.parse_args(parser)
    # Tulip's logger is very chatty, dampen it
    logging.getLogger('tulip').setLevel('WARNING')

    class CLIProtocol(examplecli.CLIProtocol, TulipFastAGIAdapter):
        pass

    executor = FastAGIExecutor(CLIProtocol)

    loop = tulip.get_event_loop()
    loop.start_serving(executor.make_protocol, args.listen, args.port)
    loop.add_signal_handler(signal.SIGINT, loop.stop)
    loop.run_forever()
