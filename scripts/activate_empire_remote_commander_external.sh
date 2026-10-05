#!/usr/bin/env bash
set -euo pipefail

REPO=/srv/empire_os
CF_CONFIG=/home/ubuntu/.cloudflared/config.yml
HOSTNAME=mcp.empire-ai.co.uk
MCP_URL=http://127.0.0.1:8765/mcp
ACTIVATE=0

if [[ "${1:-}" == "--activate" ]]; then
  ACTIVATE=1
fi

echo "=== EMPIRE REMOTE COMMANDER EXTERNAL ACTIVATION ==="
echo "hostname=$HOSTNAME"
echo "mcp_url=$MCP_URL"
echo "activation_requested=$ACTIVATE"

test -f "$CF_CONFIG"
CLOUDFLARED_BIN="$(command -v cloudflared || true)"
test -n "$CLOUDFLARED_BIN"
test -f "$REPO/scripts/install_empire_remote_commander.sh"

if [[ "$ACTIVATE" -ne 1 ]]; then
  echo "decision=PREVIEW"
  echo "would_backup=$CF_CONFIG"
  echo "would_route_dns=$HOSTNAME"
  echo "would_add_ingress=http://127.0.0.1:8765"
  echo "would_activate=empire-ops-mcp.service"
  echo "would_restart=empire-cloudflared.service"
  exit 0
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$CF_CONFIG.remote-commander.$STAMP.bak"

sudo cp -a "$CF_CONFIG" "$BACKUP"

rollback() {
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    echo "activation_failed=true" >&2
    echo "rolling_back_cloudflare_config=$BACKUP" >&2
    sudo cp -a "$BACKUP" "$CF_CONFIG" || true
    sudo systemctl restart empire-cloudflared.service || true
  fi
  exit "$rc"
}
trap rollback EXIT

sudo "$REPO/scripts/install_empire_remote_commander.sh" --activate

sudo "$REPO/.venv/bin/python" - "$CF_CONFIG" "$HOSTNAME" <<'PY'
import sys
from pathlib import Path
import yaml

path = Path(sys.argv[1])
hostname = sys.argv[2]
payload = yaml.safe_load(path.read_text()) or {}
ingress = payload.get("ingress")
if not isinstance(ingress, list):
    raise SystemExit("cloudflare config has no ingress list")

target = {"hostname": hostname, "service": "http://127.0.0.1:8765"}
existing = [
    row for row in ingress
    if isinstance(row, dict) and row.get("hostname") == hostname
]
if existing:
    for row in existing:
        if row.get("service") != target["service"]:
            raise SystemExit("existing MCP hostname routes elsewhere")
else:
    fallback_index = len(ingress)
    for idx, row in enumerate(ingress):
        if isinstance(row, dict) and "hostname" not in row:
            fallback_index = idx
            break
    ingress.insert(fallback_index, target)
    payload["ingress"] = ingress
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
PY

sudo /usr/local/bin/cloudflared tunnel route dns   "$TUNNEL_NAME" "$HOSTNAME"

sudo systemctl restart empire-cloudflared.service

sleep 2
systemctl is-active --quiet empire-ops-mcp.service
systemctl is-active --quiet empire-cloudflared.service

curl --fail --silent --show-error   --max-time 5   http://127.0.0.1:8765/mcp   -o /dev/null || true

echo "activation=complete"
echo "cloudflare_backup=$BACKUP"
echo "external_endpoint=https://$HOSTNAME/mcp"
trap - EXIT
