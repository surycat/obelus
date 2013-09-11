
import hashlib
import logging
import os
try:
    # Python 3
    from urllib.parse import unquote_to_bytes
except ImportError:
    # Python 2
    from urllib import unquote as unquote_to_bytes

from ..common import Handler
from .protocol import AGIChannel


class _AsyncAGIChannel(AGIChannel):
    """
    """

    def __init__(self, executor):
        self.executor = executor
        # Command ID => Handler
        self._commands = {}

    def send_command_line(self, line):
        return self.executor._send_command_line(self.proto, line)


class AsyncAGIExecutor(object):
    """
    AsyncAGIExecutor dispatches between a single AMI protocol instance
    and an arbitrary number of AGI channels and protocols.

    *protocol_factory* should be a callable returning a AGIProtocol
    instance.  It will be called each time a new Async AGI channel is
    started by Asterisk through the AMI.
    """

    logger = logging.getLogger(__name__)
    ami = None

    def __init__(self, protocol_factory):
        self.protocol_factory = protocol_factory
        # Channel ID => _AsyncAGIChannel
        self._channels = {}
        # Compute a reasonably random stem for command ids
        self._command_id_stem = hashlib.sha1(os.urandom(32)).hexdigest()[:10]
        self._command_id = 1

    def _new_command_id(self):
        command_id = self._command_id
        self._command_id = command_id + 1
        return "%s-%s" % (command_id, self._command_id_stem)

    def _check_bound(self):
        if self.ami is None:
            raise ValueError("Operation on non-bound executor")

    def is_bound(self):
        """
        Whether this executor is bound to an AMI protocol instance.
        """
        return self.ami is not None

    def bind(self, ami):
        """
        Bind this executor to an AMI protocol instance.
        NOTE: only one AsyncAGIExecutor can be bound to an AMI protocol
        instance, at any given time.
        """
        if self.ami is not None:
            raise ValueError("Executor already bound")
        ami.register_event_handler('AsyncAGI', self._asyncagi_event_received)
        self.ami = ami

    def unbind(self):
        """
        Unbind this executor from the AMI protocol instance it is bound to.
        """
        self._check_bound()
        ami = self.ami
        self.ami = None
        ami.unregister_event_handler('AsyncAGI')

    def _decode_agi_data(self, proto, value):
        """
        Decode some AGI protocol data encoded into an AMI header value.
        """
        return unquote_to_bytes(value)

    def _encode_agi_data(self, proto, data):
        """
        Encode some AGI data for sending over the AMI.
        """
        # The AMI protocol accepts str objects as header values, not bytes
        if not isinstance(data, str):
            return data.decode(proto.encoding)
        else:
            return data

    def _send_command_line(self, proto, line):
        self._check_bound()
        channel = proto.channel
        handler = Handler()
        command_id = self._new_command_id()
        headers = {
            'Command': self._encode_agi_data(proto, line.rstrip()),
            'CommandID': command_id,
            'Channel': proto._channel_id,
            }
        # The 'AGI' action has a synchronous response, and then the actual
        # result of the AGI command comes as an AsyncAGI event (subevent
        # 'Exec').
        action_handler = self.ami.send_action('AGI', headers)
        def _on_action_success(resp):
            channel._commands[command_id] = handler
        def _on_action_failure(exc):
            handler.on_exception(exc)
        action_handler.on_result = _on_action_success
        action_handler.on_exception = _on_action_failure
        return handler

    def _asyncagi_event_received(self, event):
        subevent = event.headers['SubEvent']
        if subevent == 'Start':
            self._asyncagi_start(event)
        elif subevent == 'Exec':
            self._asyncagi_exec(event)
        elif subevent == 'End':
            self._asyncagi_end(event)
        else:
            self.logger.warning("Unknown AsyncAGI subevent received: %r")

    def _asyncagi_exec(self, event):
        channel_id = event.headers['Channel']
        command_id = event.headers['CommandID']
        try:
            channel = self._channels[channel_id]
        except KeyError:
            # Could be from a stale session, only make it a warning
            self.logger.warning(
                "Received 'AsyncAGI exec' event for unknown channel %r",
                channel_id)
            return
        try:
            handler = channel._commands.pop(command_id)
        except KeyError:
            self.logger.warning(
                "Received 'AsyncAGI exec' event for unknown command %r "
                "in channel %r", command_id, channel_id)
            return
        # Ensure the AGI protocol is expecting a response for this command.
        proto = channel.proto
        proto._push_command(handler)
        result_block = self._decode_agi_data(proto, event.headers['Result'])
        result_lines = result_block.splitlines(True)
        for line in result_lines:
            proto.line_received(line)
        if proto._state != 'idle':
            self.logger.error(
                "Invalid AGI protocol state after AsyncAGI Exec "
                "(bad 'Env' line?): %r" % (proto._state,))
            return

    def _asyncagi_start(self, event):
        channel_id = event.headers['Channel']
        if channel_id in self._channels:
            self.logger.error(
                "Received new 'AsyncAGI start' event for bound channel %r",
                channel_id)
            return
        channel = _AsyncAGIChannel(self)
        proto = self.protocol_factory(channel)
        proto._channel_id = channel_id
        proto.bind_session()
        # The 'Env' header contains a %-encoded sequence of lines
        # containing the AGI environment, feed it to the protocol.
        env_block = self._decode_agi_data(proto, event.headers['Env'])
        env_lines = env_block.splitlines(True)
        for line in env_lines:
            proto.line_received(line)
        if proto._state != 'idle':
            self.logger.error(
                "Invalid AGI protocol state after AsyncAGI Start "
                "(bad 'Env' line?): %r" % (proto._state,))
            return
        self._channels[channel_id] = channel

    def _asyncagi_end(self, event):
        # TODO error out all the pending commands
        channel_id = event.headers['Channel']
        try:
            channel = self._channels.pop(channel_id)
        except KeyError:
            # Could be from a stale session, only make it a warning
            self.logger.warning(
                "Received 'AsyncAGI end' event for unknown channel %r",
                channel_id)
            return
        channel.proto.unbind_session()
        del channel.proto
