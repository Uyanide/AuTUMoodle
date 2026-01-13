#!/bin/bash

###
 # @Author: Uyanide pywang0608@foxmail.com
 # @Date: 2026-01-13 05:17:17
 # @LastEditTime: 2026-01-13 05:53:38
 # @Description: Installation script for Docker container
###

set -euo pipefail

# Install dependencies based on session type

REQUIREMENTS=()

if [ "$SESSION_TYPE" = "requests" ]; then
    REQUIREMENTS+=("httpx>=0.28.1" "bs4>=0.0.2")
elif [ "$SESSION_TYPE" = "playwright" ]; then
    REQUIREMENTS+=("playwright>=1.55.0")
else
    echo "Error: Unsupported session_type '$SESSION_TYPE'." >&2
    exit 1
fi

python3 -m pip install "${REQUIREMENTS[@]}" --root-user-action ignore


# Install browser if needed

if [ "$SESSION_TYPE" = "playwright" ]; then
    # Install browser binary as the target user

    gosu "$USER" playwright install "$BROWSER" --only-shell

    # Install dependencies as root

    playwright install-deps "$BROWSER"
fi
