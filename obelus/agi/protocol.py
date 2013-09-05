"""
Event-driven implementation of the AGI protocol.
"""

import collections
import logging
import re

from ..common import Handler, LineReceiver


class AGIError(RuntimeError):
    """
    An error returned by Asterisk through the AGI channel.
    """

class AGIUnknownCommand(AGIError):
    """
    Unknown AGI command.
    """

class AGIForbiddenCommand(AGIError):
    """
    AGI command disallowed on a dead channel.
    """

class AGISyntaxError(AGIError):
    """
    Invalid syntax or arguments for an AGI command.
    """

class AGICommandFailure(AGIError):
    """
    Negative result code returned by a command.
    """

_agi_errors = {
    510: AGIUnknownCommand,
    511: AGIForbiddenCommand,
    520: AGISyntaxError,
}


_BaseResponse = collections.namedtuple('_BaseResponse',
                                       ('result', 'variables', 'data'))

class Response(_BaseResponse):
    __slots__ = ()


class AGIChannel(object):

    def send_command_line(self, line):
        raise NotImplementedError


class ProtocolAGIChannel(AGIChannel):
    """
    An AGI channel which simply re-uses its protocol for communications.
    Meant to be used for the "normal" forms of AGI (script AGI, Fast AGI).
    """

    def send_command_line(self, line):
        handler = Handler()
        self.write(line)
        # Expect responses in sequential order.
        self.proto._push_command(handler)
        return handler

    def write(self, data):
        self.proto.write(data)


class AGIProtocol(LineReceiver):

    # XXX The AGI charset isn't really defined, it seems Asterisk
    # will just pass bytestrings around without caring.  We use
    # utf-8 as a reasonable default for common setups.
    encoding = 'utf-8'
    eol = '\n'
    session_factory = None

    logger = logging.getLogger(__name__)

    def __init__(self, channel):
        self.channel = channel
        self.channel.proto = self
        self.reset()

    def reset(self):
        self._state = 'init'
        self.env = {}
        self.argv = []
        self._resp_code = None
        self._resp_message = ''
        self._commands = collections.deque()
        self._session = None

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        pass

    def write(self, data):
        self.transport.write(data)

    def bind_session(self):
        """
        """
        if self.session_factory is not None:
            self._session = self.session_factory()
            self._session.proto = self
        return self._session

    def unbind_session(self):
        """
        """
        if self._session is not None:
            self._session.session_finished()
            self._session = None

    def _split_key_value(self, line):
        key, sep, value = line.rstrip().partition(':')
        if not sep:
            raise ValueError("Expected a key/value pair, got %r"
                             % (line,))
        return key, value.lstrip()

    def _escape_arg(self, arg):
        if '\0' in arg or '\n' in arg:
            raise ValueError("Forbidden characters in AGI argument: %r"
                             % (arg,))
        escaped = re.sub(r'([\\"])', r'\\\1', arg)
        if not arg or escaped != arg or ' ' in arg or '\t' in arg:
            return '"%s"' % escaped
        else:
            return escaped

    def line_received(self, line):
        """
        Processing an incoming *line* of AGI data.
        """
        if not isinstance(line, str):
            # Python 3 only
            line = line.decode(self.encoding)
        self.logger.debug("Incoming line: %r", line)
        if self._state == 'init':
            # In AGI variables header: parse a "key: value" pair
            line = line.rstrip('\r\n')
            if not line:
                # Empty line => AGI variables header finished.
                self._state = 'idle'
                self.logger.info("Got %d AGI variables, now "
                                 "waiting for commands", len(self.env))
                if self._session is not None:
                    self._session.session_established()
                return
            k, v = self._split_key_value(line)
            if not k.startswith('agi_'):
                raise ValueError("Invalid AGI variable %r" % k)
            agi_var = k[4:]
            if agi_var.startswith('arg_'):
                # AGI arguments are passed as 'agi_arg_1', etc.
                try:
                    num_arg = int(agi_var[4:], 10)
                except ValueError:
                    pass
                else:
                    if num_arg == len(self.argv) + 1:
                        self.argv.append(v)
                        return
            if agi_var in self.env:
                self.logger.warning("Duplicate value for AGI variable %r"
                                    % (k,))
            self.env[agi_var] = v
            return
        if self._state == 'idle':
            # AGI is essentially a request-response protocol, the server
            # shouldn't send anything without us asking.
            if line.strip():
                self.logger.warning("Unexpected line received while idle: %r", line)
            return
        if self._state == 'awaiting-response':
            if line[3] not in ' -':
                raise ValueError("Invalid response line %r" % line)
            code = int(line[:3])
            tail = line[4:]
            if not 200 <= code < 600:
                raise ValueError("Invalid response code %d" % code)
            if code < 300:
                self._got_successful_response(code, tail.rstrip())
                return
            if code == 520 and 'follows' in tail:
                # 520 responses can include a multiline usage message
                self._resp_code = code
                self._resp_message = tail
                self._state = 'in-response'
                return
            self._got_error_response(code, tail.rstrip())
            return
        if self._state == 'in-response':
            if line.startswith("%d " % self._resp_code):
                self._got_error_response(self._resp_code,
                                         self._resp_message)
                self._resp_code = None
                self._resp_message = None
            elif line.endswith("520 End of proper usage.\n"):
                # Workaround Async AGI bug where there is a missing EOL
                # inside the "Result" header value.
                self._resp_message += line
                self._got_error_response(self._resp_code,
                                         self._resp_message)
                self._resp_code = None
                self._resp_message = None
            else:
                self._resp_message += line
            return
        # Shouldn't come here
        assert 0

    def send_command(self, args):
        """
        Send the command identified by the *args* tuple of strings.
        """
        # XXX Relax this?
        if self._state != 'idle':
            raise RuntimeError("Can only send AGI command when idle")
        assert not self._commands
        line = self._encode_command(args)
        command = self.channel.send_command_line(line)
        self._state = 'awaiting-response'
        return command

    def _encode_command(self, args):
        """
        Return the encoded command line (as bytes) for the given *args*.
        """
        if len(args) == 0:
            raise ValueError("Args sequence cannot be empty")
        args = [self._escape_arg(a) for a in args]
        line = ' '.join(args) + self.eol
        if not isinstance(line, bytes):
            # Python 3
            line = line.encode(self.encoding)
        return line

    def _parse_result(self, line):
        """
        Parse an AGI result line and return a (result code, variables, data)
        tuple.  For example, given "result=1 (foo bar) endpos=123", return
        (1, {'endpos': '123'), 'foo bar').
        """
        result = None
        variables = {}
        data = None
        data_parts = []
        in_data = False
        for part in line.split(' '):
            if in_data:
                if part.endswith(')'):
                    data_parts.append(part[:-1])
                    in_data = False
                else:
                    data_parts.append(part)
            else:
                if part.startswith('('):
                    if part.endswith(')'):
                        data_parts.append(part[1:-1])
                    else:
                        data_parts.append(part[1:])
                        in_data = True
                else:
                    key, sep, value = part.partition('=')
                    if not sep:
                        # XXX what else?
                        continue
                    if key == 'result':
                        result = int(value, 10)
                    else:
                        variables[key] = value
        return result, variables, ' '.join(data_parts) if data_parts else None

    def _push_command(self, command):
        """
        Push a command on the commands queue and adjust the protocol's state.
        """
        self._commands.append(command)
        self._state = 'awaiting-response'

    def _pop_command(self):
        """
        Pop a command from the commands queue and adjust the protocol's state.
        """
        command = self._commands.popleft()
        self._state = 'awaiting-response' if self._commands else 'idle'
        return command

    def _got_successful_response(self, code, body):
        command = self._pop_command()
        # Try to parse the AGI ad-hoc result string
        result, variables, data = self._parse_result(body)
        if result < 0:
            # A negative result signals failure to execute a command.
            # Unfortunately, Asterisk doesn't give any error description.
            command.set_exception(AGICommandFailure(body))
        else:
            command.set_result(Response(result, variables, data))

    def _got_error_response(self, code, message):
        command = self._pop_command()
        exc_class = _agi_errors.get(code, AGIError)
        exc = exc_class(message)
        command.set_exception(exc)

