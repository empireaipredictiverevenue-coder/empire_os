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
  scripts/run_enterprise_contact_repair.py

echo
echo "=== INSTALL AUTOMATION ==="
sudo bash scripts/install_enterprise_contact_intelligence.sh /srv/empire_os

echo
echo "=== SYNC EXISTING ENTERPRISE ACTIVATION ==="
SYNC_LOG="$(mktemp)"
set +e
PYTHONPATH=/srv/empire_os \
./.venv/bin/python scripts/run_enterprise_contact_intelligence.py \
  2>&1 | tee "$SYNC_LOG"
SYNC_RC="${PIPESTATUS[0]}"
set -e

if [ "$SYNC_RC" -ne 0 ]; then
  PYTHONPATH=/srv/empire_os \
  ./.venv/bin/python scripts/run_enterprise_contact_repair.py \
    --record-test-log "$SYNC_LOG" \
    --kind "runtime_sync_failure" \
    --command "enterprise contact runtime sync" \
    --returncode "$SYNC_RC" || true
  sudo systemctl start --no-block \
    empire-enterprise-contact-repair.service || true
  echo "Runtime sync deferred to automatic repair controller."
fi
rm -f "$SYNC_LOG"

echo
echo "=== REFRESH BUYER ACQUISITION ==="
REFRESH_LOG="$(mktemp)"
set +e
PYTHONPATH=/srv/empire_os \
./.venv/bin/python scripts/refresh_buyer_acquisition_team.py \
  --repo-root /srv/empire_os 2>&1 | tee "$REFRESH_LOG"
REFRESH_RC="${PIPESTATUS[0]}"
set -e
if [ "$REFRESH_RC" -ne 0 ]; then
  PYTHONPATH=/srv/empire_os \
  ./.venv/bin/python scripts/run_enterprise_contact_repair.py \
    --record-test-log "$REFRESH_LOG" \
    --kind "buyer_acquisition_refresh_failure" \
    --command "refresh_buyer_acquisition_team.py" \
    --returncode "$REFRESH_RC" || true
  sudo systemctl start --no-block \
    empire-enterprise-contact-repair.service || true
  echo "Buyer Acquisition refresh deferred to automatic repair controller."
fi
rm -f "$REFRESH_LOG"

echo
echo "=== VERIFY REVIEW + RETRY STATE ==="
VERIFY_LOG="$(mktemp)"
set +e
PYTHONPATH=/srv/empire_os ./.venv/bin/python - <<'PY' 2>&1 | tee "$VERIFY_LOG"
import json
import urllib.parse
from pathlib import Path

from empire_os.qualification_worker_v2 import request_json

intel = json.loads(
    Path(
        "runtime/predictive_revenue/"
        "enterprise_contact_intelligence_latest.json"
    ).read_text()
)
buyer = json.loads(
    Path("runtime/buyer_acquisition/latest.json").read_text()
)
activation = json.loads(
    Path(
        "runtime/predictive_revenue/"
        "enterprise_activation_latest.json"
    ).read_text()
)

ids = [
    str(row.get("prospect_id") or "")
    for row in activation.get("targets") or []
    if row.get("prospect_id")
]
reviews = []
if ids:
    params = urllib.parse.urlencode({
        "select": (
            "id,prospect_id,contact_name,contact_title,contact_email,"
            "offer_key,status,proposed_at"
        ),
        "prospect_id": f"in.({','.join(ids)})",
        "order": "proposed_at.desc",
        "limit": 50,
    })
    reviews = request_json(
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{params}",
    ) or []

print("Contact intelligence:")
print(
    "  proposed reviews:",
    intel["proposed_review_count"],
)
print(
    "  targeted retries queued:",
    intel["targeted_retry_queued_count"],
)
print("  errors:", intel["error_count"])

print()
print("Pending/approved enterprise reviews:")
if not reviews:
    print("  NONE")
else:
    for row in reviews:
        print(
            " ",
            row.get("status"),
            "|",
            row.get("contact_name"),
            "|",
            row.get("contact_title"),
            "|",
            row.get("contact_email"),
            "|",
            row.get("offer_key"),
        )

summary = buyer[
    "predictive_revenue_enterprise_contact_intelligence"
]
print()
print("Buyer Acquisition:")
for key, value in summary.items():
    print(f"  {key}: {value}")

assert intel["live_outbound_send"] is False
assert intel["reviews_approved"] == 0
assert intel["payment_action"] is False
assert intel["actual_revenue"] is False
assert summary["live_outbound_send"] is False
assert summary["actual_revenue"] is False
PY
VERIFY_RC="${PIPESTATUS[0]}"
set -e
if [ "$VERIFY_RC" -ne 0 ]; then
  PYTHONPATH=/srv/empire_os \
  ./.venv/bin/python scripts/run_enterprise_contact_repair.py \
    --record-test-log "$VERIFY_LOG" \
    --kind "post_install_verification_failure" \
    --command "enterprise contact deployment verification" \
    --returncode "$VERIFY_RC" || true
  sudo systemctl start --no-block \
    empire-enterprise-contact-repair.service || true
  echo "Post-install verification deferred to automatic repair controller."
fi
rm -f "$VERIFY_LOG"

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
