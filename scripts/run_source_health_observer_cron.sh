#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

if systemctl is-active --quiet empire-acquisition.timer && systemctl is-enabled --quiet empire-acquisition.timer; then
  export EMPIRE_CANONICAL_ACQUISITION_SCHEDULED=true
else
  export EMPIRE_CANONICAL_ACQUISITION_SCHEDULED=false
fi

readarray -t acquisition_state < <(
  /srv/empire_os/.venv/bin/python - <<'PY'
import json
from pathlib import Path

latest_path = Path('/srv/empire_os/runtime/acquisition/latest.json')
success_path = Path('/srv/empire_os/runtime/acquisition/last_success.json')
try:
    latest = json.loads(latest_path.read_text(encoding='utf-8'))
except Exception:
    latest = {}
try:
    success = json.loads(success_path.read_text(encoding='utf-8'))
except Exception:
    success = {}

authorized = bool(
    success.get('canonical_writes') is True
    and success.get('real_data_only') is True
)
print('true' if authorized else 'false')
print(str(latest.get('metro') or success.get('metro') or 'Austin, TX'))
PY
)

export EMPIRE_CANONICAL_ACQUISITION_AUTHORIZED="${acquisition_state[0]}"
metro="${acquisition_state[1]}"

exec /srv/empire_os/.venv/bin/python \
  /srv/empire_os/scripts/source_health_observer.py \
  --source overpass \
  --metro "$metro" \
  --max-candidates 5 \
  --output /srv/empire_os/runtime/source_health/latest.json
