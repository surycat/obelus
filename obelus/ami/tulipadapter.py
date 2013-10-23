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

    from . import examplecli

    parser = examplecli.create_parser(
        description="asyncio-based AMI client example")

    options, args = examplecli.parse_args(parser)

    # asyncio's logger is very chatty, dampen it
    logging.getLogger(asyncio.__name__).setLevel('WARNING')
    log = logging.getLogger(__name__)

    loop = asyncio.get_event_loop()
    proto = examplecli.CLIProtocol(loop, options)
    fut = asyncio.async(loop.create_connection(lambda: proto,
                                               options.host, options.port))
    def cb(fut):
        exc = fut.exception()
        if exc is not None:
            log.error("Connection to %r failed: %s",
                      (options.host, options.port), exc)
            loop.stop()
    fut.add_done_callback(cb)

    loop.add_signal_handler(signal.SIGINT, loop.stop)
    loop.run_forever()
