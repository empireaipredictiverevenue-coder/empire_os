#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

echo "=================================================="
echo "CONTINUOUS BUYER LANES — DEPLOY"
echo "=================================================="

echo
echo "=== TEST ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q \
  tests/test_icp_buyer_trigger_intelligence.py \
  tests/test_buyer_acquisition_scout.py \
  tests/test_buyer_scout_persistence.py \
  tests/test_buyer_acquisition_scout_systemd.py \
  tests/test_buyer_scout_reconciliation.py \
  tests/test_buyer_scout_review_readiness.py \
  tests/test_buyer_scout_promotion_plan.py \
  tests/test_continuous_buyer_lanes_deployer.py

echo
echo "=== COMPILE ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m py_compile \
  empire_os/icp_buyer_trigger_intelligence.py \
  empire_os/buyer_acquisition_scout.py \
  empire_os/buyer_scout_persistence.py \
  scripts/run_buyer_acquisition_scout.py

echo
echo "=== INSTALL SERVICE + TIMER ==="
sudo install -m 0644 \
  deploy/systemd/empire-buyer-acquisition-scout.service \
  /etc/systemd/system/empire-buyer-acquisition-scout.service
sudo install -m 0644 \
  deploy/systemd/empire-buyer-acquisition-scout.timer \
  /etc/systemd/system/empire-buyer-acquisition-scout.timer
sudo systemctl daemon-reload
sudo systemctl enable --now empire-buyer-acquisition-scout.timer

echo
echo "=== RUN FIRST CONTINUOUS DISCOVERY CYCLE ==="
sudo systemctl reset-failed empire-buyer-acquisition-scout.service || true
sudo systemctl start empire-buyer-acquisition-scout.service

echo
echo "=== VERIFY ==="
systemctl is-active empire-buyer-acquisition-scout.timer
systemctl show empire-buyer-acquisition-scout.service \
  -p Result -p ExecMainStatus --no-pager

./.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("runtime/buyer_acquisition/scout_latest.json")
payload = json.loads(path.read_text())
print("Scout:")
print("  queries:", payload.get("query_count"))
print("  domains:", payload.get("domain_count"))
print("  search domains:", payload.get("search_domain_count"))
print(
    "  canonical fallback domains:",
    payload.get("canonical_seed_domain_count"),
)
print(
    "  canonical fallback used:",
    payload.get("canonical_seed_fallback_used"),
)
print("  candidates:", payload.get("candidate_count"))
print("  lane candidates:")
for lane, count in sorted(
    (payload.get("continuous_lane_candidate_counts") or {}).items()
):
    print(f"    {lane}: {count}")
print("  outbound sent:", payload.get("outbound_sent"))
print("  actual revenue:", payload.get("actual_revenue"))
PY

echo
echo "=================================================="
echo "CONTINUOUS BUYER LANES ACTIVE"
echo "HEAD: $(git rev-parse --short HEAD)"
echo "Enterprise unresolved contacts: 10-minute retry loop"
echo "Net-new company discovery: 30-minute Buyer Scout loop"
echo "Canonical legal/insurance seed fallback: ACTIVE when search is empty"
echo "Lanes: Predictive Revenue / Legal Mass Tort / Legal / Insurance"
echo "Discovery/probing/reconciliation/persistence: AUTOMATIC"
echo "Individual plaintiff targeting: OFF"
echo "Live outbound: UNCHANGED / GOVERNED"
echo "=================================================="
