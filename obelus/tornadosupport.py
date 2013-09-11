

class TornadoAdapter(object):
    """
    Tornado adapter for Obelus protocols (e.g. AMIProtocol, AGIProtocol).

    Pass a *protocol* instance to create the adapter, then call
    :meth:`bind_stream` when you need to wire the protocol to a Tornado
    :class:`~tornado.iostream.IOStream` instance.
    """

    stream = None

    def __init__(self, protocol):
        self.protocol = protocol

    def bind_stream(self, stream):
        """
        Bind the protocol to the given IOStream.  The stream should
        be already connected, as the protocol's connection_made() will
        be called immediately.
        """
        self.stream = stream
        self.stream.read_until_close(self._final_cb, self._streaming_cb)
        self.stream.set_close_callback(self._close_cb)
        self.protocol.connection_made(self)

    def _streaming_cb(self, data):
        if data:
            self.protocol.data_received(data)

    def _final_cb(self, data):
        # This is called when reading is finished, either because
        # of a regular EOF or because of an error.
        self._streaming_cb(data)
        self._close_cb()

    def _close_cb(self, *args):
        if self.stream is not None:
            stream = self.stream
            self.stream = None
            self.protocol.connection_lost(stream.error)

    def write(self, data):
        if self.stream is None:
            raise ValueError("write() on a non-connected protocol")
        self.stream.write(data)

    def close(self):
        if self.stream is not None:
            self.stream.close()


