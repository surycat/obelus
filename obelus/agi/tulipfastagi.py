"""
Adapter for the asyncio network programming framework.
"""

try:
    import asyncio
except ImportError:
    try:
        import tulip as asyncio
    except ImportError:
        asyncio = None

if not asyncio:
    raise ImportError("asyncio is required for this module to work: "
                      "https://pypi.python.org/pypi/asyncio")


if __name__ == "__main__":
    import logging
    import signal

    from .fastagi import FastAGIProtocol, FastAGIExecutor, TCP_PORT
    from .session import AGISession
    from . import examplecli

    parser = examplecli.create_parser(
        description="asyncio-based FastAGI server example")
    parser.add_argument('-p', '--port', type=int, default=TCP_PORT,
                        help='port to listen on')
    parser.add_argument('-L', '--listen', default='127.0.0.1',
                        help='address to listen on')

    options, args = examplecli.parse_args(parser)
    # asyncio's logger is very chatty, dampen it
    logging.getLogger(asyncio.__name__).setLevel('WARNING')

    class CLIProtocol(examplecli.CLIProtocol, FastAGIProtocol):
        pass

    executor = FastAGIExecutor(CLIProtocol)

    loop = asyncio.get_event_loop()
    try:
        loop.create_server(executor.make_protocol, args.listen, args.port)
    except AttributeError:
        # Old Tulip versions
        loop.start_serving(executor.make_protocol, args.listen, args.port)
    loop.add_signal_handler(signal.SIGINT, loop.stop)
    loop.run_forever()
