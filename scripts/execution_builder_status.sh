#!/usr/bin/env bash
set -u
set -o pipefail

ROOT=/srv/empire_os
cd "$ROOT" || exit 2

echo "=== HEAD ==="
git rev-parse --short HEAD

echo
echo "=== BUILDER / MODEL PROCESSES ==="
ps -eo pid,etime,pcpu,pmem,cmd |   grep -E 'activate_empire_coder_builder|run_batch1_pi_fallback|llama-server|ollama' |   grep -v grep || true

echo
echo "=== BUILDER CAPABILITIES ==="
if [[ -f runtime/execution_plane/builder_capabilities.json ]]; then
  "$ROOT/.venv/bin/python" -m json.tool     runtime/execution_plane/builder_capabilities.json
else
  echo "builder_capabilities.json not written yet"
fi

echo
echo "=== ACTIVE EXECUTION LEASES ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - <<'PY'
import json
from empire_os.execution_lease import ExecutionLeaseManager
print(json.dumps(ExecutionLeaseManager().active(), indent=2, sort_keys=True))
PY

echo
echo "=== BATCH 1 PROPOSAL BRANCHES ==="
git ls-remote --heads origin   'refs/heads/empire-coder/job-batch1-*'   'refs/heads/pi/job-batch1-*' || true

echo
echo "=== EXECUTION PLANE REQUESTS ==="
find runtime/execution_plane/requests -maxdepth 2 -type f -name 'batch1-*.json'   -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' 2>/dev/null | sort || true

echo
echo "=== RECENT EXECUTION TELEMETRY ==="
tail -n 20 runtime/telemetry/execution_plane.jsonl 2>/dev/null || true

echo
echo "=== LOCAL MODEL HEALTH ==="
curl -fsS --max-time 3 http://127.0.0.1:11435/health || true
echo
