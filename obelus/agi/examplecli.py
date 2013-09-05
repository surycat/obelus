import argparse
import logging
import pprint
import sys

from .protocol import AGIProtocol
from .session import AGISession

log = logging.getLogger(__name__)


class CLIOptions(object):
    pass


class CLISession(AGISession):

    def session_established(self):
        log.info("AGI session established")
        log.info("AGI variables: %s", pprint.pformat(self.proto.env))
        self.run_coroutine(self.example_commands())

    def session_finished(self):
        self.logger.info("AGI session finished")

    def example_commands(self):
        try:
            resp = yield self.proto.send_command(["channel", "status"])
            log.info("Channel status: %d", resp.result)
            resp = yield self.proto.send_command(["hangup"])
            log.info("Hangup result: %d", resp.result)
        finally:
            self.proto.transport.close()


class CLIProtocol(AGIProtocol):

    session_factory = CLISession

    def connection_made(self, transport=None):
        log.info("Connection made")
        super(CLIProtocol, self).connection_made(transport)

    def connection_lost(self, exc):
        log.info("Connection lost")
        super(CLIProtocol, self).connection_lost(exc)


def create_parser(description):
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='hide information messages')
    parser.add_argument('--debug', action='store_true',
                        help='show debug messages')
    return parser


def parse_args(parser):
    args = parser.parse_args()
    options = CLIOptions()

    if args.quiet:
        level = logging.WARNING
    elif args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(stream=sys.stderr, level=level)

    return options, args
