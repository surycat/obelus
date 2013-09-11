"""
Adapter for the Twisted network programming framework.
"""

try:
    import twisted
except ImportError:
    twisted = None

if not twisted:
    raise ImportError("Twisted is required for this module to work: "
                      "https://twistedmatrix.com/")

from twisted.internet.protocol import Factory

from ..twistedsupport import TwistedAdapter


if __name__ == "__main__":
    import logging

    from twisted.internet import reactor
    from twisted.internet.endpoints import TCP4ClientEndpoint
    from twisted.internet.error import ReactorNotRunning

    from . import examplecli

    parser = examplecli.create_parser(
        description="Twisted-based AMI client example")

    options, args = examplecli.parse_args(parser)

    log = logging.getLogger(__name__)

    # connectProtocol() appeared in 13.1, but we want to support at least 11.0+.
    # (endpoints appeared in 10.1).

    class CLIFactory(Factory):
        def buildProtocol(self, addr):
            proto = examplecli.CLIProtocol(reactor, options)
            return TwistedAdapter(proto)

    endpoint = TCP4ClientEndpoint(reactor, options.host, options.port)
    d = endpoint.connect(CLIFactory())

    def connection_failed(failure):
        log.error("Connection to %r failed: %s",
                  (options.host, options.port), failure)
        reactor.stop()

    # Hack reactor.stop() to mute errors on double stop
    _old_reactor_stop = reactor.stop
    def _reactor_stop():
        try:
            _old_reactor_stop()
        except ReactorNotRunning:
            pass
    reactor.stop = _reactor_stop

    d.addErrback(connection_failed)
    reactor.run()
