#!/usr/bin/env bash
# Runner for the settlement gateway daemon.
# - Pushes the latest /root/empire_os/empire_os/settlement_gateway_daemon.py
#   into the empire-hub container (host fs != container fs).
# - Executes the daemon inside the container so the live DB is the target.
set -euo pipefail

# Local source on host
HOST_SRC="/root/empire_os/empire_os/settlement_gateway_daemon.py"
CONTAINER_DST="empire-hub/root/empire_os/empire_os/settlement_gateway_daemon.py"

if [ -f "$HOST_SRC" ]; then
  /usr/bin/incus file push "$HOST_SRC" "$CONTAINER_DST" >/dev/null
fi

# Ensure the feedback log dir exists inside the container
/usr/bin/incus exec empire-hub -- /root/venv/bin/python3 -c \
  "import os, pathlib; pathlib.Path('/root/empire_os/feedback').mkdir(parents=True, exist_ok=True)" \
  || true

# Run the daemon (the timer re-fires this every 60s)
/usr/bin/incus exec empire-hub -- /root/venv/bin/python3 \
  /root/empire_os/empire_os/settlement_gateway_daemon.py
