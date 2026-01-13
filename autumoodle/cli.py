'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-29 22:08:19
LastEditTime: 2026-01-13 06:06:37
Description: CLI entry point for autumoodle
'''

from argparse import ArgumentParser, Action
from pathlib import Path
import json
import sys
import os
import getpass

from autumoodle.downloader import TUMMoodleDownloader

from .log import Logger
from .config_mgr import Config
from .utils import PatternMatcher


ENV_USERNAME = "TUM_USERNAME"
ENV_PASSWORD = "TUM_PASSWORD"


class OrderedPatternAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, 'ordered_patterns'):
            namespace.ordered_patterns = []
        namespace.ordered_patterns.append((self.dest, values))


def get_argparser():
    parser = ArgumentParser()
    parser.add_argument("-c", "--config", dest="config_path", default="config.json",  help="Path to configuration file (json)")
    parser.add_argument("-s", "--secret", dest="secret_path", help="Path to secret file (json)")
    parser.add_argument(
        "-r", "--regex", dest="regex", action=OrderedPatternAction, metavar="REGEX",
        help="Match course title against the given regular expression (can be given multiple times)."
    )
    parser.add_argument(
        "-t", "--contains", dest="contains", action=OrderedPatternAction, metavar="SUBSTR",
        help="Match course title against the given substring (can be given multiple times)."
    )
    parser.add_argument(
        "-l", "--literal", dest="literal", action=OrderedPatternAction, metavar="LITERAL",
        help="Match course title against the given literal string (can be given multiple times)."
    )
    parser.add_argument(
        "-S", "--session", dest="session_type", choices=["playwright", "requests"],
        help="Override session type set in configuration file (playwright or requests)."
    )
    parser.add_argument(
        "-B", "--browser", dest="browser",
        help="Override Playwright browser type set in configuration file."
    )
    return parser


def load_config(config_path: Path) -> Config:
    if not config_path.exists() or not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    config_dict = json.loads(config_path.read_text(encoding="utf-8"))
    return Config.from_dict(config_dict)


def get_additional_matchers(args):
    matchers = []
    if hasattr(args, 'ordered_patterns'):
        for pattern_type, value in args.ordered_patterns:
            if pattern_type == 'regex':
                matchers.append(PatternMatcher(value, "regex"))
            elif pattern_type == 'contains':
                matchers.append(PatternMatcher(value, "contains"))
            elif pattern_type == 'literal':
                matchers.append(PatternMatcher(value, "literal"))
    return matchers


def get_credentials(credential_path: Path | None = None):
    # First try envs
    username: str = os.environ.get(ENV_USERNAME, "")
    password: str = os.environ.get(ENV_PASSWORD, "")

    # Then try credential file
    if credential_path is not None and credential_path.exists() and credential_path.is_file():
        try:
            cred_dict = json.loads(credential_path.read_text())
            username = username if username else cred_dict.get("username", "")
            password = password if password else cred_dict.get("password", "")
        except json.JSONDecodeError:
            pass

    # Finally ask user if in interactive shell
    if sys.stdin.isatty():
        if not username:
            username = input("TUM Username: ")
        if not password:
            password = getpass.getpass("TUM Password: ")
    return username, password


async def run():
    arg_parser = get_argparser()
    args = arg_parser.parse_args()

    config_path = Path(args.config_path).expanduser()
    config = load_config(config_path)
    Logger.set_level(config.log_level)

    additional_matchers = get_additional_matchers(args)

    username, password = get_credentials(Path(args.secret_path) if args.secret_path else None)
    if not username or not password:
        raise ValueError(
            "Username or password are missing. "
            "Either provide a secret file (via -s/--secret), "
            f"or set the {ENV_USERNAME} and {ENV_PASSWORD} environment variables.")
    config.set_credentials(username, password)

    if args.session_type and args.session_type in ["playwright", "requests"]:
        Logger.i("CLI", f"Overriding session type to: {args.session_type}")
        config.session_type = args.session_type

    if args.browser:
        Logger.i("CLI", f"Overriding Playwright browser to: {args.browser}")
        config.playwright_browser = args.browser

    await TUMMoodleDownloader(config, additional_matchers).do_magic()
