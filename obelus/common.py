
import functools
import logging


class Handler(object):
    """
    A Handler holds callbacks which will be called when an ongoing
    operation terminates.  Also known as Future, Promise, Deferred, etc.

    Generally, you won't create Handler objects yourself.  Instead,
    a producer will create it for you, and you will set the
    :attr:`on_result` and :attr:`on_exception` attributes to be
    notified of the output of the operation.
    """

    _result_cb = None
    _exception_cb = None

    _triggered = False

    @property
    def on_result(self):
        """
        Success callback. Will be called with the handler's result if
        the underlying operation was successful.
        """
        return self._result_cb

    @on_result.setter
    def on_result(self, cb):
        if self._result_cb is not None:
            raise ValueError("on_result already set, cannot override")
        if not callable(cb):
            raise TypeError("on_result should be callable, got %r"
                            % type(cb))
        self._result_cb = cb

    @property
    def on_exception(self):
        """
        Failure callback. Will be called with the handler's exception if
        the underlying operation failed.
        """
        return self._exception_cb

    @on_exception.setter
    def on_exception(self, cb):
        if self._exception_cb is not None:
            raise ValueError("on_exception already set, cannot override")
        if not callable(cb):
            raise TypeError("on_exception should be callable, got %r"
                            % type(cb))
        self._exception_cb = cb

    def set_result(self, result):
        if self._triggered:
            raise RuntimeError("Cannot trigger handler a second time")
        self._triggered = True
        if self._result_cb is not None:
            self._result_cb(result)

    def set_exception(self, exc):
        if self._triggered:
            raise RuntimeError("Cannot trigger handler a second time")
        self._triggered = True
        if self._exception_cb is None:
            raise exc
        else:
            self._exception_cb(exc)

    @classmethod
    def aggregate(cls, handlers):
        """
        Return a new Handler which will trigger when all the given
        handlers have successfully fired, or when one of them fails.
        """
        result_handler = cls()
        n = len(handlers)
        results = [None] * n
        pending = set(range(n))
        def _on_result(i, res):
            if not result_handler._triggered:
                pending.remove(i)
                results[i] = res
                if not pending:
                    result_handler.set_result(results)
        def _on_exception(exc):
            if not result_handler._triggered:
                result_handler.set_exception(exc)
        for i, handler in enumerate(handlers):
            handler.on_result = functools.partial(_on_result, i)
            handler.on_exception = _on_exception
        return result_handler


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
        Call this when some *data* (a bytestring) is received.
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
