#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os
set -a
. /srv/empire_os/.env.astra_observer
set +a

exec /srv/empire_os/.venv/bin/python   /srv/empire_os/scripts/astra_observer.py
