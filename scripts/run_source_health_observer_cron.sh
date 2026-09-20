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
path = Path('/srv/empire_os/runtime/acquisition/latest.json')
try:
    data = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    data = {}
tail = str(data.get('stdout_tail') or '')
authorized = bool(
    data.get('real_data_only') is True
    and data.get('ok') is True
    and '"msg": "prospect_acquired"' in tail
)
print('true' if authorized else 'false')
print(str(data.get('metro') or 'Austin, TX'))
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
