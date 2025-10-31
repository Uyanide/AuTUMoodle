'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-26 21:59:22
LastEditTime: 2025-10-31 13:52:26
Description: Obtain credentials in multiple ways
'''

import os
import sys
import getpass
import json
from pathlib import Path

ENV_USERNAME = "TUM_USERNAME"
ENV_PASSWORD = "TUM_PASSWORD"


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
