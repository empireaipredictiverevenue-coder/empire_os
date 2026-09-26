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
  tests/test_legacy_permit_recovery_batching.py \
  tests/test_legacy_permit_recovery_cursor.py \
  tests/test_legacy_permit_project_only.py \
  tests/test_legacy_permit_inventory.py \
  tests/test_permits_source_identity.py \
  tests/test_permits_owner_quality.py \
  tests/test_permit_intelligence_runtime.py

echo
echo "=== COMPILE ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m py_compile \
  empire_os/legacy_permit_recovery.py \
  empire_os/legacy_permit_inventory.py \
  empire_os/lead_sources/permits.py \
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
print("  owner canonical matches:", payload.get("identity_match_counts"))
print(
    "  source owner identity:",
    payload.get("source_owner_identity_counts"),
)
print(
    "  permittee phone evidence:",
    payload.get("source_permittee_phone_counts"),
)
print(
    "  inventory identity modes:",
    payload.get("inventory_identity_mode_counts"),
)
print("  next offset:", payload.get("next_offset"))

summary_path = Path(
    "runtime/recovery/legacy_permit_inventory_summary.json"
)
if summary_path.exists():
    summary = json.loads(summary_path.read_text())
    print("Cumulative inventory:")
    print("  unique:", summary.get("unique_inventory_records"))
    print(
        "  verified current:",
        summary.get("verified_current_inventory"),
    )
    print(
        "  owner identified:",
        summary.get("verified_current_owner_identified"),
    )
    print(
        "  project only:",
        summary.get("verified_current_project_only"),
    )
    print(
        "  full scan complete:",
        summary.get("full_scan_complete"),
    )
print("  database write:", payload.get("database_write_performed"))
print("  promotion:", payload.get("canonical_promotion_performed"))
print("  outbound:", payload.get("outbound_sent"))
print("  revenue:", payload.get("actual_revenue"))
PY

echo
echo "=================================================="
echo "LEGACY PERMIT RECOVERY OBSERVER ACTIVE"
echo "HEAD: $(git rev-parse --short HEAD)"
echo "Batch: 500 unique prospects"
echo "Cadence: 15 minutes"
echo "Mode: OBSERVE"
echo "Canonical prospect promotion: OFF"
echo "Live outbound: OFF"
echo "Revenue recognition: OFF"
echo "=================================================="
