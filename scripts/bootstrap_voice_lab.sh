#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

echo "=== EMPIRE VOICE LAB BOOTSTRAP ==="

if ! command -v espeak-ng >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y espeak-ng
fi

./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e '.[voice]'

echo "=== DEPENDENCIES ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python - <<'PY'
from empire_os.voice_lab import EmpireVoiceLab
import json
ready = EmpireVoiceLab.dependency_readiness()
print(json.dumps(ready, indent=2, sort_keys=True))
if not all(ready.values()):
    raise SystemExit("Voice Lab dependencies incomplete")
PY

echo "=== VOICE LAB BOOTSTRAP COMPLETE ==="
