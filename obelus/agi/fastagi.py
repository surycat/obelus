import weakref

from .protocol import ProtocolAGIChannel


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
            proto.close_connection()
            proto.connection_lost(None)

