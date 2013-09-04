
import unittest

from obelus.common import LineReceiver
from obelus.test import main


class MockLineReceiver(LineReceiver):
    def __init__(self):
        super(MockLineReceiver, self).__init__()
        self.lines = []

    def line_received(self, line):
        self.lines.append(line)


class LineReceiverTest(unittest.TestCase):
    DATA = b"one line\nanother line\r\nyet another\rtail\n"
    EXPECTED = [b"one line\n", b"another line\r\n", b"yet another\r", b"tail\n"]
    # This can happen if the '\r\n' is split between two data_received()
    # calls.
    EXPECTED_ALT = [b"one line\n", b"another line\r", b"yet another\r", b"tail\n"]

    def test_receive_large(self):
        lr = MockLineReceiver()
        lr.data_received(self.DATA)
        self.assertEqual(lr.lines, self.EXPECTED)

    def test_receive_bytewise(self):
        lr = MockLineReceiver()
        for i in range(len(self.DATA)):
            lr.data_received(self.DATA[i:i + 1])
        self.assertIn(lr.lines, (self.EXPECTED, self.EXPECTED_ALT))

    def test_receive_chunkwise(self):
        for chunk_size in range(2, 20):
            chunks = [self.DATA[i:i + chunk_size]
                      for i in range(0, len(self.DATA), chunk_size)]
            lr = MockLineReceiver()
            for chunk in chunks:
                lr.data_received(chunk)
            self.assertIn(lr.lines, (self.EXPECTED, self.EXPECTED_ALT))

    def test_receive_cr_ending_lines(self):
        # '\r'-ending lines do not wait for the next byte to
        # come before they are notified.
        lr = MockLineReceiver()
        lr.data_received(b'foo\r')
        self.assertEqual(lr.lines, [b'foo\r'])
        lr.lines = []
        # '\n' gets eaten because of previous '\r'
        lr.data_received(b'\n')
        self.assertEqual(lr.lines, [])
        lr.data_received(b'\n\r')
        self.assertEqual(lr.lines, [b'\n', b'\r'])
        lr.lines = []
        # First '\n' gets eaten because of previous '\r'
        lr.data_received(b'\n\na\r\nb\r')
        self.assertEqual(lr.lines, [b'\n', b'a\r\n', b'b\r'])
        lr.lines = []
        lr.data_received(b'\rc\n')
        self.assertEqual(lr.lines, [b'\r', b'c\n'])


if __name__ == "__main__":
    main()
