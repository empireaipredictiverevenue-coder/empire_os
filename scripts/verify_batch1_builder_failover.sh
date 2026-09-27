#!/usr/bin/env bash
set +e
set -o pipefail

ROOT=/srv/empire_os
USER_UNIT_DIR="$HOME/.config/systemd/user"
cd "$ROOT" || exit 2

echo "=== INSTALL PROVEN LOCAL MODEL SERVICE CONFIG ==="
install -d -m 0755 "$USER_UNIT_DIR"
install -m 0644 \
  "$ROOT/deploy/systemd-user/empire-llama-coder.service" \
  "$USER_UNIT_DIR/empire-llama-coder.service"
systemctl --user daemon-reload
systemctl --user restart empire-llama-coder.service
sleep 3

echo
echo "=== FOCUSED BATCH 1 + BUILDER FAILOVER TESTS ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m pytest -q \
  tests/test_buyer_reply_operations_agent.py \
  tests/test_deliverability_sender_reputation_agent.py \
  tests/test_source_reliability_agent.py \
  tests/test_founder_business_agents_api.py \
  tests/test_execution_plane_dispatcher.py \
  tests/test_empire_coder_sandbox_runner.py \
  tests/test_builder_capabilities.py \
  tests/coder/test_structured_patch.py \
  tests/test_llama_coder_service.py \
  --tb=short
TEST_RC=$?

echo
echo "=== COMPILE ==="
"$ROOT/.venv/bin/python" -m py_compile \
  empire_os/buyer_reply_operations_agent.py \
  empire_os/deliverability_sender_reputation_agent.py \
  empire_os/source_reliability_agent.py \
  empire_os/execution_plane_dispatcher.py \
  empire_os/empire_coder_sandbox_runner.py \
  empire_os/empire_coder_capability_probe.py \
  empire_os/coder/structured_patch.py
COMPILE_RC=$?

echo
echo "=== LOCAL LLAMA HEALTH ==="
curl -fsS --max-time 5 http://127.0.0.1:11435/health
LLAMA_RC=$?
echo
echo "LLAMA_RC=$LLAMA_RC"

echo
echo "=== PI NATIVE TOOL-CALL CAPABILITY — INFORMATIONAL ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" scripts/pi_tool_call_probe.py
PI_CAP_RC=$?
echo "PI_CAP_RC=$PI_CAP_RC"
echo "PI_CAPABILITY_REQUIRED_FOR_PASS=false"

echo
echo "=== EMPIRE CODER STRUCTURED-PATCH CAPABILITY — GATING ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" \
  scripts/empire_coder_capability_probe.py
CODER_CAP_RC=$?
echo "CODER_CAP_RC=$CODER_CAP_RC"

echo
echo "=== BUILDER CAPABILITY LEDGER ==="
if [[ -f runtime/execution_plane/builder_capabilities.json ]]; then
  "$ROOT/.venv/bin/python" -m json.tool \
    runtime/execution_plane/builder_capabilities.json
else
  echo "{}"
fi

echo
echo "=== RESTART FOUNDER READ API ==="
systemctl --user restart empire-founder-dashboard-api.service
sleep 2
curl -fsS \
  http://127.0.0.1:8766/v1/founder-business-agents/status \
  | "$ROOT/.venv/bin/python" -m json.tool
FOUNDER_RC=${PIPESTATUS[0]}

echo
echo "=== RESULT ==="
echo "TEST_RC=$TEST_RC"
echo "COMPILE_RC=$COMPILE_RC"
echo "LLAMA_RC=$LLAMA_RC"
echo "PI_CAP_RC=$PI_CAP_RC"
echo "CODER_CAP_RC=$CODER_CAP_RC"
echo "FOUNDER_RC=$FOUNDER_RC"
echo "HEAD=$(git rev-parse --short HEAD)"

if [[ "$TEST_RC" -eq 0 \
   && "$COMPILE_RC" -eq 0 \
   && "$LLAMA_RC" -eq 0 \
   && "$CODER_CAP_RC" -eq 0 \
   && "$FOUNDER_RC" -eq 0 ]]; then
  echo "BATCH1_AND_LOCAL_BUILDER_FAILOVER=GREEN"
  exit 0
fi
echo "BATCH1_AND_LOCAL_BUILDER_FAILOVER=DEGRADED"
exit 2
