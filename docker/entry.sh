#!/bin/bash

###
# @Author: Uyanide pywang0608@foxmail.com
# @Date: 2025-11-04 18:10:34
 # @LastEditTime: 2026-01-13 06:43:07
# @Description: Entry point script for and only for Docker container
###

set -euo pipefail

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

[ -f "$CONFIG_PATH" ] || {
    echo "Error: Config file '$CONFIG_PATH' does not exist." >&2
    exit 1
}

# Create a non-root user

smart_chown() {
    local dir
    dir="$1"

    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
    fi

    local current_owner
    current_owner=$(stat -c "%u" "$dir")

    if [ "$current_owner" != "$PUID" ]; then
        chown -R "${PUID}:${PGID}" "$dir"
    fi
}

groupmod -o -g "$PGID" "$USER"
usermod -o -u "$PUID" "$USER"
smart_chown /app/autumoodle/__pycache__
smart_chown /data
smart_chown /cache

exec gosu "$USER" python3 -m autumoodle -S "$SESSION_TYPE" -B "$BROWSER" "$@"
