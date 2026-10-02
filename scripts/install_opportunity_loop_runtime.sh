#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/empire_os
SERVICE=empire-opportunity-loop.service
TIMER=empire-opportunity-loop.timer

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root (sudo bash scripts/install_opportunity_loop_runtime.sh)" >&2
  exit 2
fi

cd "$ROOT"
echo "=== OPPORTUNITY LOOP PRODUCTION INSTALL ==="

install -d -o ubuntu -g ubuntu -m 0755 \
  "$ROOT/runtime/opportunity_radar" \
  "$ROOT/runtime/opportunity_factory"

install -m 0644 deploy/systemd/$SERVICE /etc/systemd/system/$SERVICE
install -m 0644 deploy/systemd/$TIMER /etc/systemd/system/$TIMER
systemctl daemon-reload
systemctl enable "$TIMER"

# First governed run proves the installed contract. The loop itself is OBSERVE
# and freshness-guarded; it performs no outbound/commercial/payment mutation.
systemctl start "$SERVICE"
systemctl restart "$TIMER"

systemctl is-active --quiet "$TIMER"
test "$(systemctl show -p User --value "$SERVICE")" = "ubuntu"
test "$(systemctl show -p Group --value "$SERVICE")" = "ubuntu"

python3 - <<'PY'
import json
from pathlib import Path
p=Path('/srv/empire_os/runtime/opportunity_radar/loop_latest.json')
if not p.exists():
    raise SystemExit('ERROR: opportunity loop artifact missing')
d=json.loads(p.read_text())
assert d.get('ok') is True, d
assert d.get('execution_authority') == 'none', d
assert d.get('automatic_external_execution_allowed') is False, d
assert d.get('outreach_sent') is False, d
assert d.get('payment_action') is False, d
assert d.get('revenue_recognized') is False, d
print(json.dumps({
    'opportunity_loop_runtime':'ready',
    'finished_at':d.get('finished_at'),
    'radar_candidate_count':d.get('radar_candidate_count'),
    'factory_ready_count':d.get('factory_ready_count'),
    'execution_authority':d.get('execution_authority'),
},sort_keys=True))
PY

echo "=== INSTALLED CONTRACT ==="
systemctl cat "$SERVICE" | grep -E 'User=|Group=|EnvironmentFile=|ExecStart=|NoNewPrivileges=|ProtectSystem=|ReadWritePaths=|TimeoutStartSec='
systemctl cat "$TIMER" | grep -E 'OnBootSec=|OnUnitInactiveSec=|Persistent=|Unit='

echo "=== RESULT ==="
echo "opportunity_loop_runtime=ready"
echo "astra_duplicate_scheduler=false"
echo "external_execution_authority=none"
