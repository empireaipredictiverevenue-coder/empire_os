#!/usr/bin/env bash
set -euo pipefail

REPO=/srv/empire_os
BRANCH=feature/revenue-intelligence-v2
PROVIDER_ENV=/etc/empire_os/omniroute-providers.env
REPO_USER="${SUDO_USER:-ubuntu}"

run_as_repo_user() {
  if [[ "$(id -u)" -eq 0 ]]; then
    sudo -u "$REPO_USER" "$@"
  else
    "$@"
  fi
}

cd "$REPO"

echo "=== SYNC HERMES AUTO-ROUTING FIX ==="
run_as_repo_user git -C "$REPO" fetch origin "$BRANCH"
run_as_repo_user git -C "$REPO" merge --ff-only "origin/$BRANCH"

echo "=== REFRESH EXISTING PROVIDER CREDENTIALS ==="
sudo PYTHONPATH="$REPO" "$REPO/.venv/bin/python" \
  "$REPO/scripts/export_omniroute_provider_env.py" \
  --home /home/ubuntu \
  --output "$PROVIDER_ENV"

echo "=== REGISTER DIRECT PROVIDERS IN OMNIROUTE ==="
sudo PYTHONPATH="$REPO" "$REPO/.venv/bin/python" \
  "$REPO/scripts/configure_omniroute_providers.py" \
  --home /home/ubuntu \
  --provider-env "$PROVIDER_ENV" \
  --base-url http://127.0.0.1:20128

echo "=== ONE HERMES RUN ==="
sudo systemctl restart empire-hermes-control.service

echo "=== RESULT ==="
sudo journalctl -u empire-hermes-control.service -n 80 --no-pager

echo "=== COMPLETE ==="
run_as_repo_user git -C "$REPO" rev-parse --short HEAD
