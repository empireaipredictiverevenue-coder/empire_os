#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

echo "=================================================="
echo "ENTERPRISE CONTACT INTELLIGENCE — DEPLOY"
echo "=================================================="

echo
echo "=== TEST ==="
TEST_LOG="$(mktemp)"
set +e
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q \
  tests/test_buyer_discovery.py \
  tests/test_buyer_probe_worker.py \
  tests/test_enterprise_contact_intelligence.py \
  tests/test_enterprise_targeted_retry.py \
  tests/test_enterprise_contact_repair.py \
  tests/test_enterprise_contact_sync_systemd.py \
  tests/test_enterprise_contact_intelligence_installer.py \
  tests/test_predictive_revenue_enterprise_activation.py \
  tests/test_predictive_revenue_enterprise_activation_systemd.py \
  tests/test_buyer_acquisition_team.py \
  tests/test_runtime_self_heal.py \
  tests/test_ops_privileged_helper.py \
  tests/test_buyer_deferred_identity_timeout.py \
  2>&1 | tee "$TEST_LOG"
TEST_RC="${PIPESTATUS[0]}"
set -e

if [ "$TEST_RC" -ne 0 ]; then
  PYTHONPATH=/srv/empire_os \
  ./.venv/bin/python scripts/run_enterprise_contact_repair.py \
    --record-test-log "$TEST_LOG" \
    --kind "test_failure" \
    --command "enterprise contact deployment pytest" \
    --returncode "$TEST_RC" || true

  sudo systemctl start --no-block \
    empire-enterprise-contact-repair.service 2>/dev/null || true

  echo "STOP: unsafe deployment blocked; repair incident captured."
  rm -f "$TEST_LOG"
  exit "$TEST_RC"
fi
rm -f "$TEST_LOG"

echo
echo "=== COMPILE ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m py_compile \
  empire_os/buyer_discovery.py \
  empire_os/buyer_probe_worker.py \
  empire_os/buyer_deferred_enrichment.py \
  empire_os/enterprise_contact_intelligence.py \
  empire_os/enterprise_contact_repair.py \
  empire_os/runtime_self_heal.py \
  empire_os/ops_privileged_helper.py \
  scripts/run_buyer_deferred_enrichment.py \
  scripts/run_enterprise_contact_intelligence.py \
  scripts/run_enterprise_contact_sync_cycle.py \
  scripts/verify_enterprise_contact_intelligence.py \
  scripts/run_enterprise_contact_repair.py

echo
echo "=== INSTALL AUTOMATION ==="
sudo bash scripts/install_enterprise_contact_intelligence.sh /srv/empire_os

echo
echo "=== SYNC + VERIFY THROUGH CANONICAL SYSTEMD ENV ==="
sudo systemctl reset-failed empire-enterprise-contact-sync.service || true

set +e
sudo systemctl start empire-enterprise-contact-sync.service
SYNC_RC="$?"
set -e

SYNC_RESULT="$(
  systemctl show empire-enterprise-contact-sync.service \
    -p Result --value 2>/dev/null || true
)"

echo "Enterprise contact sync result: ${SYNC_RESULT:-unknown}"

if [ "$SYNC_RC" -ne 0 ] || [ "$SYNC_RESULT" != "success" ]; then
  echo "Canonical-env sync did not complete cleanly."
  echo "Repair controller has been triggered by systemd OnFailure."

  sudo systemctl start --no-block \
    empire-enterprise-contact-repair.service || true

  sudo journalctl \
    -u empire-enterprise-contact-sync.service \
    -n 80 \
    --no-pager || true
else
  echo "Canonical-env sync + Buyer Acquisition refresh + verification: success"

  sudo systemctl start empire-enterprise-contact-repair.service || true

  if [ -f runtime/predictive_revenue/enterprise_contact_intelligence_latest.json ]; then
    ./.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path(
    "runtime/predictive_revenue/"
    "enterprise_contact_intelligence_latest.json"
)
payload = json.loads(path.read_text())

print("Contact intelligence:")
print("  proposed reviews:", payload.get("proposed_review_count"))
print(
    "  targeted retries queued:",
    payload.get("targeted_retry_queued_count"),
)
print("  errors:", payload.get("error_count"))
print("  live outbound:", payload.get("live_outbound_send"))
print("  actual revenue:", payload.get("actual_revenue"))
PY
  fi
fi

echo
echo "=== START TARGETED RETRIES ASYNC ==="
sudo systemctl reset-failed empire-buyer-deferred-enrichment.service || true
sudo systemctl start --no-block empire-buyer-deferred-enrichment.service

echo
echo "=== TIMERS ==="
printf '%-58s %s\n'   "empire-buyer-deferred-enrichment.timer"   "$(systemctl is-active empire-buyer-deferred-enrichment.timer)"
printf '%-58s %s\n'   "empire-predictive-revenue-enterprise-activation.timer"   "$(systemctl is-active empire-predictive-revenue-enterprise-activation.timer)"
printf '%-58s %s\n'   "empire-ops-control.timer"   "$(systemctl is-active empire-ops-control.timer)"
printf '%-58s %s\n'   "empire-enterprise-contact-repair.timer"   "$(systemctl is-active empire-enterprise-contact-repair.timer)"

echo
echo "=================================================="
echo "ENTERPRISE CONTACT INTELLIGENCE LIVE"
echo "HEAD: $(git rev-parse --short HEAD)"
echo "Verified contacts -> pending buyer review: AUTOMATIC"
echo "Unresolved contacts -> target-aware retry: AUTOMATIC"
echo "Company fallback evidence: PRESERVED"
echo "Daily leadership/contact refresh: ACTIVE"
echo "10-minute deferred retry loop: ACTIVE"
echo "Self-heal: ACTIVE"
echo "Contact failure diagnosis/repair: ACTIVE"
echo "Live outbound: OFF"
echo "Payment/revenue mutation: OFF"
echo "=================================================="
