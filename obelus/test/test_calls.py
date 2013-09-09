
from functools import partial
import re
import unittest

from mock import Mock, ANY

from obelus.ami.calls import Call, CallManager
from obelus.ami.protocol import (
    BaseAMIProtocol, AMIProtocol, Event, Response, EventList, ActionError)
from obelus.test import main
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
            'call_finished']:
            setattr(self, meth_name, Mock(
                side_effect=lambda *args:
                    partial(self.event_calls.append, meth_name)))


class CallManagerTest(ProtocolTestBase, unittest.TestCase):

    protocol_factory = AMIProtocol

    def call(self):
        return MockCall()

    def call_manager(self):
        self.ami = self.ready_proto()
        cm = CallManager(self.ami)
        cm._tracking_variable = 'X_TRACK'
        return cm

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
        # The call is still not queued: we wait for the AMI's response
        self.assertEqual(cm.queued_calls(), set())
        self.assertEqual(cm.tracked_calls(), set())


if __name__ == "__main__":
    main()
