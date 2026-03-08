#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

groupmod -o -g "$PGID" appuser
usermod -o -u "$PUID" appuser

chown -R appuser:appuser /app /config /tvshows /temp_dir

exec gosu appuser "$@"
