#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/empire_os
SERVICE=empire-autonomous-revenue-os.service
TIMERS=(
  empire-qualification.timer
  empire-qualification-booster.timer
  empire-acquisition.timer
  empire-revenue-exchange-snapshot.timer
)

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

cd "$ROOT"

echo "=== VERIFY RELEASE ==="
bash scripts/verify_autonomous_revenue_os.sh

echo "=== OBSERVE-ONLY PREFLIGHT ==="
EMPIRE_REVENUE_LOOP_INTERNAL_WRITE=0 \
EMPIRE_REVENUE_GAUNTLET_ATTESTED=1 \
EMPIRE_REVENUE_RELEASE_ID=autonomous-revenue-os-v1 \
EMPIRE_REVENUE_CONTINUOUS_LEAD_GENERATION=0 \
PYTHONPATH="$ROOT" \
./.venv/bin/python -m empire_os.autonomous_revenue_os \
  --once --inventory-limit 25 --qualification-limit 5 \
  > runtime/revenue_sprint/autonomous_revenue_cutover_preflight.json

python3 - <<'PY'
import json
p=json.load(open("runtime/revenue_sprint/autonomous_revenue_cutover_preflight.json"))
assert p.get("release_id") == "autonomous-revenue-os-v1", p
assert p.get("status") == "ACTIVE", p
assert p.get("communications_execution") is False, p
assert p.get("booking_execution") is False, p
assert p.get("fund_movement") is False, p
assert p.get("revenue_recognition") is False, p
assert p.get("actual_revenue") is False, p
assert "ARCHITECT" in (p.get("loop") or []), p
print("PREFLIGHT=PASS")
PY

echo "=== INSTALL + RESTART AGENTIC DAEMON ==="
install -m 0644 \
  deploy/systemd/empire-autonomous-revenue-os.service \
  /etc/systemd/system/empire-autonomous-revenue-os.service
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"

echo "=== VERIFY RELEASE HEARTBEAT ==="
ok=0
for _ in $(seq 1 30); do
  if systemctl is-active --quiet "$SERVICE" && python3 - <<'PY' >/dev/null 2>&1
import json
p=json.load(open("/srv/empire_os/runtime/autonomous_revenue_os/latest.json"))
assert p.get("release_id") == "autonomous-revenue-os-v1"
assert p.get("status") in {"STARTING","ACTIVE"}
assert "ARCHITECT" in (p.get("loop") or [])
PY
  then
    ok=1
    break
  fi
  sleep 1
done
if [[ "$ok" -ne 1 ]]; then
  systemctl status "$SERVICE" --no-pager -l || true
  journalctl -u "$SERVICE" -n 100 --no-pager || true
  echo "CUTOVER_ABORTED=daemon_release_heartbeat_missing"
  exit 1
fi

timers_disabled=0
rollback() {
  rc=$?
  if [[ $rc -ne 0 && $timers_disabled -eq 1 ]]; then
    echo "=== ROLLBACK DUPLICATE TIMERS ==="
    for unit in "${TIMERS[@]}"; do
      systemctl enable --now "$unit" >/dev/null 2>&1 || true
    done
  fi
  exit $rc
}
trap rollback EXIT

echo "=== RETIRE DUPLICATE TIMER OWNERSHIP ==="
for unit in "${TIMERS[@]}"; do
  if systemctl cat "$unit" >/dev/null 2>&1; then
    systemctl disable --now "$unit"
  fi
done
timers_disabled=1

sleep 5
systemctl is-active --quiet "$SERVICE"

for unit in "${TIMERS[@]}"; do
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    echo "CUTOVER_ABORTED=timer_still_active:$unit" >&2
    exit 1
  fi
  if systemctl is-enabled --quiet "$unit" 2>/dev/null; then
    echo "CUTOVER_ABORTED=timer_still_enabled:$unit" >&2
    exit 1
  fi
done

python3 - <<'PY'
import json
p=json.load(open("/srv/empire_os/runtime/autonomous_revenue_os/latest.json"))
assert p.get("release_id") == "autonomous-revenue-os-v1"
assert p.get("status") in {"STARTING","ACTIVE"}
assert p.get("actual_revenue") is False
assert p.get("execution_authority") in {"none","observe","bounded_internal"}
print("DAEMON_STATE=PASS")
PY

echo "=== FINAL STATUS ==="
systemctl status "$SERVICE" --no-pager -l
for unit in "${TIMERS[@]}"; do
  printf '%s enabled=' "$unit"
  systemctl is-enabled "$unit" 2>/dev/null || true
  printf '%s active=' "$unit"
  systemctl is-active "$unit" 2>/dev/null || true
done

echo "=== CURRENT AUTONOMOUS REVENUE SUMMARY ==="
python3 - <<'PY'
import json
p=json.load(open("/srv/empire_os/runtime/autonomous_revenue_os/latest.json"))
inv=p.get("inventory") or {}
print(json.dumps({
  "release_id":p.get("release_id"),
  "status":p.get("status"),
  "cycle_at":p.get("cycle_at"),
  "inventory_counts":inv.get("counts"),
  "inventory_recovery":p.get("inventory_recovery"),
  "qualification_decision":p.get("qualification_decision"),
  "lead_generation_decision":p.get("lead_generation_decision"),
  "lead_generation_executed":p.get("lead_generation_executed"),
  "next_action":p.get("next_action"),
  "review_queue_count":len(p.get("review_queue") or []),
  "actual_revenue":p.get("actual_revenue"),
},indent=2,sort_keys=True,default=str))
PY

trap - EXIT
echo "CUTOVER=COMPLETE"
