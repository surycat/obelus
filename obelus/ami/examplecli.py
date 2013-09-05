import argparse
import logging
import sys

from .protocol import AMIProtocol

log = logging.getLogger(__name__)


class CLIOptions(object):
    pass


class CLIProtocol(AMIProtocol):

    def __init__(self, loop, options):
        AMIProtocol.__init__(self)
        self.loop = loop
        self.options = options

    def connection_made(self, transport):
        log.info("Connection made")
        super(CLIProtocol, self).connection_made(transport)

    def connection_lost(self, exc):
        log.info("Connection lost")
        super(CLIProtocol, self).connection_lost(exc)
        self.loop.stop()

    def greeting_received(self, api_name, api_version):
        log.info("Asterisk greeting: %r, %r", api_name, api_version)
        a = self.send_action('Login', {'username': self.options.username,
                                       'secret': self.options.secret})
        a.on_result = self.login_successful
        a.on_exception = self.login_failed

    def login_successful(self, resp):
        log.info("Successfully logged in")

    def login_failed(self, exc):
        log.error("Failed logging in: %s", exc)
        self.transport.close()


def create_parser(description):
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-H', '--host', default='localhost',
                        help='Asterisk Manager hostname')
    parser.add_argument('-p', '--port', type=int, default=5038,
                        help='Asterisk Manager port number')
    parser.add_argument('-u', '--user', default="xivouser",
                        help='authentication username')
    parser.add_argument('-s', '--secret', default="xivouser",
                        help='authentication secret')

    parser.add_argument('-q', '--quiet', action='store_true',
                        help='hide information messages')
    parser.add_argument('--debug', action='store_true',
                        help='show debug messages')

    return parser


def parse_args(parser):
    args = parser.parse_args()
    options = CLIOptions()
    options.host, options.port = args.host, args.port
    options.username, options.secret = args.user, args.secret

    if args.quiet:
        level = logging.WARNING
    elif args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(stream=sys.stderr, level=level)

    return options, args
