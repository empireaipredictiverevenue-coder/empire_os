#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

echo "=================================================="
echo "EMPIREOS OPS HEALTH — FINAL VERIFY"
echo "=================================================="

echo
echo "=== TARGETED TESTS ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q   tests/test_ops_sentinel.py   tests/test_incident_manager.py   tests/test_ops_control_health_summary.py   tests/test_runtime_self_heal.py   tests/test_ops_control_runtime_doctor.py

echo
echo "=== FRESH OPS CONTROL CYCLE ==="
sudo systemctl reset-failed empire-ops-control.service || true
sudo systemctl start empire-ops-control.service

RESULT="$(
  systemctl show empire-ops-control.service     -p Result --value
)"
echo "Ops Control result: $RESULT"

if [ "$RESULT" != "success" ]; then
  sudo systemctl status empire-ops-control.service --no-pager -l || true
  sudo journalctl -u empire-ops-control.service -n 120 --no-pager || true
  exit 1
fi

echo
echo "=== STRUCTURED HEALTH ==="
./.venv/bin/python - <<'PY'
import json
from pathlib import Path

ops = json.loads(Path("runtime/ops_control/latest.json").read_text())
doctor = ops["runtime_doctor"]

print("Overall healthy:", ops["healthy"])
print("Ops mode:", ops["mode"])
print("Blocking findings:", ops["blocking_finding_count"])
print("Health domains:")
for key, value in ops["health_domains"].items():
    print(f"  {key:34} {value}")

print()
print("Runtime Doctor:")
print("  status:", doctor["status"])
print("  Empire units:", doctor["system_unit_count"])
print("  checks:", doctor["check_count"])
print("  unresolved:", doctor["unresolved_count"])
print("  repairs:", doctor["repair_count"])
print("  inventory findings:", doctor["inventory_finding_count"])
print("  founder gates:", doctor["founder_gate_required_count"])

print()
print("Blocking findings:")
if not ops["blocking_findings"]:
    print("  NONE")
else:
    for row in ops["blocking_findings"]:
        print(
            f'  {row["severity"].upper()} | {row["code"]} | '
            f'{row["component"]} | {row["summary"]}'
        )
        print("    evidence:", row.get("evidence") or {})

blocking_ids = {
    (row["code"], row["component"])
    for row in ops["blocking_findings"]
}
infos = [
    row
    for row in ops["sentinel"]["findings"]
    if (row["code"], row["component"]) not in blocking_ids
]

print()
print("Informational findings:")
if not infos:
    print("  NONE")
else:
    for row in infos:
        print(
            f'  {row["severity"].upper()} | {row["code"]} | '
            f'{row["component"]} | {row["summary"]}'
        )

assert ops["mode"] == "GUARDED_EXECUTE"
assert doctor["status"] == "HEALTHY"
assert doctor["unresolved_count"] == 0
assert doctor["actual_revenue"] is False
PY

echo
echo "=== CONTROL PLANE ==="
for UNIT in   empire-ops-control.timer   empire-ops-privileged-helper.service   empire-public-gateway.service   empire-self-serve-checkout.service   empire-ops-mcp.service
do
  printf '%-48s %s\n'     "$UNIT"     "$(systemctl is-active "$UNIT" || true)"
done

echo
echo "=================================================="
echo "OPS HEALTH VERIFY COMPLETE"
echo "HEAD: $(git rev-parse --short HEAD)"
echo "=================================================="
