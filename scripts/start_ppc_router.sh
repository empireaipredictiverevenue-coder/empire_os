#!/bin/bash
# Canonical launcher for ppc_router.py — sources /root/empire_os/.env first
# so SOLANA_PAYER_SECRET reaches the process.
# Usage: start_ppc_router.sh [extra args]
set -e

ENV_FILE=/root/empire_os/.env
if [ ! -f "$ENV_FILE" ]; then
    echo "FATAL: $ENV_FILE missing" >&2
    exit 1
fi

# Load .env into current shell (no-op if already set)
set -a
. "$ENV_FILE"
set +a

# Verify critical secret is present
if [ -z "${SOLANA_PAYER_SECRET:-}" ]; then
    echo "FATAL: SOLANA_PAYER_SECRET empty after sourcing $ENV_FILE" >&2
    exit 2
fi

cd /root/empire_os
exec /root/venv/bin/python3 /root/empire_os/empire_os/ppc_router.py "$@"