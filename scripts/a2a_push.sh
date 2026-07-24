#!/bin/bash
# A2A Buyer Marketplace Pusher — canonical launcher.
# Sources /root/empire_os/.env (no secrets required for this job but keeps
# consistency with other empire scripts) and runs the pusher once.
set -e

ENV_FILE=/root/empire_os/.env
if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi

cd /root/empire_os
exec /root/venv/bin/python3 /root/empire_os/empire_os/a2a_buyer_marketplace.py "$@"
