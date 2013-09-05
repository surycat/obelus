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


if __name__ == "__main__":
    import logging
    import signal

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
    # Tulip's logger is very chatty, dampen it
    logging.getLogger('tulip').setLevel('WARNING')

    class CLIProtocol(examplecli.CLIProtocol, FastAGIProtocol):
        pass

    executor = FastAGIExecutor(CLIProtocol)

    loop = tulip.get_event_loop()
    loop.start_serving(executor.make_protocol, args.listen, args.port)
    loop.add_signal_handler(signal.SIGINT, loop.stop)
    loop.run_forever()
