#!/usr/bin/env bash
set +e
cd /srv/empire_os || exit 1

echo "=== AIDER RECOVERY RETEST ==="
echo "HEAD=$(git rev-parse --short HEAD)"

echo
echo "=== STATIC TESTS ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q   tests/test_aider_builder.py   tests/test_aider_capability_probe.py   tests/test_aider_execution_failover.py   tests/test_empire_coder_sandbox_runner.py   tests/test_execution_plane_dispatcher.py   --tb=short
TEST_RC=$?
echo "TEST_RC=$TEST_RC"

echo
echo "=== COMPILE ==="
./.venv/bin/python -m py_compile   empire_os/aider_builder.py   empire_os/aider_capability_probe.py   empire_os/empire_coder_sandbox_runner.py   empire_os/execution_plane_dispatcher.py   scripts/diagnose_aider_gateway.py   scripts/aider_capability_probe.py
COMPILE_RC=$?
echo "COMPILE_RC=$COMPILE_RC"

echo
echo "=== AIDER / OMNIROUTE DIAGNOSTIC ==="
PYTHONPATH=/srv/empire_os   ./.venv/bin/python scripts/diagnose_aider_gateway.py
DIAG_RC=$?
echo "DIAG_RC=$DIAG_RC"

echo
echo "=== MUTATION PROBE ==="
PYTHONPATH=/srv/empire_os   ./.venv/bin/python scripts/aider_capability_probe.py
PROBE_RC=$?
echo "PROBE_RC=$PROBE_RC"

echo
echo "=== AIDER CAPABILITY ==="
./.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path(
    "/srv/empire_os/runtime/execution_plane/builder_capabilities.json"
)
data = json.loads(path.read_text()) if path.exists() else {}
row = (
    ((data.get("workers") or {}).get("empire_coder") or {})
    .get("aider_mutation")
)
print(json.dumps(row or {
    "ready": False,
    "reason": "missing",
}, indent=2, sort_keys=True))
PY

echo
echo "=== DIFF ==="
git diff --check
DIFF_RC=$?
echo "DIFF_RC=$DIFF_RC"

echo
echo "=== RESULT ==="
echo "tests=$TEST_RC compile=$COMPILE_RC diag=$DIAG_RC probe=$PROBE_RC diff=$DIFF_RC"
