#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/srv/empire_os}"
export PATH="/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

echo "=== AIDER BUILDER BOOTSTRAP ==="

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required for an isolated Aider installation." >&2
  echo "Install uv, then rerun this bootstrap." >&2
  exit 2
fi

echo "=== INSTALL / UPDATE ISOLATED AIDER TOOL ==="
uv tool install --force --python python3.12 aider-chat

AIDER_BIN="$(command -v aider || true)"
if [ -z "$AIDER_BIN" ]; then
  for candidate in     /home/ubuntu/.local/bin/aider     /usr/local/bin/aider
  do
    if [ -x "$candidate" ]; then
      AIDER_BIN="$candidate"
      break
    fi
  done
fi

if [ -z "$AIDER_BIN" ] || [ ! -x "$AIDER_BIN" ]; then
  echo "ERROR: aider executable not found after installation" >&2
  exit 3
fi

echo "=== VERSION ==="
"$AIDER_BIN" --version

echo "=== OMNIROUTE CONFIG PRESENCE ==="
if [ ! -r /etc/empire_os/omniroute-hermes.env ]; then
  echo "ERROR: protected OmniRoute env is not readable by this user" >&2
  exit 4
fi
grep -q '^OPENAI_BASE_URL=' /etc/empire_os/omniroute-hermes.env
grep -q '^OPENAI_API_KEY=' /etc/empire_os/omniroute-hermes.env
echo "OmniRoute provider config present; secrets not printed."

echo "=== STATIC TESTS ==="
cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT"   "$REPO_ROOT/.venv/bin/python" -m pytest -q   tests/test_aider_builder.py   tests/test_aider_execution_failover.py   tests/test_empire_coder_sandbox_runner.py   --tb=short

echo "=== LIVE DISPOSABLE-CLONE CAPABILITY PROBE ==="
EMPIRE_AIDER_EXECUTABLE="$AIDER_BIN" PYTHONPATH="$REPO_ROOT"   "$REPO_ROOT/.venv/bin/python"   scripts/aider_capability_probe.py

echo "=== CAPABILITY LEDGER ==="
"$REPO_ROOT/.venv/bin/python" - <<'PY'
import json
from pathlib import Path
path = Path("/srv/empire_os/runtime/execution_plane/builder_capabilities.json")
data = json.loads(path.read_text()) if path.exists() else {}
row = ((data.get("workers") or {}).get("empire_coder") or {}).get("aider_mutation")
print(json.dumps(row or {"ready": False, "reason": "missing"}, indent=2, sort_keys=True))
PY

echo "=== COMPLETE ==="
