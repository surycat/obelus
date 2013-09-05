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

    from . import examplecli

    parser = examplecli.create_parser(
        description="Tulip-based AMI client example")

    options, args = examplecli.parse_args(parser)

    # Tulip's logger is very chatty, dampen it
    logging.getLogger('tulip').setLevel('WARNING')
    log = logging.getLogger(__name__)

    loop = tulip.get_event_loop()
    proto = examplecli.CLIProtocol(loop, options)
    fut = tulip.async(loop.create_connection(lambda: proto,
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
