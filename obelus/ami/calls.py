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

    def _bind(self, manager, call_id):
        self.manager = manager
        self._call_id = call_id
        self._state = None
        self._state_desc = None
        self._unique_ids = set()

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
        Return a set of all queued calls.
        """
        return set(self._calls.values())

    def tracked_calls(self):
        """
        Return a set of currently tracked calls (i.e. queued *and*
        successfully originated).  This is a subset of queued_calls().
        """
        return set(self._calls.values()) - set(self._actions.values())

    def setup_event_handlers(self):
        """
        Setup the AMI event handlers required for call tracking.
        This is implicitly called on __init__().
        """
        self.ami.register_event_handler('VarSet', self.on_var_set)
        self.ami.register_event_handler('LocalBridge', self.on_local_bridge)
        self.ami.register_event_handler('Dial', self.on_dial)
        self.ami.register_event_handler('Newstate', self.on_new_state)
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
        call._bind(self, call_id)
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
        h = event.headers
        if h['Response'] != 'Failure':
            return
        action_id = h['ActionID']
        call = self._actions.pop(action_id, None)
        if call is not None:
            del self._calls[call._call_id]
            call.call_failed(OriginateError(h['Reason']))

    def on_var_set(self, event):
        h = event.headers
        if h['Variable'] != self._tracking_variable:
            return
        call_id = h['Value']
        unique_id = h['Uniqueid']
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

    def on_hangup(self, event):
        h = event.headers
        unique_id = h['Uniqueid']
        call = self._unique_ids.pop(unique_id, None)
        if call is None:
            log.debug("Hangup: unknown UniqueID %r, ignoring", unique_id)
            return
        call._unique_ids.remove(unique_id)
        if not call._unique_ids:
            del self._calls[call._call_id]
            call.call_ended(int(h['Cause'], 10), h.get('Cause-txt', ''))

    def on_dial(self, event):
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
        h = event.headers
        unique_id = h['Uniqueid']
        call = self._unique_ids.get(unique_id)
        if call is None:
            log.debug("Newstate: unknown UniqueID %r, ignoring", unique_id)
            return
        state = int(h['ChannelState'])
        state_desc = h['ChannelStateDesc']
        if state != call._state:
            call._state = state
            call.call_state_changed(state, state_desc)
        call._state_desc = state_desc
