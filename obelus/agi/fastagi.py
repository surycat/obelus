import weakref

from .protocol import AGIProtocol, ProtocolAGIChannel


TCP_PORT = 4573


class FastAGIExecutor(object):

    def __init__(self, protocol_factory):
        self._conns = weakref.WeakSet()
        self.protocol_factory = protocol_factory

    def make_protocol(self):
        proto = self.protocol_factory(ProtocolAGIChannel())
        self._conns.add(proto)
        return proto

    def close(self):
        for proto in list(self._conns):
            proto.transport.close()
            proto.connection_lost(None)


class FastAGIProtocol(AGIProtocol):

    def connection_made(self, transport):
        super(FastAGIProtocol, self).connection_made(transport)
        self.bind_session()

    def connection_lost(self, exc):
        super(FastAGIProtocol, self).connection_lost(exc)
        self.unbind_session()
