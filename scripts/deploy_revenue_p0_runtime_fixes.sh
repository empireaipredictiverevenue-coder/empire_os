#!/usr/bin/env bash
set -euo pipefail

REPO=/srv/empire_os
BRANCH=feature/revenue-intelligence-v2
ENV_FILE="$REPO/runtime/secrets/outbound.env"

cd "$REPO"

echo "=== SYNC REVENUE P0 RUNTIME FIXES ==="
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"

SECRET_ALREADY_INSTALLED=0
if grep -q '^RESEND_RECEIVING_API_KEY=re_' "$ENV_FILE" 2>/dev/null; then
  SECRET_ALREADY_INSTALLED=1
  echo "=== RECEIVING SECRET ALREADY INSTALLED ==="
fi

if [[ "$SECRET_ALREADY_INSTALLED" -eq 0 ]]; then
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
fi

echo "=== INSTALL CURRENT SYSTEMD UNITS ==="
sudo install -m 0644 deploy/systemd/empire-resend-inbound.service /etc/systemd/system/empire-resend-inbound.service
sudo install -m 0644 deploy/systemd/empire-hermes-control.service /etc/systemd/system/empire-hermes-control.service
sudo install -m 0644 deploy/systemd/empire-hermes-control.timer /etc/systemd/system/empire-hermes-control.timer
sudo systemctl daemon-reload

echo "=== RESTART INBOUND + REFRESH HERMES ==="
sudo systemctl restart empire-resend-inbound.service
sudo systemctl enable --now empire-hermes-control.timer
sudo systemctl start empire-hermes-control.service || true

wait_active() {
  local unit="$1"
  local attempts="${2:-30}"
  local state=""
  for ((i=1; i<=attempts; i++)); do
    state="$(sudo systemctl is-active "$unit" 2>/dev/null || true)"
    if [[ "$state" == "active" ]]; then
      echo "$unit: active"
      return 0
    fi
    if [[ "$state" == "failed" || "$state" == "inactive" ]]; then
      echo "$unit: $state" >&2
      sudo systemctl status "$unit" --no-pager -l || true
      return 1
    fi
    sleep 1
  done
  echo "$unit did not reach active state; final_state=$state" >&2
  sudo systemctl status "$unit" --no-pager -l || true
  return 1
}

echo "=== VERIFY ==="
curl -fsS http://127.0.0.1:8097/health
echo
wait_active empire-resend-inbound.service 30
wait_active empire-hermes-control.timer 10

echo "=== HERMES LATEST LOG ==="
sudo journalctl -u empire-hermes-control.service -n 20 --no-pager || true

echo "=== COMPLETE ==="
git rev-parse --short HEAD
