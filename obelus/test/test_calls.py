
from functools import partial
import re
import unittest

from mock import Mock, ANY

from obelus.ami.calls import Call, CallManager, OriginateError
from obelus.ami.protocol import (
    BaseAMIProtocol, AMIProtocol, Event, Response, EventList, ActionError)
from obelus.test import main, watch_logging
from obelus.test.test_amiprotocol import ProtocolTestBase


class MockCall(Call):

    def __init__(self):
        self.event_calls = []
        for meth_name in [
            'call_queued',
            'call_failed',
            'call_state_changed',
            'dialing_started',
            'dialing_finished',
            'call_ended']:
            def side_effect(meth_name=meth_name):
                def mocked(*args):
                    self.event_calls.append(meth_name)
                return mocked
            setattr(self, meth_name, Mock(side_effect=side_effect()))


UNIQUE_ID = '1378719573.625'
CHANNEL = 'Local/6004@default-00000118;1'


class CallManagerTest(ProtocolTestBase, unittest.TestCase):

    protocol_factory = AMIProtocol

    def call(self):
        return MockCall()

    def call_manager(self):
        self.ami = self.ready_proto()
        cm = CallManager(self.ami)
        cm._tracking_variable = 'X_TRACK'
        return cm

    def queued_call(self):
        cm = self.call_manager()
        call = self.call()
        cm.ami._action_id = 1
        cm.ami.write = Mock()
        cm.originate(call, {"Foo": "Bar"})
        resp = Response('success', {'ActionID': '1'}, [])
        cm.ami.response_received(resp)
        return cm, call

    def tracked_call(self):
        cm, call = self.queued_call()
        event = Event('VarSet',
                      {'Variable': 'X_TRACK',
                       'Value': '1',
                       'Channel': CHANNEL,
                       'Uniqueid': UNIQUE_ID})
        cm.ami.event_received(event)
        return cm, call

    def test_init(self):
        ami = self.protocol_factory()
        cm = CallManager(ami)
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), set())
        self.assertIs(cm.ami, ami)

    def test_tracking_variable(self):
        cms = [CallManager(self.protocol_factory()) for i in range(5)]
        tracking_variables = {cm._tracking_variable for cm in cms}
        self.assertEqual(len(tracking_variables), len(cms), tracking_variables)
        one_var = tracking_variables.pop()
        self.assertTrue(re.match("^[A-Z][_A-Z0-9]*$", one_var), one_var)

    def test_new_call_id(self):
        cm = self.call_manager()
        self.assertEqual(cm._new_call_id(), "1")
        self.assertEqual(cm._new_call_id(), "2")
        self.assertEqual(cm._new_call_id(), "3")

    def test_setup_filters(self):
        cm = self.call_manager()
        sa = cm.ami.send_action = Mock()
        cm.setup_filters()
        self.assertEqual(sa.call_count, 2)
        for (c, filter_desc) in zip(sa.call_args_list,
                                    ["Privilege: call,all",
                                     "Variable: X_TRACK"]):
            (name, headers), _ = c
            self.assertEqual(name, 'Filter')
            self.assertEqual(headers, {'Operation': 'Add',
                                       'Filter': filter_desc})

    def test_originate_bad_call_type(self):
        cm = self.call_manager()
        with self.assertRaises(TypeError):
            cm.originate(object(), {})
        with self.assertRaises(TypeError):
            cm.originate("foo", {})
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), set())

    def test_originate(self):
        cm = self.call_manager()
        call = self.call()
        sa = cm.ami.send_action = Mock()
        cm.originate(call, {"Foo": "Bar"})
        sa.assert_called_once_with(
            "Originate", {"Foo": "Bar"}, {"X_TRACK": "1"})
        self.assertIs(call.manager, cm)
        # The call is still not queued: we wait for the AMI's response
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), set())
        self.assertEqual(call.event_calls, [])

    def test_sync_originate_failure(self):
        # Synchronous failure: the originate action's response is a failure
        cm = self.call_manager()
        call = self.call()
        cm.ami._action_id = 1
        cm.ami.write = Mock()
        cm.originate(call, {"Foo": "Bar"})
        resp = Response('error', {'Message': 'Extension does not exist.',
                                  'ActionID': '1'}, [])
        cm.ami.response_received(resp)
        self.assertEqual(call.event_calls, ['call_failed'])
        self.assert_called_once_with_exc(call.call_failed, ActionError)

    def test_call_queued(self):
        cm, call = self.queued_call()
        self.assertEqual(call.event_calls, ['call_queued'])
        call.call_queued.assert_called_once_with()
        self.assertEqual(cm.queued_calls(), {call})
        self.assertEqual(cm.tracked_calls(), set())

    def test_async_originate_failure(self):
        # Early asynchronous failure: the originate action's response is
        # a success, but a failed OriginateResponse event comes just after
        cm, call = self.queued_call()
        event = Event('OriginateResponse',
                      {'Uniqueid': '<null>',
                       'Reason': '0',
                       'ActionID': '1',
                       'Response': 'Failure'})
        cm.ami.event_received(event)
        self.assertEqual(call.event_calls, ['call_queued', 'call_failed'])
        exc = self.assert_called_once_with_exc(call.call_failed, OriginateError)
        self.assertEqual(exc.reason, 0)

    def test_channel_matching(self):
        cm, call = self.queued_call()
        # This one is ignored
        event = Event('Newchannel',
                      {'Uniqueid': UNIQUE_ID,
                       'ChannelState': '0',
                       'Channel': CHANNEL,
                       'ChannelStateDesc': 'Down'})
        cm.ami.event_received(event)
        self.assertEqual(cm.tracked_calls(), set())
        # Not the right variable value => ignored too
        event = Event('VarSet',
                      {'Variable': 'X_TRACK',
                       'Value': '42',
                       'Channel': CHANNEL,
                       'Uniqueid': UNIQUE_ID})
        with watch_logging('obelus.ami.calls', level='WARN') as w:
            cm.ami.event_received(event)
        self.assertEqual(cm.tracked_calls(), set())
        self.assertEqual(len(w.output), 1)
        # This one sets up the matching
        event = Event('VarSet',
                      {'Variable': 'X_TRACK',
                       'Value': '1',
                       'Channel': CHANNEL,
                       'Uniqueid': UNIQUE_ID})
        cm.ami.event_received(event)
        self.assertEqual(cm.queued_calls(), {call})
        self.assertEqual(cm.tracked_calls(), {call})

    def test_early_hangup(self):
        # Test getting a Hangup without an earlier LocalBridge
        cm, call = self.tracked_call()
        # Ignored (unknown channel even though it's probably related)
        event = Event('Hangup',
                      {'Cause-txt': 'Unknown',
                       'Uniqueid': '1378719573.626',
                       'Cause': '0',
                       'Channel': 'Local/6004@default-00000118;2'})
        cm.ami.event_received(event)
        self.assertEqual(call.event_calls, ['call_queued'])
        # This one triggers the call's end
        event = Event('Hangup',
                      {'Cause-txt': 'Unknown',
                       'Uniqueid': UNIQUE_ID,
                       'Cause': '0',
                       'Channel': CHANNEL})
        cm.ami.event_received(event)
        self.assertEqual(call.event_calls, ['call_queued', 'call_ended'])
        call.call_ended.assert_called_once_with(0, 'Unknown')


if __name__ == "__main__":
    main()
