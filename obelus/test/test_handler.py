
import unittest

from mock import Mock

from obelus.common import Handler
from . import main


class HandlerTest(unittest.TestCase):

    def test_set_on_result(self):
        h = Handler()
        self.assertIs(h.on_result, None)
        with self.assertRaises(TypeError):
            # Not a callable
            h.on_result = object()
        cb = h.on_result = Mock()
        with self.assertRaises(ValueError):
            # Cannot rebind
            h.on_result = Mock()
        self.assertIs(h.on_result, cb)

    def test_set_on_exception(self):
        h = Handler()
        self.assertIs(h.on_exception, None)
        with self.assertRaises(TypeError):
            # Not a callable
            h.on_exception = object()
        cb = h.on_exception = Mock()
        with self.assertRaises(ValueError):
            # Cannot rebind
            h.on_exception = Mock()
        self.assertIs(h.on_exception, cb)

    def test_set_result_after_callbacks(self):
        h = Handler()
        cb = h.on_result = Mock()
        eb = h.on_exception = Mock()
        h.set_result(5)
        cb.assert_called_once_with(5)
        self.assertEqual(eb.call_count, 0)

    def test_set_exception_after_callbacks(self):
        h = Handler()
        exc = ZeroDivisionError()
        cb = h.on_result = Mock()
        eb = h.on_exception = Mock()
        h.set_exception(exc)
        eb.assert_called_once_with(exc)
        self.assertEqual(cb.call_count, 0)

    def test_set_result_before_callbacks(self):
        h = Handler()
        h.set_result(5)
        with self.assertRaises(NotImplementedError):
            h.on_result = Mock()
        with self.assertRaises(NotImplementedError):
            h.on_exception = Mock()

    def test_set_exception_before_callbacks(self):
        h = Handler()
        exc = ZeroDivisionError()
        with self.assertRaises(ZeroDivisionError):
            h.set_exception(exc)
        with self.assertRaises(NotImplementedError):
            h.on_result = Mock()
        with self.assertRaises(NotImplementedError):
            h.on_exception = Mock()

    def test_set_result_twice(self):
        h = Handler()
        cb = h.on_result = Mock()
        h.set_result(5)
        with self.assertRaises(RuntimeError):
            h.set_result(6)
        with self.assertRaises(RuntimeError):
            h.set_exception(ZeroDivisionError())
        self.assertEqual(cb.call_count, 1)

    def test_set_result_exception(self):
        h = Handler()
        cb = h.on_result = Mock()
        with self.assertRaises(TypeError):
            h.set_result(ZeroDivisionError())
        self.assertEqual(cb.call_count, 0)

    def test_set_exception_twice(self):
        h = Handler()
        eb = h.on_exception = Mock()
        exc = ZeroDivisionError()
        h.set_exception(exc)
        with self.assertRaises(RuntimeError):
            h.set_exception(exc)
        with self.assertRaises(RuntimeError):
            h.set_result(6)
        self.assertEqual(eb.call_count, 1)

    def test_set_exception_non_exception(self):
        h = Handler()
        eb = h.on_exception = Mock()
        with self.assertRaises(TypeError):
            h.set_exception(5)
        self.assertEqual(eb.call_count, 0)



if __name__ == "__main__":
    main()
