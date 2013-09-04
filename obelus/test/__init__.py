
import collections
import contextlib
import logging
import sys
from unittest.main import TestProgram
try:
    from unittest import mock
except ImportError:
    import mock
# Allow for e.g. "from mock import Mock"
sys.modules['mock'] = mock


def main():
    """
    Execute the test suite from the current __main__ module.
    """
    TestProgram()


class LoggingWatcher(collections.namedtuple("Watcher", ["records", "output"])):
    pass


class CapturingHandler(logging.Handler):
    """
    A logging handler capturing all (raw and formatted) logging output.
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.watcher = LoggingWatcher([], [])

    def flush(self):
        pass

    def emit(self, record):
        self.watcher.records.append(record)
        msg = self.format(record)
        self.watcher.output.append(msg)


LOGGING_FORMAT = "%(levelname)s:%(name)s:%(message)s"

@contextlib.contextmanager
def watch_logging(logger_name=None, level=logging.INFO):
    """
    Setup logging to enable log capturing on the given logger
    (or the root logger if None).
    Note that all descendents of this logger will also get captured.
    """
    if isinstance(logger_name, logging.Logger):
        logger = logger_name
    else:
        logger = logging.getLogger(logger_name)
    formatter = logging.Formatter(LOGGING_FORMAT)
    handler = CapturingHandler()
    handler.setFormatter(formatter)
    old_handlers = logger.handlers[:]
    old_level = logger.level
    old_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    try:
        yield handler.watcher
    finally:
        logger.handlers = old_handlers
        logger.propagate = old_propagate
        logger.setLevel(old_level)
