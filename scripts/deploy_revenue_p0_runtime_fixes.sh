#!/usr/bin/env bash
set -euo pipefail

REPO=/srv/empire_os
BRANCH=feature/revenue-intelligence-v2
ENV_FILE="$REPO/runtime/secrets/outbound.env"

cd "$REPO"

echo "=== SYNC REVENUE P0 RUNTIME FIXES ==="
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"

if [[ -z "${RESEND_RECEIVING_API_KEY:-}" ]]; then
  read -r -s -p "RESEND_RECEIVING_API_KEY: " RESEND_RECEIVING_API_KEY
  echo
fi
if [[ "$RESEND_RECEIVING_API_KEY" != re_* ]]; then
  echo "invalid Resend receiving key" >&2
  exit 2
fi

echo "=== INSTALL RECEIVING SECRET ==="
mkdir -p "$(dirname "$ENV_FILE")"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
grep -v '^RESEND_RECEIVING_API_KEY=' "$ENV_FILE" > "$tmp" || true
printf 'RESEND_RECEIVING_API_KEY=%s\n' "$RESEND_RECEIVING_API_KEY" >> "$tmp"
cat "$tmp" > "$ENV_FILE"
chmod 600 "$ENV_FILE"
unset RESEND_RECEIVING_API_KEY

echo "=== INSTALL CURRENT SYSTEMD UNITS ==="
sudo install -m 0644 deploy/systemd/empire-resend-inbound.service /etc/systemd/system/empire-resend-inbound.service
sudo install -m 0644 deploy/systemd/empire-hermes-control.service /etc/systemd/system/empire-hermes-control.service
sudo install -m 0644 deploy/systemd/empire-hermes-control.timer /etc/systemd/system/empire-hermes-control.timer
sudo systemctl daemon-reload

echo "=== RESTART INBOUND + REFRESH HERMES ==="
sudo systemctl restart empire-resend-inbound.service
sudo systemctl enable --now empire-hermes-control.timer
sudo systemctl start empire-hermes-control.service || true

echo "=== VERIFY ==="
curl -fsS http://127.0.0.1:8097/health
echo
sudo systemctl is-active empire-resend-inbound.service
sudo systemctl is-active empire-hermes-control.timer

echo "=== COMPLETE ==="
git rev-parse --short HEAD
