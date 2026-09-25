#!/usr/bin/env bash
set +e
set -o pipefail

ROOT=/srv/empire_os
cd "$ROOT" || exit 2

echo "=== BATCH 1 BUSINESS AGENT TESTS ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m pytest -q   tests/test_buyer_reply_operations_agent.py   tests/test_deliverability_sender_reputation_agent.py   tests/test_source_reliability_agent.py   tests/test_founder_business_agents_api.py   tests/test_control_fabric.py   tests/test_builder_capabilities.py   tests/test_execution_plane_dispatcher.py   tests/coder/test_jobs_worker.py   --tb=short
TEST_RC=$?

echo
echo "=== COMPILE ==="
"$ROOT/.venv/bin/python" -m py_compile   empire_os/buyer_reply_operations_agent.py   empire_os/deliverability_sender_reputation_agent.py   empire_os/source_reliability_agent.py   empire_os/founder_business_agents_api.py   empire_os/builder_capabilities.py   empire_os/empire_coder_capability_probe.py   empire_os/execution_plane_dispatcher.py   empire_os/coder/worker.py
COMPILE_RC=$?

echo
echo "=== RESTART FOUNDER READ API ==="
systemctl --user restart empire-founder-dashboard-api.service
sleep 2

echo
echo "=== FOUNDER BUSINESS AGENTS ==="
curl -fsS   http://127.0.0.1:8766/v1/founder-business-agents/status   | "$ROOT/.venv/bin/python" -m json.tool
FOUNDER_RC=${PIPESTATUS[0]}

echo
echo "=== PI MUTATION CAPABILITY PROBE ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" scripts/pi_tool_call_probe.py
PI_CAP_RC=$?
echo "PI_CAP_RC=$PI_CAP_RC"

echo
echo "=== EMPIRE CODER STRUCTURED-PATCH PROBE ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" scripts/empire_coder_capability_probe.py
CODER_CAP_RC=$?
echo "CODER_CAP_RC=$CODER_CAP_RC"

echo
echo "=== BUILDER CAPABILITY LEDGER ==="
if [[ -f runtime/execution_plane/builder_capabilities.json ]]; then
  "$ROOT/.venv/bin/python" -m json.tool     runtime/execution_plane/builder_capabilities.json
else
  echo "{}"
fi

echo
echo "=== RESULT ==="
echo "TEST_RC=$TEST_RC"
echo "COMPILE_RC=$COMPILE_RC"
echo "FOUNDER_RC=$FOUNDER_RC"
echo "PI_CAP_RC=$PI_CAP_RC"
echo "CODER_CAP_RC=$CODER_CAP_RC"
echo "HEAD=$(git rev-parse --short HEAD)"

if [[ "$TEST_RC" -eq 0 && "$COMPILE_RC" -eq 0 && "$FOUNDER_RC" -eq 0 ]]; then
  exit 0
fi
exit 2
