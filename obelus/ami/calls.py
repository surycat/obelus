import hashlib
import logging
import os

from obelus.ami.protocol import Handler, ActionError


log = logging.getLogger(__name__)


class OriginateError(ActionError):
    """
    Error triggered by an OriginateResponse of type "Failure".
    """
    # XXX see e.g. http://permalink.gmane.org/gmane.comp.telephony.pbx.asterisk.user/210539
    # for the meaning of the reason.

    def __init__(self, reason):
        self.reason = int(reason, 10)

    def __str__(self):
        return "Originate failed with reason %s" % (self.reason)


class Call(object):
    """
    Base class for call objects tracked by the CallManager.
    It is recommended you subclass this class and override the various
    event handlers.
    """

    _call_id = None
    _action_id = None
    manager = None

    def _bind(self, manager, call_id, outgoing):
        self.manager = manager
        self._call_id = call_id
        self._state = None
        self._state_desc = None
        self._unique_ids = set()
        self._outgoing = outgoing
        self._last_hangup_cause = None

    def __str__(self):
        try:
            return "Call #%s" % self._call_id
        except AttributeError:
            return super(Call, self).__str__()

    def unique_ids(self):
        """
        Get the alive channels related this call.
        Return a list of unique ids.
        """
        try:
            return sorted(self._unique_ids)
        except AttributeError:
            pass
        raise ValueError("Call not originated")

    # XXX should the state notification callbacks get the logical
    # channel number? (i.e. 1 for the first created channel, 2 for the
    # second...)

    def call_queued(self):
        """
        Called when a call is queued (i.e. when the Originate command
        is accepted).
        """

    def call_failed(self, exc):
        """
        Called when a call fails early.  This either means the Originate
        command was rejected, or a failed OriginateResponse event was
        received just after the command was accepted.
        """

    def call_state_changed(self, state, state_desc):
        """
        Called when a call has its state changed.  *state* is the new
        numeric state, *state_desc* its textual description.
        """

    def dialing_started(self):
        """
        Called when dialing the call has started.
        """

    def dialing_finished(self, status):
        """
        Called when dialing the call has finished with the given *status*.
        """

    def call_ended(self, cause, cause_desc):
        """
        Called when the call ends.  *cause* is the numeric cause
        sent by Asterisk, *cause_desc* its textual description.
        """
        # NOTE: the cause codes are mostly Q850, and enumerated in
        # <asterisk>/include/asterisk/causes.h.
        # The textual descriptions are in <asterisk>/main/channel.c.


class CallManager(object):
    """
    A CallManager helps you originate calls and track the status of those
    calls using an AMI instance.
    """
    # Implementation strategy: when originating a call, we add a custom
    # variable with a unique name and a unique per-call value.  We then
    # listen to SetVar events, which allows us to associate a given
    # call with the first channel allocated for it.
    # Another strategy would be to hijack the CallerID field for our
    # unique id, but this would prevent the user from passing important
    # information there.

    def __init__(self, ami):
        self.ami = ami
        self._tracking_variable = (
            'X_' + hashlib.sha1(os.urandom(32)).hexdigest().upper()[:12])
        self._call_id = 1
        self._incoming_call_factory = None
        # channel unique id => newchannel event headers
        self._new_channels = {}
        # action id => call (queued but untracked calls)
        self._actions = {}
        # call id => call (all queued calls)
        self._calls = {}
        # channel unique id => call
        self._unique_ids = {}
        self.setup_event_handlers()

    def _new_call_id(self):
        i = self._call_id
        self._call_id = i + 1
        return str(i)

    def queued_calls(self):
        """
        Return a set of all queued (outgoing) calls.
        """
        return {call for call in self._calls.values() if call._outgoing}

    def tracked_calls(self):
        """
        Return a set of currently tracked calls (both incoming and
        originated).  Note: some queued calls may be untracked yet.
        """
        return set(self._calls.values()) - set(self._actions.values())

    def listen_for_incoming_calls(self, call_factory):
        """
        When an incoming call is detected, call the given *call_factory*.
        The *call_factory* will be called with the headers of the
        "Newchannel" event for the call, and must return a Call instance
        (possibly a subclass).
        """
        if not callable(call_factory):
            raise TypeError("call factory should be callable")
        self._incoming_call_factory = call_factory

    def setup_event_handlers(self):
        """
        Setup the AMI event handlers required for call tracking.
        This is implicitly called on __init__().
        """
        self.ami.register_event_handler('Newchannel', self.on_new_channel)
        self.ami.register_event_handler('VarSet', self.on_var_set)
        self.ami.register_event_handler('LocalBridge', self.on_local_bridge)
        self.ami.register_event_handler('Dial', self.on_dial)
        self.ami.register_event_handler('Newstate', self.on_new_state)
        self.ami.register_event_handler('SoftHangupRequest', self.on_soft_hangup_request)
        self.ami.register_event_handler('Hangup', self.on_hangup)
        # Yes, there's an event called "OriginateResponse"
        self.ami.register_event_handler('OriginateResponse', self.on_originate_response)

    def setup_filters(self):
        """
        Setup server-side AMI event filters tailored for this CallManager,
        in order to limit resource consumption in the AMI protocol.

        Calling this method is not required for proper functioning, but
        recommended if your Asterisk receives a lot of traffic and generates
        a lot of AMI events by default.

        This method only relies on whitelisting, you can therefore
        setup more server-side filters if you are interested in other
        events.
        """
        # We are interesting in "call" events, as well as in those
        # events that mention our tracking variable (normally, it's
        # only one SetVar event per successfully originated call).
        # This spares us the bursts of NewExten, VarSet and AGIExec events
        # that can occur on non-trivial Asterisk setups.
        filters = ['Privilege: call,all',
                   'Variable: ' + self._tracking_variable]
        handlers = [self.ami.send_action('Filter',
                                         {'Operation': 'Add',
                                          'Filter': filter})
                    for filter in filters]
        return Handler.aggregate(handlers)

    def originate(self, call, headers, variables=None):
        """
        Originate a *call* with the given *headers* (and, optionally,
        call-specific *variables*).  *call* should be a Call instance.
        """
        if not isinstance(call, Call):
            raise TypeError("expected a Call instance, got %r"
                            % call.__class__)
        if call.manager is not None:
            raise ValueError("cannot reuse Call instance, need a new one")
        call_id = self._new_call_id()
        variables = variables or {}
        variables[self._tracking_variable] = call_id
        a = self.ami.send_action('Originate', headers, variables)
        call._bind(self, call_id, outgoing=True)
        def _call_queued(resp):
            action_id = resp.headers['ActionID']
            call._action_id = action_id
            self._actions[action_id] = call
            self._calls[call_id] = call
            call.call_queued()
        def _call_failed(exc):
            call.call_failed(exc)
        a.on_result = _call_queued
        a.on_exception = _call_failed

    def on_originate_response(self, event):
        """
        On an OriginateResponse event, mark the associated call failed
        or queued.
        """
        h = event.headers
        if h['Response'] != 'Failure':
            return
        action_id = h['ActionID']
        call = self._actions.pop(action_id, None)
        if call is not None:
            del self._calls[call._call_id]
            call.call_failed(OriginateError(h['Reason']))

    def _candidate_incoming_call(self, unique_id):
        newchannel = self._new_channels.pop(unique_id, None)
        if (newchannel is not None
            and self._incoming_call_factory is not None):
            call = self._incoming_call_factory(newchannel)
            call_id = self._new_call_id()
            call._bind(self, call_id, outgoing=False)
            self._calls[call_id] = call
            call._unique_ids.add(unique_id)
            self._unique_ids[unique_id] = call
            return call

    def on_new_channel(self, event):
        """
        On a Newchannel event, register the channel as a candidate
        incoming call.
        """
        h = event.headers
        unique_id = h['Uniqueid']
        if h['Channel'].startswith('Local/'):
            log.debug("Newchannel: local channel %r, ignoring", h['Channel'])
            return
        self._new_channels[unique_id] = h

    def on_var_set(self, event):
        """
        On a VarSet event, check if the variable is our tracking variable
        and associate the channel with a call by us.
        """
        h = event.headers
        if h['Variable'] != self._tracking_variable:
            return
        call_id = h['Value']
        unique_id = h['Uniqueid']
        # The channel belongs to an outgoing call, remove it from the
        # candidate incoming calls.
        self._new_channels.pop(unique_id, None)
        try:
            call = self._calls[call_id]
        except KeyError:
            log.error("Got unknown call_id in SetVar: %s", call_id)
            return
        try:
            del self._actions[call._action_id]
        except KeyError:
            log.error("Got duplicate SetVar for call #%s", call_id)
            return
        log.info("Got UniqueID %r for call #%s (channel %r)",
                 unique_id, call_id, h['Channel'])
        call._unique_ids.add(unique_id)
        self._unique_ids[unique_id] = call

    def on_local_bridge(self, event):
        """
        On a LocalBridge event, recognize that the two channels belongs
        to the same call.
        """
        h = event.headers
        id1 = h['Uniqueid1']
        call = self._unique_ids.get(id1)
        if call is None:
            log.debug("LocalBridge: unknown UniqueID %r, ignoring", id1)
            return
        id2 = h['Uniqueid2']
        other_call = self._unique_ids.get(id2)
        if other_call is not None and other_call is not call:
            log.error("LocalBridge: UniqueID %r already bound to other call #%s",
                      id2, other_call._call_id)
            return
        log.info("LocalBridge: new related UniqueID %r for call #%s",
                 id2, call._call_id)
        call._unique_ids.add(id2)
        self._unique_ids[id2] = call

    def _update_hangup_cause(self, call, headers):
        cause = int(headers.get('Cause', '0'), 10)
        if cause or not call._last_hangup_cause:
            call._last_hangup_cause = (cause, headers.get('Cause-txt', ''))

    def on_soft_hangup_request(self, event):
        """
        On a SoftHangupRequest event, update the call's hangup cause
        if desirable.
        """
        h = event.headers
        unique_id = h['Uniqueid']
        call = self._unique_ids.get(unique_id)
        if call is None:
            log.debug("SoftHangupRequest: unknown UniqueID %r, ignoring",
                      unique_id)
            return
        self._update_hangup_cause(call, h)

    def on_hangup(self, event):
        """
        On a Hangup event, recognize that the channel is dead, and that
        the associated call has ended if it has no more channels.
        """
        h = event.headers
        unique_id = h['Uniqueid']
        self._new_channels.pop(unique_id, None)
        call = self._unique_ids.pop(unique_id, None)
        if call is None:
            log.debug("Hangup: unknown UniqueID %r, ignoring", unique_id)
            return
        call._unique_ids.remove(unique_id)
        self._update_hangup_cause(call, h)
        if not call._unique_ids:
            del self._calls[call._call_id]
            call.call_ended(*call._last_hangup_cause)

    def on_dial(self, event):
        """
        On a Dial event, update the call state.
        """
        h = event.headers
        unique_id = h['UniqueID']  # casing!
        call = self._unique_ids.get(unique_id)
        if call is None:
            log.debug("Dial: unknown UniqueID %r, ignoring", unique_id)
            return
        sub = h['SubEvent']
        if sub == 'Begin':
            call.dialing_started()
        elif sub == 'End':
            status = h['DialStatus']
            call.dialing_finished(status)

    def on_new_state(self, event):
        """
        On a Newstate event, update the call state.
        """
        h = event.headers
        unique_id = h['Uniqueid']
        call = self._unique_ids.get(unique_id)
        if call is None:
            call = self._candidate_incoming_call(unique_id)
            if call is None:
                log.debug("Newstate: unknown UniqueID %r, ignoring", unique_id)
                return
        state = int(h['ChannelState'])
        state_desc = h['ChannelStateDesc']
        if state != call._state:
            call._state = state
            call.call_state_changed(state, state_desc)
        call._state_desc = state_desc
