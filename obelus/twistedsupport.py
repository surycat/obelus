try:
    import twisted
except ImportError:
    twisted = None

if not twisted:
    raise ImportError("Twisted is required for this module to work: "
                      "https://twistedmatrix.com/")

from twisted.internet.protocol import Protocol


class TwistedAdapter(Protocol):
    """
    Twisted adapter for Obelus protocols (e.g. AMIProtocol, AGIProtocol),
    inheriting from twisted.internet.protocol.Protocol.

    Pass a *protocol* instance to create the adapter, which you can
    e.g. return from your Twisted Factory implementation.
    """

    def __init__(self, protocol):
        self.protocol = protocol

    def connectionMade(self):
        self.protocol.connection_made(self)

    def connectionLost(self, failure):
        self.protocol.connection_lost(failure.value)

    def dataReceived(self, data):
        self.protocol.data_received(data)

    # Transport methods
    def write(self, data):
        """
        Write the given *data* bytes on the transport.
        """
        self.transport.write(data)

    def close(self):
        """
        Close the transport's underlying connection.
        """
        self.transport.loseConnection()
