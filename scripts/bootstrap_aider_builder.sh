#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/srv/empire_os}"
export PATH="/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

echo "=== AIDER BUILDER BOOTSTRAP ==="

UV_BIN="$(command -v uv || true)"
UV_BOOTSTRAP=""
if [ -z "$UV_BIN" ]; then
  echo "=== BOOTSTRAP UV IN DISPOSABLE VENV ==="
  UV_BOOTSTRAP="/var/tmp/empire-uv-bootstrap"
  rm -rf "$UV_BOOTSTRAP"
  python3 -m venv "$UV_BOOTSTRAP"
  "$UV_BOOTSTRAP/bin/python" -m pip install --upgrade pip uv
  UV_BIN="$UV_BOOTSTRAP/bin/uv"
fi

echo "=== INSTALL / UPDATE ISOLATED AIDER TOOL ==="
"$UV_BIN" tool install --force --python 3.12 aider-chat

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

if [ -n "$UV_BOOTSTRAP" ]; then
  rm -rf "$UV_BOOTSTRAP"
fi

echo "=== COMPLETE ==="
