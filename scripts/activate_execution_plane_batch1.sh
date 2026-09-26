#!/usr/bin/env bash
set -u
set -o pipefail

ROOT=/srv/empire_os
cd "$ROOT" || exit 2

stage() {
  printf '\n=== %s ===\n' "$1"
}

failures=0

stage "ARCHITECTURE GATE"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m pytest -q   tests/test_master_execution_ledger.py   tests/test_agent_execution_plane.py   tests/test_execution_lease.py   tests/test_pi_sandbox_runner.py   tests/test_agent_tool_runtime.py   tests/test_agent_reach_sensor.py   tests/test_agent_tool_bootstraps.py   tests/test_execution_plane_dispatcher.py   tests/test_execution_plane_verification.py   tests/test_candidate_verification.py   tests/test_execution_result_reconciler.py   tests/test_founder_execution_plane_api.py   tests/test_control_fabric.py   tests/test_architecture_contract.py   --tb=short
ARCH_RC=$?
echo "ARCH_RC=$ARCH_RC"
if [[ "$ARCH_RC" -ne 0 ]]; then
  echo "BLOCKED: architecture gate failed; activation not attempted"
  exit "$ARCH_RC"
fi

stage "BOOTSTRAP PI"
sudo bash scripts/bootstrap_pi_agent.sh
PI_RC=$?
echo "PI_BOOTSTRAP_RC=$PI_RC"
[[ "$PI_RC" -ne 0 ]] && failures=$((failures + 1))

stage "BOOTSTRAP AGENT REACH"
sudo bash scripts/bootstrap_agent_reach.sh
REACH_RC=$?
echo "AGENT_REACH_BOOTSTRAP_RC=$REACH_RC"
[[ "$REACH_RC" -ne 0 ]] && failures=$((failures + 1))

stage "BOOTSTRAP SPACE AGENT"
sudo bash scripts/bootstrap_space_agent.sh
SPACE_RC=$?
echo "SPACE_BOOTSTRAP_RC=$SPACE_RC"
[[ "$SPACE_RC" -ne 0 ]] && failures=$((failures + 1))

stage "TOOL HEALTH"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - <<'PY'
import json
from empire_os.agent_tool_runtime import execution_tool_health_snapshot
print(json.dumps(execution_tool_health_snapshot(), indent=2, sort_keys=True))
PY

stage "FOUNDER READ API"
systemctl --user restart empire-founder-dashboard-api.service
sleep 2
curl -fsS   http://127.0.0.1:8766/v1/founder-execution-plane/status   | "$ROOT/.venv/bin/python" -m json.tool   | head -180
FOUNDER_RC=${PIPESTATUS[0]}
echo "FOUNDER_API_RC=$FOUNDER_RC"
[[ "$FOUNDER_RC" -ne 0 ]] && failures=$((failures + 1))

stage "START HERMES BATCH 1"
sudo systemctl start empire-hermes-control.service
HERMES_RC=$?
echo "HERMES_START_RC=$HERMES_RC"
[[ "$HERMES_RC" -ne 0 ]] && failures=$((failures + 1))

stage "RUN PI DATA QUALITY BATCH"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" scripts/run_batch1_data_quality_pi.py
PI_BUILD_RC=$?
echo "PI_BUILD_RC=$PI_BUILD_RC"
[[ "$PI_BUILD_RC" -ne 0 ]] && failures=$((failures + 1))

stage "AGENT REACH PUBLIC SENSOR SMOKE"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - <<'PY'
import json
from empire_os.agent_reach_sensor import run_public_sensor
try:
    payload = run_public_sensor("github", "predictive revenue intelligence", limit=3)
except Exception as exc:
    payload = {
        "status": "DEGRADED",
        "error": f"{type(exc).__name__}: {exc}",
        "truth_authority": "none",
        "execution_authority": "none",
    }
print(json.dumps(payload, indent=2, sort_keys=True))
PY

stage "SPACE AGENT LOOPBACK"
curl -fsS --max-time 5 http://127.0.0.1:3010/ >/dev/null
SPACE_HEALTH_RC=$?
echo "SPACE_HEALTH_RC=$SPACE_HEALTH_RC"
[[ "$SPACE_HEALTH_RC" -ne 0 ]] && failures=$((failures + 1))
ss -ltnp | grep -E ':(3010|8769|11435)\b' || true

stage "HERMES STATUS"
sudo systemctl --no-pager --full status empire-hermes-control.service | head -50 || true

stage "MASTER LEDGER"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" scripts/master_execution_status.py   --output runtime/execution_plane/master_ledger.json
"$ROOT/.venv/bin/python" - <<'PY'
import json
x=json.load(open("runtime/execution_plane/master_ledger.json"))
s=x["summary"]
print("TOTAL:", s["total"])
print("DONE:", s["done"])
print("PENDING:", s["pending"])
PY

stage "ACTIVATION SUMMARY"
echo "FAILURE_COUNT=$failures"
echo "HEAD=$(git rev-parse --short HEAD)"
if [[ "$failures" -eq 0 ]]; then
  echo "EXECUTION_PLANE_ACTIVATION=GREEN"
  exit 0
fi
echo "EXECUTION_PLANE_ACTIVATION=DEGRADED"
exit 1
