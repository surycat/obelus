"""
Event-driven, framework-agnostic implementation of the AMI protocol.
"""

import collections
import logging

from ..common import _BaseHandler, LineReceiver


_BaseResponse = collections.namedtuple('_BaseResponse',
                                       ('type', 'headers', 'payload'))

class Response(_BaseResponse):
    __slots__ = ()


_BaseEvent = collections.namedtuple('_BaseEvent',
                                    ('name', 'headers'))

class Event(_BaseEvent):
    __slots__ = ()


_BaseEventList = collections.namedtuple('_BaseEventList',
                                        ('headers', 'events'))

class EventList(_BaseEventList):
    __slots__ = ()


class ActionError(RuntimeError):
    """
    An error response was received following an action.
    """


class _ActionHandler(_BaseHandler):

    def __init__(self, action_id, proto):
        self._action_id = action_id
        self._proto = proto


class BaseAMIProtocol(LineReceiver):
    """
    Implementation of the AMI protocol syntax.
    """

    # XXX The AMI charset isn't really defined, it seems Asterisk
    # will just pass bytestrings around without caring.  We use
    # utf-8 as a reasonable default for common setups.
    encoding = 'utf-8'
    eol = '\r\n'

    logger = logging.getLogger(__name__)

    _response_types = {'success', 'follows', 'error', 'goodbye'}
    _headers_for_response_follows = {'Privilege', 'ActionID'}
    _response_follows_end = '--END COMMAND--'

    def __init__(self):
        super(BaseAMIProtocol, self).__init__()
        self.reset()

    def reset(self):
        self._state = 'init'
        self._event_handlers = {}

    def _split_key_value(self, line):
        key, sep, value = line.rstrip().partition(':')
        if not sep:
            raise ValueError("Expected a key/value pair, got %r"
                             % (line,))
        return key, value.lstrip()

    def greeting_received(self, api_name, api_version):
        """
        Called when the AMI's initial greeting line is received.
        Typical valeus for *api_name* and *api_version* are
        "Asterisk Call Manager" and "1.1", respectively.

        Override this method to do something with said information.
        """

    def line_received(self, line):
        """
        Processing an incoming *line* of AMI data.
        """
        line = line.rstrip(b'\r\n')
        if not isinstance(line, str):
            # Python 3 only
            line = line.decode(self.encoding)
        self.logger.debug("Incoming line: %r", line)
        if self._state == 'init':
            # Parse greeting line
            name, version = line.strip().split("/")
            self._state = 'idle'
            self.greeting_received(name, version)
        elif self._state == 'idle':
            # Start of event or response
            if not line:
                return
            key, value = self._split_key_value(line)
            if key == 'Response':
                self._state = 'in-response'
                self._headers = {}
                self._payload = []
                self._resp_type = value.lower()
                if self._resp_type not in self._response_types:
                    raise ValueError("Invalid response type %r"
                                     % (self.resp_type))
            elif key == 'Event':
                self._state = 'in-event'
                self._headers = {}
                self._event_type = value
            else:
                raise ValueError("Unexpected first message line %r" % (line,))
        elif self._state == 'in-response':
            if not line:
                # Response ends with an empty line
                self._state = 'idle'
                self._response_complete()
            else:
                # Expect a "Key: value" line
                key, value = self._split_key_value(line)
                self._headers[key] = value
                if (self._resp_type == 'follows' and
                    set(self._headers) >= self._headers_for_response_follows):
                    # The payload of a "command" response comes after the
                    # "Response", "ActionID" and "Privilege" headers.
                    assert not self._payload
                    self._state = 'in-response-follows'
        elif self._state == 'in-event':
            if not line:
                # Event ends with an empty line
                self._state = 'idle'
                self._event_complete()
            else:
                # Expect a "Key: value" line
                key, value = self._split_key_value(line)
                self._headers[key] = value
        elif self._state == 'in-response-follows':
            # Inside a command payload: accumulate until we encounter
            # the '--END COMMAND--' marker.
            if line.endswith(self._response_follows_end):
                line = line[:-len(self._response_follows_end)]
                if line:
                    self._payload.append(line)
                self._state = 'idle'
                self._response_complete()
            else:
                self._payload.append(line)
        else:
            # Shouldn't come here
            assert 0

    def _response_complete(self):
        resp = Response(self._resp_type, self._headers, self._payload)
        self.response_received(resp)

    def _event_complete(self):
        event = Event(self._event_type, self._headers)
        self.event_received(event)

    def response_received(self, resp):
        """
        Called when a response is received.
        """

    def event_received(self, event):
        """
        Called when an event is received.
        """

    def serialize_message(self, headers):
        """
        Serialize a message comprised of the given *headers*.
        Each header value can be either a str or a list of str objects.
        """
        lines = []
        for key, values in headers.items():
            if not isinstance(values, list):
                values = [values]
            for value in values:
                lines.append(": ".join([key, value]))
        lines.extend(["", ""])
        data = self.eol.join(lines)
        if not isinstance(data, bytes):
            data = data.encode(self.encoding)
        return data


class AMIProtocol(BaseAMIProtocol):
    """
    Higher-level AMI protocol implementation, including response and event
    matching.
    """

    def reset(self):
        super(AMIProtocol, self).reset()
        self._action_id = 1
        self._actions = {}
        self._event_lists = {}

    def _next_action_id(self):
        a = self._action_id
        self._action_id = a + 1
        return str(a)

    def send_action(self, name, headers, variables=()):
        """
        """
        if variables:
            vars_list = headers.setdefault('Variable', [])
            for key, value in variables.items():
                vars_list.append('='.join([key, value]))
        headers['Action'] = name
        try:
            action_id = headers['ActionID']
        except KeyError:
            action_id = headers['ActionID'] = self._next_action_id()
        data = self.serialize_message(headers)
        self.logger.debug("Writing action: %r", data)
        self.write(data)
        handler = _ActionHandler(action_id, self)
        self._actions[action_id] = handler
        return handler

    def _cancel_action(self, handler):
        action_id = handler._action_id
        try:
            current_handler = self._actions.pop(action_id)
        except KeyError:
            # For convenience, we allow "cancelling" an action which
            # has finished receiving results, or was already cancelled.
            pass
        else:
            if current_handler is not handler:
                self._actions[action_id] = current_handler
                raise RuntimeError("Cannot cancel stale action handler")

    def register_event_handler(self, name, func):
        """
        Register a callable event handler *func* for the event *name*.
        """
        if not isinstance(name, str):
            raise TypeError("Event name should be str, not %r" % (name.__class__))
        if name in self._event_handlers:
            raise KeyError("Handler already registered for %r" % (name,))
        self._event_handlers[name] = func

    def unregister_event_handler(self, name):
        """
        Unregister the handler for event *name*.
        """
        del self._event_handlers[name]

    def _handle_event_list_start(self, resp, action_id, handler):
        if action_id in self._event_lists:
            self.logger.error("Received new EventList for "
                              "ungoing event list %r" % (action_id,))
            return
        self._event_lists[action_id] = EventList(resp.headers, [])

    def event_received(self, event):
        action_id = event.headers.get('ActionID')
        action_handler = action_id and self._actions.get(action_id)
        event_list = action_handler and self._event_lists.get(action_id)
        if event_list is not None:
            # Handle potential event list item
            event_type = event.headers.get('EventList', '').lower()
            if event_type == 'complete':
                del self._event_lists[action_id]
                del self._actions[action_id]
                # We merge the end event's headers into the EventList's,
                # since they can carry useful information.
                event_list.headers.update(event.headers)
                action_handler._on_result(event_list)
                return
            elif event_type:
                self.logger.warn("Invalid EventList header in event: %r"
                                 % (event_type,))
            event_list.events.append(event)
            return
        self._dispatch_event(event)

    def _dispatch_event(self, event):
        try:
            handler = self._event_handlers[event.name]
        except KeyError:
            self.unhandled_event_received(event)
        else:
            handler(event)

    def unhandled_event_received(self, event):
        """
        Called when an *event* is received for which no handler has
        been registered.
        """
        self.logger.info("Unhandled event type %r", event.name)

    def response_received(self, resp):
        action_id = resp.headers['ActionID']
        try:
            handler = self._actions[action_id]
        except KeyError:
            self.logger.info("Unknown or stale response received "
                             "with action ID %r" % (action_id,))
            return
        if resp.type == 'error':
            del self._actions[action_id]
            exc = ActionError(resp.headers.get('Message', ''))
            handler._on_exception(exc)
        elif resp.type in ('success', 'goodbye', 'follows'):
            event_type = resp.headers.get('EventList', '').lower()
            if event_type == 'start':
                self._handle_event_list_start(resp, action_id, handler)
                return
            elif event_type:
                self.logger.warn("Invalid EventList header in response: %r"
                                 % (event_type,))
            del self._actions[action_id]
            handler._on_result(resp)
        else:
            # Can't come here
            assert 0

