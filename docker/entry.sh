#!/bin/sh

###
# @Author: Uyanide pywang0608@foxmail.com
# @Date: 2025-11-04 18:10:34
 # @LastEditTime: 2025-11-23 19:23:05
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

[ -z "$PUID" ] && {
    PUID=1000
}

[ -z "$PGID" ] && {
    PGID=1000
}

# Parse args

CONFIG_PATH="$1"
USER="appuser"
shift 1
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

smart_chown() {
    local dir="$1"

    if [ ! -d "$dir" ]; then
        mkdir -p "$dir" || {
            echo "Error: Failed to create directory $dir." >&2
            exit 1
        }
        return 0
    fi

    local current_owner
    current_owner=$(stat -c "%u" "$dir")

    if [ "$current_owner" != "$PUID" ]; then
        chown -R "${PUID}:${PGID}" "$dir" || {
            echo "Error: Failed to change ownership of $dir." >&2
            exit 1
        }
    fi
}

{
    groupadd -f -g "${PGID}" "${USER}" || true && \
    useradd -r -m -u "${PUID}" -g "${PGID}" "${USER}" 2>/dev/null || \
    useradd -r -m -u "${PUID}" -g "${USER}" "${USER}" && \
    smart_chown /data && \
    smart_chown /cache
} || {
    echo "Error: Failed to create or configure ${USER}." >&2
    exit 1
}

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

exec gosu "$USER" python3 -m autumoodle $ARGS
