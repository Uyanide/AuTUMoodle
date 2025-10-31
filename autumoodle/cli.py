'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-29 22:08:19
LastEditTime: 2025-10-31 13:32:03
Description: CLI entry point for autumoodle
'''

from argparse import ArgumentParser
from pathlib import Path
import json

from autumoodle.downloader import TUMMoodleDownloader

from .log import Logger
from .config_mgr import Config
from . import credential


def get_argparser():
    parser = ArgumentParser()
    parser.add_argument("-c", "--config", dest="config_path", default="config.json",  help="Path to configuration file (json)")
    parser.add_argument("-s", "--secret", dest="secret_path", help="Path to secret file (json)")
    return parser


async def run():
    arg_parser = get_argparser()
    args = arg_parser.parse_args()
    config_path = Path(args.config_path).expanduser()
    if not config_path.exists() or not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    config_dict = json.loads(config_path.read_text(encoding="utf-8"))
    config = Config.from_dict(config_dict)
    Logger.set_level(config.log_level)

    username, password = credential.get_credentials(Path(args.secret_path) if args.secret_path else None)
    if not username or not password:
        raise ValueError(
            "Username or password are missing. "
            "Either provide a secret file (via -s/--secret), "
            f"or set the {credential.ENV_USERNAME} and {credential.ENV_PASSWORD} environment variables.")
    config.set_credentials(username, password)

    await TUMMoodleDownloader(config).do_magic()
