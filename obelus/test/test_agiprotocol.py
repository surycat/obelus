# -*- coding: utf-8 -*-

import contextlib
import textwrap
import unittest

from mock import Mock, ANY

from obelus.agi.protocol import (
    AGIProtocol, ProtocolAGIChannel, Response,
    AGICommandFailure, AGIUnknownCommand, AGIForbiddenCommand, AGISyntaxError)
from obelus.common import Handler
from obelus.test import main, watch_logging


def literal_message(text):
    msg = textwrap.dedent(text)
    if not isinstance(msg, bytes):
        # Python 3
        msg = msg.encode('utf-8')
    return msg


HEADER = literal_message("""\
    agi_request: /root/agi_hello.sh
    agi_channel: Local/12345@default-0000000d;2
    agi_language: en
    agi_type: Local
    agi_uniqueid: 1377869716.36
    agi_version: 11.5.0+pf.xivo.13.16~20130722.141054.2668289
    agi_callerid: unknown
    agi_calleridname: unknown
    agi_callingpres: 67
    agi_callingani2: 0
    agi_callington: 0
    agi_callingtns: 0
    agi_dnid: unknown
    agi_rdnis: unknown
    agi_context: default
    agi_extension: 12345
    agi_priority: 1
    agi_enhanced: 0.0
    agi_accountcode:
    agi_threadid: -1257116816
    """)

AGI_ENV = {
    'request': '/root/agi_hello.sh',
    'channel': 'Local/12345@default-0000000d;2',
    'language': 'en',
    'type': 'Local',
    'uniqueid': '1377869716.36',
    'version': '11.5.0+pf.xivo.13.16~20130722.141054.2668289',
    'callerid': 'unknown',
    'calleridname': 'unknown',
    'callingpres': '67',
    'callingani2': '0',
    'callington': '0',
    'callingtns': '0',
    'dnid': 'unknown',
    'rdnis': 'unknown',
    'context': 'default',
    'extension': '12345',
    'priority': '1',
    'enhanced': '0.0',
    'accountcode': '',
    'threadid': '-1257116816',
    }


class AGIProtocolTest(unittest.TestCase):

    def setUp(self):
        self.channel = ProtocolAGIChannel()
        self.proto = AGIProtocol(self.channel)

    def check_header_parsing(self, header, expected_env, expected_args):
        p = self.proto
        for line in header.splitlines(True):
            p.line_received(line)
            self.assertEqual(p._state, 'init')
        p.line_received(b'\n')
        self.assertEqual(p._state, 'idle')
        self.assertEqual(p.env, expected_env)
        self.assertEqual(p.argv, expected_args)

    def proto_idle(self):
        p = self.proto
        p.data_received(HEADER + b"\n")
        self.assertEqual(p._state, 'idle')
        p.channel.write = Mock()
        return p

    def assert_called_once_with_exc(self, mock, exc_class):
        mock.assert_called_once_with(ANY)
        (exc,), _ = mock.call_args
        self.assertIsInstance(exc, exc_class)
        return exc

    @contextlib.contextmanager
    def sending_command(self, args=None):
        p = self.proto
        h = p.send_command(args or ("foo",))
        h.on_result = Mock()
        h.on_exception = Mock()
        yield h

    def test_header_parsing(self):
        self.check_header_parsing(HEADER, AGI_ENV, [])

    def test_header_parsing_with_args(self):
        header = HEADER + literal_message("""\
            agi_arg_1: toto
            agi_arg_2: héhé
            """)
        self.check_header_parsing(header, AGI_ENV, ['toto', 'héhé'])

    def test_parse_result(self):
        f = self.proto._parse_result
        self.assertEqual(f("result=-1"), (-1, {}, None))
        self.assertEqual(f("result=1 endpos=1234"),
                         (1, {'endpos': '1234'}, None))
        self.assertEqual(f("result=0 (foobar)"),
                         (0, {}, "foobar"))
        self.assertEqual(f("result=1 (foobar) endpos=1234"),
                         (1, {'endpos': '1234'}, "foobar"))
        self.assertEqual(f("result=0 (foo quux bar)"),
                         (0, {}, "foo quux bar"))
        self.assertEqual(f("result=1 (foo quux bar) endpos=1234"),
                         (1, {'endpos': '1234'}, "foo quux bar"))

    def test_line_received_when_idle(self):
        p = self.proto_idle()
        # Empty lines are simply ignored, other ones are logged
        p.line_received(b"\n")
        self.assertEqual(p._state, "idle")
        with watch_logging('obelus.agi', level='WARN') as w:
            p.line_received(b"some unexpected data\n")
            self.assertEqual(p._state, "idle")
        self.assertEqual(len(w.output), 1)
        self.assertIn("some unexpected data", w.output[0])

    def test_send_command_invalid(self):
        # Invalid characters in args
        p = self.proto_idle()
        with self.assertRaises(ValueError):
            p.send_command(("foo", "\0"))
        with self.assertRaises(ValueError):
            p.send_command(("foo", "\n"))
        self.assertEqual(0, p.channel.write.call_count)

    def test_send_command_simple_tuple(self):
        p = self.proto_idle()
        h = p.send_command(("set", "variable", "foo", "bar"))
        p.channel.write.assert_called_once_with(b'set variable foo bar\n')
        self.assertIsInstance(h, Handler)

    def test_send_command_simple_list(self):
        p = self.proto_idle()
        h = p.send_command(["set", "variable", "foo", "bar"])
        p.channel.write.assert_called_once_with(b'set variable foo bar\n')
        self.assertIsInstance(h, Handler)

    def test_send_command_escaping_1(self):
        p = self.proto_idle()
        p.send_command(("set", "variable", "some\tspaced data", "bar"))
        p.channel.write.assert_called_once_with(
            b'set variable "some\tspaced data" bar\n')

    def test_send_command_escaping_2(self):
        p = self.proto_idle()
        p.send_command(("set", "variable", 'some"quoted"\\data', "bar"))
        p.channel.write.assert_called_once_with(
            b'set variable "some\\"quoted\\"\\\\data" bar\n')

    def test_send_command_escaping_3(self):
        p = self.proto_idle()
        p.send_command(("say", "alpha", "HELLO WORLD", ""))
        p.channel.write.assert_called_once_with(b'say alpha "HELLO WORLD" ""\n')

    def test_send_command_not_idle(self):
        p = self.proto_idle()
        p.send_command(("foo",))
        with self.assertRaises(RuntimeError):
            p.send_command(("bar",))
        self.assertEqual(p._state, 'awaiting-response')
        p.channel.write.assert_called_once_with(b"foo\n")

    def test_successful_response(self):
        p = self.proto_idle()
        with self.sending_command() as h:
            p.line_received(b"200 result=0 (foobar) endpos=1234\n")
            self.assertEqual(p._state, 'idle')
            h.on_result.assert_called_once_with(
                Response(result=0, variables={'endpos': '1234'}, data='foobar'))
            self.assertEqual(h.on_exception.call_count, 0)

    def test_error_response_200(self):
        p = self.proto_idle()
        with self.sending_command() as h:
            p.line_received(b"200 result=-1\n")
            self.assertEqual(p._state, 'idle')
            self.assertEqual(h.on_result.call_count, 0)
            self.assert_called_once_with_exc(h.on_exception, AGICommandFailure)

    def test_error_response_510(self):
        p = self.proto_idle()
        with self.sending_command() as h:
            p.line_received(b"510 some message\n")
            self.assertEqual(p._state, 'idle')
            self.assertEqual(h.on_result.call_count, 0)
            exc = self.assert_called_once_with_exc(h.on_exception, AGIUnknownCommand)
            self.assertEqual(str(exc), "some message")

    def test_error_response_511(self):
        p = self.proto_idle()
        with self.sending_command() as h:
            p.line_received(b"511 some other message\n")
            self.assertEqual(p._state, 'idle')
            self.assertEqual(h.on_result.call_count, 0)
            exc = self.assert_called_once_with_exc(h.on_exception, AGIForbiddenCommand)
            self.assertEqual(str(exc), "some other message")

    def test_error_response_520(self):
        p = self.proto_idle()
        with self.sending_command() as h:
            p.line_received(b"520 Invalid command syntax.  Proper usage not available.\n")
            self.assertEqual(p._state, 'idle')
            self.assertEqual(h.on_result.call_count, 0)
            exc = self.assert_called_once_with_exc(h.on_exception, AGISyntaxError)
            self.assertEqual(str(exc), "Invalid command syntax.  Proper usage not available.")

    def test_error_response_520_multiline(self):
        p = self.proto_idle()
        with self.sending_command() as h:
            p.line_received(
                b"520-Invalid command syntax.  Proper usage follows:\n")
            p.line_received(
                b"Returns <literal>0</literal> if <replaceable>variablename"
                b"</replaceable> is not set. Returns <literal>1</literal> "
                b"if <replaceable>variablename</replaceable> is set and "
                b"returns the variable in parentheses.\n")
            # The Unicode replacement character (U+FFFD) actually appears
            # in a AGI debug trace on the Asterisk command line. Not sure
            # why, but it's probably worth testing.
            p.line_received(
                b"Example return code: 200 result=1 (testvariable)\xef\xbf\xbd\n")
            self.assertNotEqual(p._state, 'idle')
            p.line_received(
                b"520 End of proper usage.\n")
            self.assertEqual(p._state, 'idle')
            exc = self.assert_called_once_with_exc(h.on_exception, AGISyntaxError)
            self.assertEqual(str(exc), textwrap.dedent("""\
                Invalid command syntax.  Proper usage follows:
                Returns <literal>0</literal> if <replaceable>variablename</replaceable> is not set. Returns <literal>1</literal> if <replaceable>variablename</replaceable> is set and returns the variable in parentheses.
                Example return code: 200 result=1 (testvariable)�
                """))

    def test_multiple_commands(self):
        p = self.proto_idle()
        with self.sending_command(("foo",)) as h:
            p.line_received(b"200 result=0\n")
            h.on_result.assert_called_once_with(
                Response(result=0, variables={}, data=None))
        p.channel.write.assert_called_once_with(b"foo\n")
        with self.sending_command(("bar", "quux")) as h:
            p.line_received(b"200 result=1\n")
            h.on_result.assert_called_once_with(
                Response(result=1, variables={}, data=None))
        p.channel.write.assert_called_with(b"bar quux\n")
        self.assertEqual(p._state, 'idle')
