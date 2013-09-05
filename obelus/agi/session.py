
from functools import partial
import logging

from ..common import Handler


class AGISession(object):

    proto = None
    logger = logging.getLogger(__name__)

    def session_established(self):
        """
        Called when the AGI session is established.
        """

    def session_finished(self):
        """
        Called when the AGI session is torn down.
        """

    def run_coroutine(self, gen):
        handler = next(gen)
        self._bind_coroutine_handler(gen, handler)

    def _bind_coroutine_handler(self, gen, handler):
        if not isinstance(handler, Handler):
            raise TypeError(handler.__class__)
        handler.on_result = partial(self._on_coroutine_result, gen, True)
        handler.on_exception = partial(self._on_coroutine_result, gen, False)

    def _on_coroutine_result(self, gen, is_success, result):
        try:
            if is_success:
                handler = gen.send(result)
            else:
                handler = gen.throw(result)
        except StopIteration:
            gen.close()
        else:
            self._bind_coroutine_handler(gen, handler)
