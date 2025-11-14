#!/bin/sh

###
# @Author: Uyanide pywang0608@foxmail.com
# @Date: 2025-11-04 18:10:34
# @LastEditTime: 2025-11-09 21:28:37
# @Description: Entry point script for and only for Docker container
###

# Check envs

[ -z "$TUM_USERNAME" ] && {
    echo "Error: TUM_USERNAME environment variable is not set." >&2
    exit 1
}

[ -z "$TUM_PASSWORD" ] && {
    echo "Error: TUM_PASSWORD environment variable is not set." >&2
    exit 1
}

# Parse args

CONFIG_PATH="$1"
USER="$2"
shift 2
ARGS="$*"

[ -f "$CONFIG_PATH" ] || {
    echo "Error: Config file '$CONFIG_PATH' does not exist." >&2
    exit 1
}

# Install python packages

{
    REQUIREMENTS=""

    SESSION_TYPE=$(jq -r '.session_type // ""' "$CONFIG_PATH")

    if [ "$SESSION_TYPE" = "requests" ]; then
        REQUIREMENTS="$REQUIREMENTS httpx>=0.28.1 bs4>=0.0.2"
    elif [ "$SESSION_TYPE" = "playwright" ]; then
        REQUIREMENTS="$REQUIREMENTS playwright>=1.55.0"
    else
        echo "Error: Unsupported session_type '$SESSION_TYPE' in config." >&2
        exit 1
    fi

    python3 -m pip install $REQUIREMENTS --root-user-action ignore
} || {
    echo "Error: Failed to install required packages." >&2
    exit 1
}

# Create a non-root user
# should be done in Dockerfile

# {
#     groupadd -f -g "${PGID}" "${USER}" || true && \
#     useradd -r -m -u "${PUID}" -g "${PGID}" "${USER}" 2>/dev/null || \
#     useradd -r -m -u "${PUID}" -g "${USER}" "${USER}" && \
#     chown -R "${USER}":"${USER}" /app
# } || {
#     echo "Error: Failed to create or configure ${USER}." >&2
#     exit 1
# }

# Install browser if needed

if [ "$SESSION_TYPE" = "playwright" ]; then
    BROWSER=$(jq -r '.playwright.browser // "chromium-headless-shell"' "$CONFIG_PATH")

    # Install browser binary as the target user

    su - "${USER}" -c "(
        playwright install $BROWSER --only-shell
    )" || {
        echo "Error: Playwright browser installation failed." >&2
        exit 1
    }

    # Install dependencies as root

    playwright install-deps $BROWSER || {
        echo "Error: Playwright dependencies installation failed." >&2
        exit 1
    }
fi

su - "${USER}" -c "(
    cd /app
    export TUM_USERNAME=\"$TUM_USERNAME\"
    export TUM_PASSWORD=\"$TUM_PASSWORD\"
    python3 -m autumoodle $ARGS
)"
