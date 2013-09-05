
import logging


class Handler(object):

    # User-overridable attributes
    on_result = None
    on_exception = None

    _cancelled = False
    _triggered = False

    def cancel(self):
        """
        Cancel this handler.
        TODO clarify semantics -- is this useful?
        """
        self._cancelled = True
        self._proto._cancel_action(self)

    def _on_result(self, result):
        if self._cancelled:
            return
        if self._triggered:
            raise RuntimeError("Cannot trigger handler a second time")
        self._triggered = True
        if self.on_result is not None:
            self.on_result(result)

    def _on_exception(self, exc):
        if self._cancelled:
            return
        if self._triggered:
            raise RuntimeError("Cannot trigger handler a second time")
        self._triggered = True
        if self.on_exception is None:
            raise exc
        else:
            self.on_exception(exc)


class LineReceiver(object):
    """
    A base protocol class turning incoming data into distinct lines.
    The `line_received()` method must be defined in order to receive
    individual lines.
    """

    _chunks = None
    logger = logging.getLogger(__name__)

    def data_received(self, data):
        """
        Call this when some data is received.
        """
        if self._chunks is None:
            self._chunks = []
            self._eat_lf = False
        if self._chunks:
            chunks = self._chunks[:-1]
            parts = (self._chunks[-1] + data).splitlines(True)
        else:
            if self._eat_lf and data.startswith(b'\n'):
                data = data[1:]
            self._eat_lf = False
            chunks = []
            parts = data.splitlines(True)
        if len(parts) <= 1 and not data.endswith((b'\r', b'\n')):
            # No new line, just buffer received data
            self._chunks.append(data)
            return
        # First part is the tail of a buffered line
        first_part = parts[0]
        line = b''.join(chunks) + first_part
        last_line = line
        self.line_received(line)
        self._chunks[:] = []
        if len(parts) > 1:
            # Intermediate parts are standalone lines
            for p in parts[1:-1]:
                self.line_received(p)
            # Last part can be an in-progress or complete line
            last_part = parts[-1]
            if last_part.endswith((b'\r', b'\n')):
                last_line = last_part
                self.line_received(last_part)
            else:
                last_line = b''
                self._chunks.append(last_part)
        # Instead of buffering when we receive a line
        # ending with '\r', notify it immediately and swallow the
        # following '\n' later (if any).
        if last_line.endswith(b'\r'):
            self._eat_lf = True
