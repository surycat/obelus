
class _BaseTornadoAdapter(object):
    """
    Base Tornado adapter for protocol classes.
    """

    _stream = None

    def bind_stream(self, stream):
        """
        Bind this protocol to the given IOStream.  The stream should
        be already connected, as connection_made() will be called immediately.
        """
        self._stream = stream
        self._stream.read_until_close(self._final_cb, self._streaming_cb)
        self._stream.set_close_callback(self._close_cb)
        self.connection_made(stream)

    def _streaming_cb(self, data):
        if data:
            self.data_received(data)

    def _final_cb(self, data):
        # This is called when reading is finished, either because
        # of a regular EOF or because of an error.
        self._streaming_cb(data)
        self._close_cb()

    def _close_cb(self, *args):
        if self._stream is not None:
            stream = self._stream
            self._stream = None
            self.connection_lost(stream.error)

    def write(self, data):
        if self._stream is None:
            raise ValueError("write() on a non-connected protocol")
        self._stream.write(data)

    def close_connection(self):
        if self._stream is not None:
            self._stream.close()
