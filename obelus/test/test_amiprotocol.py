
from collections import OrderedDict
import textwrap
import unittest

from mock import Mock, ANY

from obelus.ami.protocol import (
    BaseAMIProtocol, AMIProtocol, Event, Response, EventList, ActionError)
from obelus.common import Handler
from obelus.test import main


def literal_message(text):
    return textwrap.dedent(text.rstrip() + '\n\n').encode('utf-8')

EVENT_HANGUP = literal_message("""\
    Event: Hangup
    Privilege: call,all
    Channel: SIP/0004F2060EB4-00000000
    Uniqueid: 1283174108.0
    """)

CORE_SETTINGS_RESPONSE = literal_message("""\
    Response: Success
    AMIversion: 1.1
    AsteriskVersion: 1.8.13.0~dfsg-1
    """)

ERROR_RESPONSE = literal_message("""\
    Response: Error
    ActionID: 4444
    Message: Invalid/unknown command: xyzzy. (blabla)
    """)

LOGOFF_RESPONSE = literal_message("""\
    Response: Goodbye
    Message: Thanks for all the fish.
    """)

CORE_SHOW_VERSION_RESPONSE = literal_message("""\
    Response: Follows
    Privilege: Command
    ActionID: DEF.768
    Asterisk 1.8.13.0~dfsg-1
    --END COMMAND--
    """)

OTHER_COMMAND_RESPONSE = literal_message("""\
    Response: Follows
    Privilege: Command
    ActionID: 1234
    foo
    bar--END COMMAND--
    """)

DIALPLAN_START_RESPONSE = literal_message("""\
    Response: Success
    ActionID: 123.567
    EventList: start
    Message: DialPlan list will follow
    """)

DIALPLAN_RESPONSE_EVENTS = literal_message("""\
    Event: ListDialplan
    ActionID: 123.567
    Context: inbound-call
    Registrar: pbx_config

    Event: ListDialplan
    ActionID: 123.567
    Context: default
    IncludeContext: outgoing-call-leg1
    Registrar: pbx_config
    """)

DIALPLAN_EVENTS_END = literal_message("""\
    Event: ShowDialPlanComplete
    EventList: Complete
    ListItems: 52
    ListExtensions: 19
    ListPriorities: 51
    ListContexts: 19
    ActionID: 123.567
    """)


class ProtocolTestBase(object):

    greeting_line = b"Asterisk Call Manager/1.4\r\n"

    def setUp(self):
        p = self.proto = self.protocol_factory()
        p.greeting_received = Mock()

    def ready_proto(self):
        p = self.proto
        p.data_received(self.greeting_line)
        return p

    def feed(self, message):
        lines = message.splitlines(True)
        for line in lines:
            self.proto.line_received(line)

    def assert_called_once_with_exc(self, callback, exc_class):
        callback.assert_called_once_with(ANY)
        (exc,), _ = callback.call_args
        return exc


class BaseAMIProtocolTest(ProtocolTestBase, unittest.TestCase):

    protocol_factory = BaseAMIProtocol

    def test_greeting_line(self):
        p = self.proto
        self.assertEqual(p._state, 'init')
        self.assertEqual(p.greeting_received.call_count, 0)
        p.data_received(self.greeting_line)
        p.greeting_received.assert_called_once_with(
            "Asterisk Call Manager", "1.4")
        self.assertEqual(p._state, 'idle')

    def test_event_received(self):
        p = self.ready_proto()
        p.event_received = Mock()
        expected = Event('Hangup', {
            'Privilege': 'call,all',
            'Channel': 'SIP/0004F2060EB4-00000000',
            'Uniqueid': '1283174108.0',
            })
        self.feed(EVENT_HANGUP)
        p.event_received.assert_called_once_with(expected)
        (evt,), _ = p.event_received.call_args
        # Headers are case-insensitive
        self.assertEqual(evt.headers['privilege'], 'call,all')
        self.assertEqual(evt.headers['Privilege'], 'call,all')
        self.assertEqual(p._state, 'idle')
        p.event_received.reset_mock()
        self.feed(EVENT_HANGUP)
        p.event_received.assert_called_once_with(expected)
        self.assertEqual(p._state, 'idle')

    def test_response_received(self):
        p = self.ready_proto()
        p.response_received = Mock()
        core_settings = Response('success', {
            'AMIversion': '1.1',
            'AsteriskVersion': '1.8.13.0~dfsg-1',
            }, [])
        error = Response('error', {
            'ActionID': '4444',
            'Message': 'Invalid/unknown command: xyzzy. (blabla)',
            }, [])
        goodbye = Response('goodbye', {
            'Message': 'Thanks for all the fish.',
            }, [])
        self.feed(CORE_SETTINGS_RESPONSE)
        p.response_received.assert_called_once_with(core_settings)
        (resp,), _ = p.response_received.call_args
        # Headers are case-insensitive
        self.assertEqual(resp.headers['amiversion'], '1.1')
        self.assertEqual(resp.headers['AmiVersion'], '1.1')
        p.response_received.reset_mock()
        self.feed(ERROR_RESPONSE)
        p.response_received.assert_called_once_with(error)
        p.response_received.reset_mock()
        self.feed(CORE_SETTINGS_RESPONSE)
        p.response_received.assert_called_once_with(core_settings)
        p.response_received.reset_mock()
        self.feed(LOGOFF_RESPONSE)
        p.response_received.assert_called_once_with(goodbye)
        self.assertEqual(p._state, 'idle')

    def test_command_response_received(self):
        p = self.ready_proto()
        p.response_received = Mock()
        expected = Response('follows', {
            'Privilege': 'Command',
            'ActionID': 'DEF.768',
            }, ['Asterisk 1.8.13.0~dfsg-1'])
        self.feed(CORE_SHOW_VERSION_RESPONSE)
        p.response_received.assert_called_once_with(expected)
        self.assertEqual(p._state, 'idle')

    def test_command_response_received_no_eol(self):
        # Sometimes the command payload is concatenated to the
        # '--END COMMAND--' marker without a EOL separator.
        p = self.ready_proto()
        p.response_received = Mock()
        expected = Response('follows', {
            'Privilege': 'Command',
            'ActionID': '1234',
            }, ['foo', 'bar'])
        self.feed(OTHER_COMMAND_RESPONSE)
        p.response_received.assert_called_once_with(expected)
        self.assertEqual(p._state, 'idle')

    def test_serialize_message(self):
        p = self.ready_proto()
        expected = b"foo: bar\r\n\r\n"
        self.assertEqual(expected, p.serialize_message({'foo': 'bar'}))
        expected = (
            b"foo: bar\r\n"
            b"foo: zyxxy\r\n"
            b"\r\n")
        self.assertEqual(expected,
                         p.serialize_message({'foo': ['bar', 'zyxxy']}))
        expected = (
            b"foo: bar\r\n"
            b"quux: zyxxy\r\n"
            b"\r\n")
        headers = OrderedDict([('foo', 'bar'), ('quux', 'zyxxy')])
        self.assertEqual(expected, p.serialize_message(headers))

    def test_serialize_message_type_error(self):
        p = self.ready_proto()
        with self.assertRaises(TypeError):
            p.serialize_message({'foo': 1})
        if str is not bytes:
            with self.assertRaises(TypeError):
                p.serialize_message({b'foo': b'bar'})


class AMIProtocolTest(ProtocolTestBase, unittest.TestCase):

    protocol_factory = AMIProtocol

    def test_event_received(self):
        p = self.ready_proto()
        p.unhandled_event_received = Mock()
        self.feed(EVENT_HANGUP)
        p.unhandled_event_received.assert_called_once_with(
            Event('Hangup', {
                'Privilege': 'call,all',
                'Channel': 'SIP/0004F2060EB4-00000000',
                'Uniqueid': '1283174108.0',
                }))

    def test_event_handler(self):
        p = self.ready_proto()
        cb_hangup, cb_foobar = Mock(), Mock()
        p.register_event_handler('Hangup', cb_hangup)
        p.register_event_handler('Foobar', cb_foobar)
        self.feed(EVENT_HANGUP)
        cb_hangup.assert_called_once_with(
            Event('Hangup', {
                'Privilege': 'call,all',
                'Channel': 'SIP/0004F2060EB4-00000000',
                'Uniqueid': '1283174108.0',
                }))

    def test_send_action(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('Hello', OrderedDict({'foo': 'bar'}))
        self.assertIsInstance(a, Handler)
        p.write.assert_called_once_with(
            b"foo: bar\r\n"
            b"Action: Hello\r\n"
            b"ActionID: 1\r\n"
            b"\r\n")
        self.assertEqual(a._action_id, '1')
        a = p.send_action('Hi', {'Channel': 'SIP/foo'})
        self.assertIsInstance(a, Handler)
        (data,), _ = p.write.call_args
        lines = data.splitlines()
        self.assertIn(b"ActionID: 2", lines)
        self.assertIn(b"Action: Hi", lines)
        self.assertIn(b"Channel: SIP/foo", lines)
        self.assertEqual(a._action_id, '2')
        self.assertEqual(set(p._actions), {'1', '2'})

    def test_send_action_variables(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('Hi', OrderedDict(), {})
        (data,), _ = p.write.call_args
        self.assertEqual(data, b"Action: Hi\r\nActionID: 1\r\n\r\n")
        a = p.send_action('Hi', {'x': 'y'}, {'foo': '1', 'bar': '2'})
        (data,), _ = p.write.call_args
        lines = data.splitlines(True)
        self.assertEqual(set(lines), {b"x: y\r\n",
                                      b"Variable: foo=1\r\n",
                                      b"Variable: bar=2\r\n",
                                      b"Action: Hi\r\n",
                                      b"ActionID: 2\r\n",
                                      b"\r\n"
                                      })

    def test_send_action_override_action_id(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('Hi', {'ActionID': 'ABCD'})
        (data,), _ = p.write.call_args
        lines = data.splitlines(True)
        self.assertEqual(set(lines), {b"Action: Hi\r\n",
                                      b"ActionID: ABCD\r\n",
                                      b"\r\n"
                                      })
        self.assertEqual(a._action_id, 'ABCD')
        self.assertEqual(set(p._actions), {'ABCD'})

    def test_send_action_response_success(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('CoreSettings', {'ActionID': '1234'})
        a.on_result = Mock()
        a.on_exception = Mock()
        resp = literal_message("""\
            Response: Success
            ActionID: 1234
            AsteriskVersion: 1.8.13
            """)
        p.data_received(resp)
        a.on_result.assert_called_once_with(
            Response('success', {'ActionID': '1234',
                                 'AsteriskVersion': '1.8.13'}, []))
        self.assertEqual(a.on_exception.call_count, 0)
        # The handler has been unregistered: no further callbacks
        p.data_received(resp)
        self.assertEqual(a.on_result.call_count, 1)
        self.assertEqual(a.on_exception.call_count, 0)

    def test_send_action_response_follows(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('Command',
                          {'Command': 'core show version',
                           'ActionID': 'DEF.768'})
        a.on_result = Mock()
        a.on_exception = Mock()
        p.data_received(CORE_SHOW_VERSION_RESPONSE)
        a.on_result.assert_called_once_with(
            Response('follows', {'ActionID': 'DEF.768',
                                 'Privilege': 'Command'},
                                 ['Asterisk 1.8.13.0~dfsg-1']))
        self.assertEqual(a.on_exception.call_count, 0)

    def test_send_action_response_goodbye(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('Logoff',
                          {'ActionID': '1234'})
        a.on_result = Mock()
        a.on_exception = Mock()
        resp = literal_message("""\
            Response: Goodbye
            ActionID: 1234
            Message: Thanks for all the fish.
            """)
        p.data_received(resp)
        a.on_result.assert_called_once_with(
            Response('goodbye', {'ActionID': '1234',
                                 'Message': 'Thanks for all the fish.'},
                                []))
        self.assertEqual(a.on_exception.call_count, 0)

    def test_send_action_response_error(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('xyzzy',
                          {'ActionID': '4444'})
        a.on_result = Mock()
        a.on_exception = Mock()
        p.data_received(ERROR_RESPONSE)
        self.assertEqual(a.on_result.call_count, 0)
        exc = self.assert_called_once_with_exc(a.on_exception, ActionError)
        self.assertEqual(str(exc), "Invalid/unknown command: xyzzy. (blabla)")

    def test_send_action_event_list(self):
        p = self.ready_proto()
        p.write = Mock()
        a = p.send_action('ShowDialPlan',
                          {'ActionID': '123.567'})
        a.on_result = Mock()
        a.on_exception = Mock()
        p.data_received(DIALPLAN_START_RESPONSE)
        self.assertEqual(a.on_result.call_count, 0)
        self.assertEqual(a.on_exception.call_count, 0)
        p.data_received(DIALPLAN_RESPONSE_EVENTS)
        self.assertEqual(a.on_result.call_count, 0)
        self.assertEqual(a.on_exception.call_count, 0)
        p.data_received(DIALPLAN_EVENTS_END)
        a.on_result.assert_called_once_with(ANY)
        self.assertEqual(a.on_exception.call_count, 0)
        (evlist,), _ = a.on_result.call_args
        self.assertIsInstance(evlist, EventList)
        self.assertEqual(len(evlist.events), 2)
        self.assertEqual(evlist.events[0], Event(
            name='ListDialplan',
            headers={
                'ActionID': '123.567',
                'Context': 'inbound-call',
                'Registrar': 'pbx_config',
                }))
        self.assertEqual(evlist.events[1], Event(
            name='ListDialplan',
            headers={
                'ActionID': '123.567',
                'Context': 'default',
                'IncludeContext': 'outgoing-call-leg1',
                'Registrar': 'pbx_config',
                }))
        # End headers are merged with start headers
        self.assertEqual(evlist.headers, {
            'ActionID': '123.567',
            'EventList': 'Complete',
            'ListItems': '52',
            'ListExtensions': '19',
            'ListPriorities': '51',
            'ListContexts': '19',
            'ActionID': '123.567',
            'Message': 'DialPlan list will follow',
            })



if __name__ == "__main__":
    main()
