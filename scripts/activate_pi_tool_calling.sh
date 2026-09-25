#!/usr/bin/env bash
set -u
set -o pipefail

ROOT=/srv/empire_os
USER_UNIT_DIR="$HOME/.config/systemd/user"
cd "$ROOT" || exit 2

echo "=== UPDATE LLAMA TOOL-CALL SERVICE ==="
install -d -m 0755 "$USER_UNIT_DIR"
install -m 0644   "$ROOT/deploy/systemd-user/empire-llama-coder.service"   "$USER_UNIT_DIR/empire-llama-coder.service"

systemctl --user daemon-reload
systemctl --user restart empire-llama-coder.service
sleep 3

echo
echo "=== LLAMA SERVICE ==="
systemctl --user --no-pager --full status   empire-llama-coder.service | head -35

echo
echo "=== VERIFY JINJA ARGUMENT ==="
systemctl --user show empire-llama-coder.service   -p ExecStart --value | grep -F -- "--jinja"
JINJA_RC=$?

echo
echo "=== LLAMA HEALTH ==="
curl -fsS --max-time 5 http://127.0.0.1:11435/health
HEALTH_RC=$?
echo
echo "JINJA_RC=$JINJA_RC"
echo "HEALTH_RC=$HEALTH_RC"

echo
echo "=== PI REGRESSION ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m pytest -q   tests/test_pi_sandbox_runner.py   tests/test_llama_coder_service.py   tests/test_agent_execution_plane.py   --tb=short
TEST_RC=$?

echo
echo "=== PI TOOL-CALL MUTATION SMOKE ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python"   "$ROOT/scripts/pi_tool_call_mutation_smoke.py"
MUTATION_RC=$?

echo
echo "=== BATCH 1 RETRY ==="
if [[ "$MUTATION_RC" -eq 0 ]]; then
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python"     "$ROOT/scripts/run_batch1_pi_fallback.py"
  BATCH_RC=$?
else
  BATCH_RC=99
fi

echo
echo "=== RESULT ==="
echo "TEST_RC=$TEST_RC"
echo "JINJA_RC=$JINJA_RC"
echo "HEALTH_RC=$HEALTH_RC"
echo "MUTATION_RC=$MUTATION_RC"
echo "BATCH_RC=$BATCH_RC"
echo "HEAD=$(git rev-parse --short HEAD)"

if [[ "$TEST_RC" -eq 0 && "$JINJA_RC" -eq 0 && "$HEALTH_RC" -eq 0 && "$MUTATION_RC" -eq 0 ]]; then
  exit "$BATCH_RC"
fi
exit 2
