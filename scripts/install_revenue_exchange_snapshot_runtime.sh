#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root (sudo bash scripts/install_revenue_exchange_snapshot_runtime.sh)" >&2
  exit 1
fi

ROOT=/srv/empire_os
cd "$ROOT"

PROVISION_READER=false
if [[ "${1:-}" == "--provision-reader" ]]; then
  PROVISION_READER=true
elif [[ -n "${1:-}" ]]; then
  echo "ERROR: unsupported argument: ${1}" >&2
  exit 2
fi

echo "=== REVENUE EXCHANGE SNAPSHOT RUNTIME INSTALL ==="

# Founder-gated authority activation. The installer never provisions a new
# database identity unless the explicit flag is present.
if [[ "$PROVISION_READER" == true ]]; then
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/provision_revenue_exchange_reader.py" --apply
elif [[ ! -s /etc/empire_revenue_exchange.env ]]; then
  echo "ERROR: dedicated Revenue Exchange reader is not provisioned." >&2
  echo "After explicit founder approval, rerun with --provision-reader." >&2
  exit 3
fi

install -d -o ubuntu -g ubuntu -m 0755 \
  "$ROOT/runtime/revenue_exchange"

install -m 0644 \
  deploy/systemd/empire-revenue-exchange-snapshot.service \
  /etc/systemd/system/empire-revenue-exchange-snapshot.service

install -m 0644 \
  deploy/systemd/empire-revenue-exchange-snapshot.timer \
  /etc/systemd/system/empire-revenue-exchange-snapshot.timer

systemctl daemon-reload

# Reload the narrow helper so its new read-only unit allowlist is active.
systemctl restart empire-ops-privileged-helper.service

# Enable bounded autonomous refresh and run one governed cycle immediately.
systemctl enable --now empire-revenue-exchange-snapshot.timer
systemctl start empire-revenue-exchange-snapshot.service

echo "=== INSTALLED CONTRACT ==="
systemctl cat \
  empire-revenue-exchange-snapshot.service \
  empire-revenue-exchange-snapshot.timer \
  | grep -E 'User=|Group=|EnvironmentFile=|ExecStart=|OnUnitInactiveSec=|ReadWritePaths=|NoNewPrivileges='

echo "=== RUNTIME STATUS ==="
systemctl status \
  empire-revenue-exchange-snapshot.service \
  empire-revenue-exchange-snapshot.timer \
  empire-ops-privileged-helper.service \
  --no-pager -l

echo "=== SNAPSHOT SUMMARY ==="
runuser -u ubuntu -- "$ROOT/.venv/bin/python" - <<'PY'
import json
from pathlib import Path
p=Path('/srv/empire_os/runtime/revenue_exchange/latest.json')
if not p.exists():
    raise SystemExit('snapshot_missing')
d=json.load(open(p))
print(json.dumps({
    'schema_version':d.get('schema_version'),
    'source':d.get('source'),
    'market_count':d.get('market_count'),
    'invalid_row_count':d.get('invalid_row_count'),
    'blockers':d.get('blockers'),
    'read_only':d.get('read_only'),
    'execution_authority':d.get('execution_authority'),
    'allocation_authority':d.get('allocation_authority'),
    'pricing_authority':d.get('pricing_authority'),
    'settlement_authority':d.get('settlement_authority'),
    'payment_action':d.get('payment_action'),
    'revenue_recognition':d.get('revenue_recognition'),
}, indent=2, sort_keys=True))
PY

echo "=== RESULT ==="
echo "revenue_exchange_snapshot_runtime=ready"
echo "commercial_authority=unchanged"
echo "payment_authority=unchanged"
echo "revenue_recognition_authority=unchanged"
