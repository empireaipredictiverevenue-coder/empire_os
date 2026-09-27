#!/usr/bin/env bash
set -u
set -o pipefail

ROOT=/srv/empire_os
cd "$ROOT" || exit 2

echo "=== ARCHITECTURE / BUILDER REGRESSION ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m pytest -q   tests/test_builder_capabilities.py   tests/test_empire_coder_sandbox_runner.py   tests/test_execution_plane_dispatcher.py   tests/test_agent_execution_plane.py   --tb=short
TEST_RC=$?

echo
echo "=== LOCAL MODEL HEALTH ==="
curl -fsS --max-time 5 http://127.0.0.1:11435/health
MODEL_RC=$?
echo
echo "TEST_RC=$TEST_RC"
echo "MODEL_RC=$MODEL_RC"

echo
echo "=== PROVE EMPIRE CODER STRUCTURED PATCH MUTATION ==="
if [[ "$TEST_RC" -eq 0 && "$MODEL_RC" -eq 0 ]]; then
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - <<'PY'
import json
from empire_os.empire_coder_capability_probe import (
    probe_empire_coder_structured_patch,
)
result = probe_empire_coder_structured_patch("/srv/empire_os")
print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
raise SystemExit(0 if result.ok else 2)
PY
  PROBE_RC=$?
else
  PROBE_RC=99
fi

echo
echo "=== CAPABILITY EVIDENCE ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - <<'PY'
import json
from empire_os.builder_capabilities import builder_capability_snapshot
print(json.dumps(builder_capability_snapshot(), indent=2, sort_keys=True))
PY

echo
echo "=== BATCH 1 THROUGH CAPABLE BUILDER ==="
if [[ "$PROBE_RC" -eq 0 ]]; then
  PYTHONPATH="$ROOT"   "$ROOT/.venv/bin/python" scripts/run_batch1_pi_fallback.py
  BATCH_RC=$?
else
  BATCH_RC=99
fi

echo
echo "=== RESULT ==="
echo "TEST_RC=$TEST_RC"
echo "MODEL_RC=$MODEL_RC"
echo "PROBE_RC=$PROBE_RC"
echo "BATCH_RC=$BATCH_RC"
echo "HEAD=$(git rev-parse --short HEAD)"

if [[ "$TEST_RC" -eq 0 && "$MODEL_RC" -eq 0 && "$PROBE_RC" -eq 0 ]]; then
  exit "$BATCH_RC"
fi
exit 2
