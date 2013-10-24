
from functools import partial
import re
import unittest

from mock import Mock, ANY

from obelus.ami.calls import Call, CallManager, OriginateError
from obelus.ami.protocol import (
    BaseAMIProtocol, AMIProtocol, Event, Response, EventList, ActionError)
from . import main, watch_logging
from .test_amiprotocol import ProtocolTestBase


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
UNIQUE_ID_2 = '1378719573.626'
CHANNEL_2 = 'Local/6004@default-00000118;2'
UNIQUE_ID_OTHER = '1378719573.631'
UNIQUE_ID_OTHER_2 = '1378719573.632'
UNIQUE_ID_INCOMING = '1382364953.8'
CHANNEL_INCOMING = 'SIP/surycat-00000008'

LOCAL_BRIDGE = Event('LocalBridge',
                     {'Uniqueid2': UNIQUE_ID_2,
                      'Uniqueid1': UNIQUE_ID,
                      'Channel2': CHANNEL_2,
                      'Channel1': CHANNEL,
                      'Context': 'default'})

LOCAL_BRIDGE_OTHER = Event('LocalBridge',
                     {'Uniqueid2': UNIQUE_ID_OTHER_2,
                      'Uniqueid1': UNIQUE_ID_OTHER,
                      'Channel2': 'Local/6004@default-00000119;2',
                      'Channel1': 'Local/6004@default-00000119;1',
                      'Context': 'default'})

DIAL_START = Event('Dial',
                   {'DestUniqueID': '1378719683.629',
                    'SubEvent': 'Begin',
                    'UniqueID': UNIQUE_ID_2,
                    'Channel': CHANNEL_2,
                    'Dialstring': '0sxqaw'})

DIAL_END = Event('Dial',
                 {'SubEvent': 'End',
                  'UniqueID': UNIQUE_ID_2,
                  'Channel': CHANNEL_2,
                  'DialStatus': 'BUSY'})

DIAL_OTHER = Event('Dial',
                   {'DestUniqueID': '1378719683.629',
                    'SubEvent': 'Begin',
                    'UniqueID': UNIQUE_ID_OTHER,
                    'Channel': CHANNEL_2,
                    'Dialstring': '0sxqaw'})

NEWCHANNEL_1 = Event('Newchannel',
                     {'AccountCode': '',
                      'Uniqueid': UNIQUE_ID,
                      'Channel': CHANNEL,
                      'Exten': '6004',
                      'Context': 'default',
                      'CallerIDNum': '',
                      'CallerIDName': '',
                      'Privilege': 'call,all',
                      'ChannelState': '0',
                      'ChannelStateDesc': 'Down'})

NEWCHANNEL_2 = Event('Newchannel',
                     {'AccountCode': '',
                      'Uniqueid': UNIQUE_ID_2,
                      'Channel': CHANNEL_2,
                      'Exten': '6004',
                      'Context': 'default',
                      'CallerIDNum': '',
                      'CallerIDName': '',
                      'Privilege': 'call,all',
                      'ChannelState': '4',
                      'ChannelStateDesc': 'Ring'})

NEWCHANNEL_INCOMING = Event('Newchannel',
                            {'Privilege': 'call,all',
                             'Uniqueid': UNIQUE_ID_INCOMING,
                             'Channel': CHANNEL_INCOMING,
                             'ChannelState': '0',
                             'ChannelStateDesc': 'Down',
                             'CallerIDNum': '202',
                             'CallerIDName': 'User PTI1',
                             'AccountCode': '',
                             'Exten': '444',
                             'Context': 'inbound-call'})

NEWSTATE_1_OTHER = Event('Newstate',
                         {'ChannelState': '5',
                          'Uniqueid': '1378719683.629',
                          'Channel': 'SIP/0sxqaw-00000041',
                          'ChannelStateDesc': 'Ringing'})

NEWSTATE_1 = Event('Newstate',
                   {'ChannelState': '5',
                    'Uniqueid': UNIQUE_ID,
                    'Channel': CHANNEL,
                    'ChannelStateDesc': 'Ringing'})

NEWSTATE_2 = Event('Newstate',
                   {'ChannelState': '6',
                    'Uniqueid': UNIQUE_ID_2,
                    'Channel': CHANNEL_2,
                    'ChannelStateDesc': 'Up'})

NEWSTATE_INCOMING = Event('Newstate',
                          {'ChannelState': '4',
                           'ChannelStateDesc': 'Ring',
                           'Uniqueid': UNIQUE_ID_INCOMING,
                           'Channel': CHANNEL_INCOMING,
                           'CallerIDNum': '202',
                           'CallerIDName': 'User PTI1',
                           'ConnectedLineNum': '',
                           'ConnectedLineName': ''})

HANGUP_REJECTED_1 = Event('Hangup',
                          {'Cause-txt': 'Call Rejected',
                           'Uniqueid': UNIQUE_ID_2,
                           'Cause': '21',
                           'Channel': CHANNEL_2})

HANGUP_REJECTED_2 = Event('Hangup',
                          {'Cause-txt': 'Call Rejected',
                           'Uniqueid': UNIQUE_ID,
                           'Cause': '21',
                           'Channel': CHANNEL})

SOFT_HANGUP_INCOMING_1 = Event('SoftHangupRequest',
                               {'Channel': CHANNEL_INCOMING,
                                'Uniqueid': UNIQUE_ID_INCOMING,
                                'Cause': '32'})

SOFT_HANGUP_INCOMING_2 = Event('SoftHangupRequest',
                               {'Channel': CHANNEL_INCOMING,
                                'Uniqueid': UNIQUE_ID_INCOMING,
                                'Cause': '16'})

HANGUP_INCOMING = Event('Hangup',
                        {'Channel': CHANNEL_INCOMING,
                         'Uniqueid': UNIQUE_ID_INCOMING,
                         'CallerIDNum': '202',
                         'CallerIDName': 'User PTI1',
                         'ConnectedLineNum': '<unknown>',
                         'ConnectedLineName': '<unknown>',
                         'Cause': '0',
                         'Cause-txt': 'Unknown'})


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
        cm.ami.event_received(NEWCHANNEL_1)
        cm.ami.event_received(NEWCHANNEL_2)
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

    def test_originate_call_reuse(self):
        cm = self.call_manager()
        call = self.call()
        sa = cm.ami.send_action = Mock()
        cm.originate(call, {"Foo": "Bar"})
        with self.assertRaises(ValueError):
            cm.originate(call, {"Foo": "Quux"})
        self.assertEqual(sa.call_count, 1)

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

    def test_call_originated_unique_ids(self):
        cm = self.call_manager()
        call = self.call()
        cm.ami._action_id = 1
        cm.ami.write = Mock()
        self.assertRaises(ValueError, call.unique_ids)
        cm.originate(call, {"Foo": "Bar"})
        self.assertEqual(call.unique_ids(), [])

    def test_call_queued_unique_ids(self):
        cm, call = self.queued_call()
        self.assertEqual(call.unique_ids(), [])

    def test_call_tracked_unique_ids(self):
        cm, call = self.tracked_call()
        self.assertEqual(call.unique_ids(), [UNIQUE_ID])

    def test_local_bridges(self):
        cm, call = self.tracked_call()
        self.assertEqual(call.unique_ids(), [UNIQUE_ID])
        cm.ami.event_received(LOCAL_BRIDGE_OTHER)
        self.assertEqual(call.unique_ids(), [UNIQUE_ID])
        cm.ami.event_received(LOCAL_BRIDGE)
        self.assertEqual(call.unique_ids(), [UNIQUE_ID, UNIQUE_ID_2])

    def test_call_queued(self):
        cm, call = self.queued_call()
        self.assertEqual(call.event_calls, ['call_queued'])
        call.call_queued.assert_called_once_with()
        self.assertEqual(cm.queued_calls(), {call})
        self.assertEqual(cm.tracked_calls(), set())
        # Newchannel events for the call are ignored
        cm.ami.event_received(NEWCHANNEL_1)
        cm.ami.event_received(NEWCHANNEL_2)
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
        # Not the right variable name => ignored
        event = Event('VarSet',
                      {'Variable': 'SOMETHING',
                       'Value': '1',
                       'Channel': CHANNEL,
                       'Uniqueid': UNIQUE_ID})
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
                       'Uniqueid': UNIQUE_ID_2,
                       'Cause': '0',
                       'Channel': CHANNEL_2})
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

    def test_dialing_started(self):
        cm, call = self.tracked_call()
        # The LocalBridge events helps track the second channel, on which
        # the dialing will happen.
        cm.ami.event_received(LOCAL_BRIDGE)
        self.assertEqual(call.event_calls, ['call_queued'])
        cm.ami.event_received(DIAL_START)
        self.assertEqual(call.event_calls, ['call_queued', 'dialing_started'])
        call.dialing_started.assert_called_once_with()

    def test_dialing_finished(self):
        cm, call = self.tracked_call()
        cm.ami.event_received(LOCAL_BRIDGE)
        cm.ami.event_received(DIAL_START)
        cm.ami.event_received(DIAL_END)
        self.assertEqual(call.event_calls, ['call_queued', 'dialing_started',
                                            'dialing_finished'])
        call.dialing_finished.assert_called_once_with('BUSY')

    def test_dial_other(self):
        cm, call = self.tracked_call()
        cm.ami.event_received(LOCAL_BRIDGE)
        cm.ami.event_received(DIAL_OTHER)
        self.assertEqual(call.event_calls, ['call_queued'])

    def test_state_events(self):
        cm, call = self.tracked_call()
        cm.ami.event_received(LOCAL_BRIDGE)
        cm.ami.event_received(DIAL_START)
        cm.ami.event_received(NEWSTATE_1_OTHER)
        self.assertEqual(call.event_calls, ['call_queued', 'dialing_started'])
        cm.ami.event_received(NEWSTATE_1)
        self.assertEqual(call.event_calls,
                         ['call_queued', 'dialing_started', 'call_state_changed'])
        call.call_state_changed.assert_called_once_with(5, 'Ringing')
        # call_state_changed not called again if the state doesn't change
        cm.ami.event_received(NEWSTATE_1)
        call.call_state_changed.assert_called_once_with(5, 'Ringing')
        cm.ami.event_received(NEWSTATE_2)
        self.assertEqual(call.event_calls,
                         ['call_queued', 'dialing_started',
                          'call_state_changed', 'call_state_changed'])
        call.call_state_changed.assert_called_with(6, 'Up')

    def test_call_ended(self):
        cm, call = self.tracked_call()
        cm.ami.event_received(LOCAL_BRIDGE)
        cm.ami.event_received(HANGUP_REJECTED_1)
        self.assertEqual(call.event_calls, ['call_queued'])
        cm.ami.event_received(HANGUP_REJECTED_2)
        self.assertEqual(call.event_calls, ['call_queued', 'call_ended'])
        call.call_ended.assert_called_once_with(21, 'Call Rejected')

    def test_call_ended_2(self):
        # Same as test_call_ended(), but Hangups received in reverse order.
        cm, call = self.tracked_call()
        cm.ami.event_received(LOCAL_BRIDGE)
        cm.ami.event_received(HANGUP_REJECTED_2)
        self.assertEqual(call.event_calls, ['call_queued'])
        cm.ami.event_received(HANGUP_REJECTED_1)
        self.assertEqual(call.event_calls, ['call_queued', 'call_ended'])
        call.call_ended.assert_called_once_with(21, 'Call Rejected')

    #
    # Tracking of incoming calls
    #

    def incoming_call(self, cm, newchannel, newstate):
        def factory(*args):
            factory.result = MockCall()
            return factory.result
        factory = Mock(side_effect=factory)
        cm.listen_for_incoming_calls(factory)
        cm.ami.event_received(newchannel)
        self.assertEqual(factory.call_count, 0)
        cm.ami.event_received(newstate)
        factory.assert_called_once_with(newchannel.headers)
        return factory.result

    def test_incoming_local_call(self):
        # Local calls are not considered
        cm = self.call_manager()
        factory = Mock()
        cm.listen_for_incoming_calls(factory)
        cm.ami.event_received(NEWCHANNEL_1)
        cm.ami.event_received(NEWSTATE_1)
        self.assertEqual(factory.call_count, 0)
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), set())

    def test_incoming_sip_call(self):
        # Non-local calls are considered incoming when newstate is received
        cm = self.call_manager()
        call = self.incoming_call(cm, NEWCHANNEL_INCOMING, NEWSTATE_INCOMING)
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), {call})
        self.assertEqual(call.event_calls, ['call_state_changed'])
        call.call_state_changed.assert_called_once_with(4, 'Ring')
        cm.ami.event_received(HANGUP_INCOMING)
        self.assertEqual(call.event_calls, ['call_state_changed', 'call_ended'])
        call.call_ended.assert_called_once_with(0, 'Unknown')

    def test_incoming_sip_call_hangup_cause(self):
        # The cause passed to "call_ended" corresponds to the last non-zero
        # cause of either Hangup or SoftHangupRequest events.
        cm = self.call_manager()
        call = self.incoming_call(cm, NEWCHANNEL_INCOMING, NEWSTATE_INCOMING)
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), {call})
        self.assertEqual(call.event_calls, ['call_state_changed'])
        call.call_state_changed.assert_called_once_with(4, 'Ring')
        cm.ami.event_received(SOFT_HANGUP_INCOMING_1)
        cm.ami.event_received(SOFT_HANGUP_INCOMING_2)
        self.assertEqual(call.event_calls, ['call_state_changed'])
        cm.ami.event_received(HANGUP_INCOMING)
        self.assertEqual(call.event_calls, ['call_state_changed', 'call_ended'])
        call.call_ended.assert_called_once_with(16, '')

    def test_incoming_sip_call_no_factory(self):
        # Incoming calls are ignored if no factory is registered
        cm = self.call_manager()
        cm.ami.event_received(NEWCHANNEL_INCOMING)
        cm.ami.event_received(NEWSTATE_INCOMING)
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), set())

    def test_incoming_call_factory_type_error(self):
        cm = self.call_manager()
        with self.assertRaises(TypeError):
            cm.listen_for_incoming_calls(object())


if __name__ == "__main__":
    main()
