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


class TulipAMIAdapter(tulip.Protocol):
    """
    Adapter mixin to make an AMI protocol class usable as a Tulip
    Protocol.  Use in this way:

        class MyAMIProtocol(AMIProtocol, TulipAMIAdapter):
            pass

    (the inheritance order is important! TulipAMIAdapter should be
     specified last)
    """

    def connection_made(self, transport):
        self.transport = transport
        super(TulipAMIAdapter, self).connection_made(transport)

    def write(self, data):
        self.transport.write(data)

    def close_connection(self):
        self.transport.close()


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

    class CLIProtocol(examplecli.CLIProtocol, TulipAMIAdapter):
        pass

    loop = tulip.get_event_loop()
    proto = CLIProtocol(loop, options)
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
