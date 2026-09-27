#!/usr/bin/env bash
set -u

GUARD_STATE="${EMPIRE_SUPABASE_EGRESS_GUARD_STATE:-/srv/empire_os/runtime/control/supabase_egress_guard.json}"
PYTHON_BIN="${EMPIRE_PYTHON_BIN:-python3}"
SYSTEMCTL_BIN="${EMPIRE_SYSTEMCTL_BIN:-systemctl}"

if [[ -r "$GUARD_STATE" ]] && "$PYTHON_BIN" - "$GUARD_STATE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)

raise SystemExit(
    0
    if (
        isinstance(payload, dict)
        and payload.get("state") == "contained"
        and payload.get("contained") is True
    )
    else 1
)
PY
then
  echo "supabase egress contained; revenue runtime supervisor inert"
  exit 0
fi

# Bounded self-healing for the revenue runtime. This script never changes
# commercial authority, sends mail directly, applies migrations, or moves funds.
# It only keeps already-installed, governed EmpireOS runtime units alive.

UNITS=(
  empire-resend-inbound.service
  empire-outbound-governor.timer
  empire-outbound-followup.timer
  empire-gtm-pipeline.timer
  empire-closer-reply-worker.timer
)

failed=0

for unit in "${UNITS[@]}"; do
  if "$SYSTEMCTL_BIN" is-active --quiet "$unit"; then
    echo "ok $unit"
    continue
  fi

  echo "recover $unit"
  "$SYSTEMCTL_BIN" reset-failed "$unit" >/dev/null 2>&1 || true
  if ! "$SYSTEMCTL_BIN" start "$unit"; then
    echo "failed $unit" >&2
    failed=1
  fi
done

# If the governor itself is failed, clear the failed state. Its timer remains
# the cadence authority; do not create a second send loop here.
if "$SYSTEMCTL_BIN" is-failed --quiet empire-outbound-governor.service; then
  echo "reset failed governor service"
  "$SYSTEMCTL_BIN" reset-failed empire-outbound-governor.service || failed=1
fi

exit "$failed"
