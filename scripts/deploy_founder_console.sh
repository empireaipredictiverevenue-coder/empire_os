#!/usr/bin/env bash
set -euo pipefail

REPO="/srv/empire_os"
BRANCH="feature/revenue-intelligence-v2"
APP_DIR="$REPO/apps/search-command-centre"
API_UNIT="empire-founder-dashboard-api.service"
CONSOLE_UNIT="empire-founder-console.service"

cd "$REPO"

echo "=== FOUNDER CONSOLE SAFE DEPLOY ==="

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  found="${current_branch:-DETACHED}"
  echo "refusing deploy: expected branch $BRANCH, found $found" >&2
  exit 2
fi

if [[ -n "$(git status --short --untracked-files=no)" ]]; then
  echo "refusing deploy: tracked working tree is dirty" >&2
  git status --short --untracked-files=no >&2
  exit 3
fi

previous_head="$(git rev-parse HEAD)"
echo "previous_head=$previous_head"

echo
echo "=== FAST-FORWARD PRODUCTION TRUTH ==="
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"
current_head="$(git rev-parse HEAD)"
echo "current_head=$current_head"

echo
echo "=== BACKEND VERIFICATION ==="
PYTHONPATH="$REPO" "$REPO/.venv/bin/python" -m pytest -q \
  tests/test_empire_mailbox.py \
  tests/test_founder_mailbox_api.py \
  tests/test_reply_classifier.py \
  tests/test_resend_webhook_app.py \
  tests/test_buyer_reply_operations_agent.py \
  --tb=short

"$REPO/.venv/bin/python" -m py_compile \
  empire_os/empire_mailbox.py \
  empire_os/founder_mailbox_api.py \
  empire_os/reply_classifier.py \
  empire_os/founder_dashboard_service.py

echo
echo "=== FRONTEND VERIFICATION + BUILD ==="
cd "$APP_DIR"
npm ci
npm run lint
npm run build
cd "$REPO"

echo
echo "=== INSTALL CURRENT FOUNDER UNITS ==="
sudo install -m 0644 deploy/systemd/empire-founder-dashboard-api.service "/etc/systemd/system/$API_UNIT"
sudo install -m 0644 deploy/systemd/empire-founder-console.service "/etc/systemd/system/$CONSOLE_UNIT"
sudo systemctl daemon-reload

echo
echo "=== RESTART FOUNDER SERVICES ==="
sudo systemctl restart "$API_UNIT"
sudo systemctl restart "$CONSOLE_UNIT"

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
    if [[ "$state" == "failed" ]]; then
      echo "$unit: failed" >&2
      sudo systemctl status "$unit" --no-pager -l || true
      return 1
    fi
    sleep 1
  done
  echo "$unit did not reach active state; final_state=$state" >&2
  sudo systemctl status "$unit" --no-pager -l || true
  return 1
}

wait_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-30}"
  local body=""
  for ((i=1; i<=attempts; i++)); do
    if body="$(curl -fsS --max-time 5 "$url" 2>/dev/null)"; then
      echo "$label: HTTP OK"
      printf "%s\n" "$body" | head -c 500
      echo
      return 0
    fi
    sleep 1
  done
  echo "$label did not become HTTP-ready: $url" >&2
  return 1
}

wait_active "$API_UNIT" 30
wait_active "$CONSOLE_UNIT" 30

echo
echo "=== LOCAL SMOKE ==="
wait_http "http://127.0.0.1:8766/health" "Founder API health" 30
wait_http "http://127.0.0.1:8766/v1/founder-mailbox/summary?limit=5" "Empire Mail API" 30

mail_html="$(curl -fsS --max-time 10 "http://127.0.0.1:3001/founder/mail")"
if ! grep -q "Empire Mail" <<<"$mail_html"; then
  echo "Founder Console responded but Empire Mail marker was not found" >&2
  exit 4
fi
echo "Founder Console /founder/mail: HTTP OK + marker found"

echo
echo "=== DEPLOY COMPLETE ==="
echo "previous_head=$previous_head"
echo "current_head=$current_head"
echo "api_unit=$API_UNIT"
echo "console_unit=$CONSOLE_UNIT"
