# -*- coding: utf-8 -*-

import contextlib
import textwrap
import unittest

from mock import Mock, ANY

from obelus.agi.asyncagi import AsyncAGIExecutor
from obelus.agi.protocol import (
    AGIProtocol, Response,
    AGICommandFailure, AGIUnknownCommand, AGIForbiddenCommand, AGISyntaxError)
from obelus.agi.session import AGISession
from obelus.ami.protocol import AMIProtocol, ActionError
from obelus.common import Handler
from obelus.test import main, watch_logging


def literal_ami(text):
    text = textwrap.dedent(text.rstrip() + '\n\n')
    if not isinstance(text, bytes):
        text = text.encode('utf-8')
    return text

AMI_GREETING_LINE = b"Asterisk Call Manager/1.4\r\n"

ASYNC_AGI_START = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Start
    Channel: Local/678@default-00000012;2
    Env: agi_request%3A%20async%0Aagi_channel%3A%20Local%2F678%40default-00000012%3B2%0Aagi_language%3A%20en%0Aagi_type%3A%20Local%0Aagi_uniqueid%3A%201377871527.46%0Aagi_version%3A%2011.5.0%2Bpf.xivo.13.16~20130722.141054.2668289%0Aagi_callerid%3A%20unknown%0Aagi_calleridname%3A%20unknown%0Aagi_callingpres%3A%2067%0Aagi_callingani2%3A%200%0Aagi_callington%3A%200%0Aagi_callingtns%3A%200%0Aagi_dnid%3A%20unknown%0Aagi_rdnis%3A%20unknown%0Aagi_context%3A%20default%0Aagi_extension%3A%20678%0Aagi_priority%3A%201%0Aagi_enhanced%3A%200.0%0Aagi_accountcode%3A%20%0Aagi_threadid%3A%20-1257751696%0A%0A
    """)

# Non-ASCII 'Channel', Non-ASCII 'Env'
ASYNC_AGI_START_NON_ASCII = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Start
    Channel: Local/678é@default-00000008;2
    Env: agi_request%3A%20async%0Aagi_channel%3A%20Local%2F678%C3%A9%40default-00000008%3B2%0Aagi_language%3A%20en%0Aagi_type%3A%20Local%0Aagi_uniqueid%3A%201378115103.17%0Aagi_version%3A%2011.5.0%2Bpf.xivo.13.16~20130722.141054.2668289%0Aagi_callerid%3A%20unknown%0Aagi_calleridname%3A%20unknown%0Aagi_callingpres%3A%2067%0Aagi_callingani2%3A%200%0Aagi_callington%3A%200%0Aagi_callingtns%3A%200%0Aagi_dnid%3A%20unknown%0Aagi_rdnis%3A%20unknown%0Aagi_context%3A%20default%0Aagi_extension%3A%20678%C3%A9%0Aagi_priority%3A%201%0Aagi_enhanced%3A%200.0%0Aagi_accountcode%3A%20%0Aagi_threadid%3A%20-1258722448%0A%0A
    """)

# 'Env' lacks the trailing double-EOL
ASYNC_AGI_START_INCOMPLETE = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Start
    Channel: Local/678@default-00000012;2
    Env: agi_request%3A%20async%0A
    """)

ASYNC_AGI_END = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: End
    Channel: Local/678@default-00000012;2
    """)

OTHER_ASYNC_AGI_END = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: End
    Channel: Local/some-unknown-channel
    """)

AGI_ACTION_SUCCESS = literal_ami("""\
    Response: Success
    ActionID: 1
    Message: Added AGI command to queue
    """)

AGI_ACTION_ERROR = literal_ami("""\
    Response: Error
    ActionID: 1
    Message: Channel does not exist.
    """)

# '200 result=0 (foobar) endpos=1234'
ASYNC_AGI_EXEC_1 = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Exec
    Channel: Local/678@default-00000012;2
    CommandID: SOME-COMMAND-ID
    Result: 200%20result%3D0%20%28foobar%29%20endpos%3D1234%0A
    """)

ASYNC_AGI_RESP_1 = Response(result=0, variables={'endpos': '1234'},
                            data='foobar')

# '510 Invalid or unknown command'
ASYNC_AGI_EXEC_2 = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Exec
    Channel: Local/678@default-00000012;2
    CommandID: SOME-COMMAND-ID
    Result: 510%20Invalid%20or%20unknown%20command%0A
    """)

# '520-Invalid command syntax' + continuation
# NOTE: the "Result" value is malformed, there is a missing EOL
# between the usage string and the "520 End of proper usage" line.
ASYNC_AGI_EXEC_3 = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Exec
    Channel: Local/678@default-00000012;2
    CommandID: SOME-COMMAND-ID
    Result: 520-Invalid%20command%20syntax.%20%20Proper%20usage%20follows%3A%0AReturns%20%3Cliteral%3E0%3C%2Fliteral%3E%20if%20%3Creplaceable%3Evariablename%3C%2Freplaceable%3E%20is%20not%20set.%20Returns%20%3Cliteral%3E1%3C%2Fliteral%3E%20if%20%3Creplaceable%3Evariablename%3C%2Freplaceable%3E%20is%20set%20and%20returns%20the%20variable%20in%20parentheses.%0AExample%20return%20code%3A%20200%20result%3D1%20(testvariable)520%20End%20of%20proper%20usage.%0A
    """)

ASYNC_AGI_EXEC_OTHER_COMMAND = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Exec
    Channel: Local/678@default-00000012;2
    CommandID: SOME-OTHER-COMMAND-ID
    Result: 200%20result%3D0%20%28foobar%29%20endpos%3D1234%0A
    """)

ASYNC_AGI_EXEC_OTHER_CHANNEL = literal_ami("""\
    Event: AsyncAGI
    Privilege: agi,all
    SubEvent: Exec
    Channel: Local/some-other-channel
    CommandID: SOME-COMMAND-ID
    Result: 200%20result%3D0%20%28foobar%29%20endpos%3D1234%0A
    """)


class TestHelpers(object):

    def setUp(self):
        def session_factory():
            # Stick the latest created session on this test case instance.
            self.session = Mock(spec_set=AGISession)
            return self.session

        class MyAGIProtocol(AGIProtocol):
            pass
        MyAGIProtocol.session_factory = staticmethod(session_factory)
        self.agi_protocol_factory = MyAGIProtocol
        self.ami = AMIProtocol()
        self.executor = self.make_executor()
        self.session = None

    def make_executor(self):
        return AsyncAGIExecutor(self.agi_protocol_factory)

    def bound_executor(self):
        e = self.executor
        self.ami.line_received(AMI_GREETING_LINE)
        e.bind(self.ami)
        return e

    def feed_ami(self, message):
        lines = message.splitlines(True)
        for line in lines:
            self.ami.line_received(line)

    def assert_one_proto(self, expected_channel_id=None):
        e = self.executor
        self.assertEqual(1, len(e._channels))
        (channel_id, channel), = e._channels.items()
        proto = channel.proto
        if expected_channel_id is not None:
            self.assertEqual(channel_id, expected_channel_id)
            self.assertEqual(proto.env['channel'], expected_channel_id)
        self.assertEqual(proto._state, 'idle')
        # A session was bound to the proto
        session = self.session
        self.assertIsInstance(session, AGISession)
        self.assertEqual(session.proto, proto)
        session.session_established.assert_called_once_with()
        return proto

    def assert_called_once_with_exc(self, callback, exc_class):
        callback.assert_called_once_with(ANY)
        (exc,), _ = callback.call_args
        return exc


class AsyncAGITest(TestHelpers, unittest.TestCase):
    """
    General tests for the Async AGI protocol.
    """

    def test_init(self):
        e = self.executor
        self.assertIs(False, e.is_bound())
        self.assertEqual(0, len(e._channels))
        self.assertIs(self.session, None)

    def test_new_command_id(self):
        def assert_no_dups(ids):
            self.assertEqual(sorted(ids), sorted(set(ids)))
        e = self.executor
        f = self.make_executor()
        e_ids = [e._new_command_id() for i in range(10)]
        f_ids = [f._new_command_id() for i in range(10)]
        assert_no_dups(e_ids)
        assert_no_dups(f_ids)
        assert_no_dups(e_ids + f_ids)

    def test_bind(self):
        e = self.executor
        e.bind(self.ami)
        self.assertIs(True, e.is_bound())
        self.assertRaises(ValueError, e.bind, self.ami)
        self.assertIs(True, e.is_bound())
        self.assertEqual(0, len(e._channels))
        self.assertIs(self.session, None)

    def test_unbind(self):
        e = self.executor
        self.assertRaises(ValueError, e.unbind)
        self.assertIs(False, e.is_bound())
        e.bind(self.ami)
        self.assertIs(True, e.is_bound())
        e.unbind()
        self.assertIs(False, e.is_bound())
        self.assertRaises(ValueError, e.unbind)

    def test_async_agi_start(self):
        e = self.bound_executor()
        self.feed_ami(ASYNC_AGI_START)
        proto = self.assert_one_proto("Local/678@default-00000012;2")
        self.assertEqual(proto.argv, [])
        self.assertEqual(proto.env['threadid'], "-1257751696")
        self.assertEqual(self.session.session_finished.call_count, 0)

    def test_async_agi_start_non_ascii(self):
        e = self.bound_executor()
        self.feed_ami(ASYNC_AGI_START_NON_ASCII)
        proto = self.assert_one_proto("Local/678é@default-00000008;2")
        self.assertEqual(proto.argv, [])
        self.assertEqual(proto.env['threadid'], "-1258722448")
        self.assertEqual(self.session.session_finished.call_count, 0)

    def test_async_agi_start_incomplete(self):
        e = self.bound_executor()
        with watch_logging('obelus.agi', level='WARN') as w:
            self.feed_ami(ASYNC_AGI_START_INCOMPLETE)
        self.assertEqual(0, len(e._channels))
        # XXX should it be None?
        self.assertEqual(self.session.session_established.call_count, 0)
        self.assertEqual(self.session.session_finished.call_count, 0)

    def test_async_agi_end(self):
        e = self.bound_executor()
        self.feed_ami(ASYNC_AGI_START)
        self.assertEqual(1, len(e._channels))
        session = self.session
        self.feed_ami(ASYNC_AGI_END)
        self.assertEqual(0, len(e._channels))
        session.session_established.assert_called_once_with()
        session.session_finished.assert_called_once_with()

    def test_async_agi_end_unknown_channel(self):
        e = self.bound_executor()
        self.feed_ami(ASYNC_AGI_START)
        self.assert_one_proto("Local/678@default-00000012;2")
        with watch_logging('obelus.agi', level='WARN') as w:
            self.feed_ami(OTHER_ASYNC_AGI_END)
        self.assert_one_proto("Local/678@default-00000012;2")
        self.assertEqual(len(w.output), 1)
        self.assertIn("Local/some-unknown-channel", w.output[0])
        self.assertEqual(self.session.session_finished.call_count, 0)


class CommandSendingTest(TestHelpers, unittest.TestCase):
    """
    Tests for sending and matching commands over Async AGI.
    """

    def setUp(self):
        TestHelpers.setUp(self)
        e = self.bound_executor()
        self.feed_ami(ASYNC_AGI_START)
        self.proto = self.assert_one_proto()
        self.ami.write = Mock()
        e._new_command_id = Mock(return_value='SOME-COMMAND-ID')

    def test_send_command(self):
        p = self.proto
        e = self.executor
        ami = self.ami
        h = p.send_command(("set", "variable", "foo", "bar quux"))
        self.assertIsInstance(h, Handler)
        ami.write.assert_called_once_with(ANY)
        (data,), _ = ami.write.call_args
        lines = data.splitlines()
        self.assertEqual(len(lines), 6, lines)
        self.assertIn(b"Channel: Local/678@default-00000012;2", lines)
        self.assertIn(b"Action: AGI", lines)
        self.assertIn(b"ActionID: 1", lines)
        self.assertIn(b'Command: set variable foo "bar quux"', lines)
        self.assertIn(b"CommandID: SOME-COMMAND-ID", lines)
        self.assertEqual(lines[-1], b"")

    def queued_command(self, args):
        p = self.proto
        h = p.send_command(["noop"])
        h.on_result = Mock()
        h.on_exception = Mock()
        # A command is only queued when the "AGI" action gets a successful
        # response.
        self.assertEqual(list(p.channel._commands), [])
        self.feed_ami(AGI_ACTION_SUCCESS)
        self.assertEqual(list(p.channel._commands), ['SOME-COMMAND-ID'])
        return p, h

    def test_command_queued(self):
        p, h = self.queued_command(["noop"])
        self.assertEqual(h.on_result.call_count, 0)
        self.assertEqual(h.on_exception.call_count, 0)

    def test_command_queued_successful(self):
        p, h = self.queued_command(["noop"])
        self.feed_ami(ASYNC_AGI_EXEC_1)
        h.on_result.assert_called_once_with(ASYNC_AGI_RESP_1)
        self.assertEqual(h.on_exception.call_count, 0)
        self.assertEqual(p._state, 'idle')
        self.assertEqual(list(p.channel._commands), [])

    def test_command_queued_failed_1(self):
        p, h = self.queued_command(["noop"])
        self.feed_ami(ASYNC_AGI_EXEC_2)
        self.assertEqual(h.on_result.call_count, 0)
        exc = self.assert_called_once_with_exc(h.on_exception, AGIUnknownCommand)
        self.assertEqual(str(exc), "Invalid or unknown command")
        self.assertEqual(p._state, 'idle')
        self.assertEqual(list(p.channel._commands), [])

    def test_command_queued_failed_2(self):
        p, h = self.queued_command(["noop"])
        self.feed_ami(ASYNC_AGI_EXEC_3)
        self.assertEqual(h.on_result.call_count, 0)
        exc = self.assert_called_once_with_exc(h.on_exception, AGISyntaxError)
        self.assertTrue(str(exc).startswith("Invalid command syntax"),
                        str(exc))
        self.assertEqual(p._state, 'idle')
        self.assertEqual(list(p.channel._commands), [])

    def test_command_queuing_failure(self):
        p = self.proto
        h = p.send_command(["noop"])
        h.on_result = Mock()
        h.on_exception = Mock()
        self.feed_ami(AGI_ACTION_ERROR)
        self.assertEqual(list(p.channel._commands), [])
        self.assertEqual(h.on_result.call_count, 0)
        exc = self.assert_called_once_with_exc(h.on_exception, ActionError)
        self.assertEqual(str(exc), "Channel does not exist.")

    def test_other_command_ignored(self):
        p, h = self.queued_command(["noop"])
        with watch_logging('obelus.agi', level='WARN'):
            self.feed_ami(ASYNC_AGI_EXEC_OTHER_COMMAND)
        self.assertEqual(h.on_result.call_count, 0)
        self.assertEqual(h.on_exception.call_count, 0)
        self.assertEqual(list(p.channel._commands), ['SOME-COMMAND-ID'])

    def test_other_channel_ignored(self):
        p, h = self.queued_command(["noop"])
        with watch_logging('obelus.agi', level='WARN'):
            self.feed_ami(ASYNC_AGI_EXEC_OTHER_CHANNEL)
        self.assertEqual(h.on_result.call_count, 0)
        self.assertEqual(h.on_exception.call_count, 0)
        self.assertEqual(list(p.channel._commands), ['SOME-COMMAND-ID'])

