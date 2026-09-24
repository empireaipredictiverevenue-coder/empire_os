#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

echo "=================================================="
echo "LEGACY PERMIT RECOVERY OBSERVER — DEPLOY"
echo "=================================================="

echo
echo "=== TEST ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q \
  tests/test_legacy_permit_recovery.py \
  tests/test_legacy_permit_recovery_runner.py \
  tests/test_legacy_permit_recovery_systemd.py \
  tests/test_permit_intelligence_runtime.py

echo
echo "=== COMPILE ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m py_compile \
  empire_os/legacy_permit_recovery.py \
  scripts/run_legacy_permit_recovery_observer.py

echo
echo "=== INSTALL SERVICE + TIMER ==="
sudo install -m 0644 \
  deploy/systemd/empire-legacy-permit-recovery.service \
  /etc/systemd/system/empire-legacy-permit-recovery.service
sudo install -m 0644 \
  deploy/systemd/empire-legacy-permit-recovery.timer \
  /etc/systemd/system/empire-legacy-permit-recovery.timer
sudo systemctl daemon-reload

echo
echo "=== RUN FIRST OBSERVE CYCLE ==="
sudo systemctl reset-failed empire-legacy-permit-recovery.service || true
sudo systemctl start empire-legacy-permit-recovery.service

echo
echo "=== ENABLE TIMER ==="
sudo systemctl enable --now empire-legacy-permit-recovery.timer

echo
echo "=== VERIFY ==="
systemctl is-active empire-legacy-permit-recovery.timer
systemctl show empire-legacy-permit-recovery.service \
  -p Result -p ExecMainStatus --no-pager

./.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("runtime/recovery/legacy_permit_recovery_latest.json")
payload = json.loads(path.read_text())

print("Recovery observer:")
print("  mode:", payload.get("mode"))
print("  scanned:", payload.get("scanned_row_count"))
print("  processed:", payload.get("processed_count"))
print("  classifications:", payload.get("classification_counts"))
print("  states:", payload.get("recovery_state_counts"))
print("  identity matches:", payload.get("identity_match_counts"))
print("  next offset:", payload.get("next_offset"))
print("  database write:", payload.get("database_write_performed"))
print("  promotion:", payload.get("canonical_promotion_performed"))
print("  outbound:", payload.get("outbound_sent"))
print("  revenue:", payload.get("actual_revenue"))
PY

echo
echo "=================================================="
echo "LEGACY PERMIT RECOVERY OBSERVER ACTIVE"
echo "HEAD: $(git rev-parse --short HEAD)"
echo "Batch: 250 records"
echo "Cadence: 30 minutes"
echo "Mode: OBSERVE"
echo "Canonical prospect promotion: OFF"
echo "Live outbound: OFF"
echo "Revenue recognition: OFF"
echo "=================================================="
