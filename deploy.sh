#!/usr/bin/env bash
# deploy.sh — sync host empire_os code into the empire-hub incus container
# and restart the running services. Prevents host/container code drift
# (the root cause of the stale 'simulated' charge bug).
#
# Usage:  ./deploy.sh [--no-restart] [--smoke]
set -uo pipefail

CONTAINER="empire-hub"
HOST_REPO="/root/empire_os"
HOST_SRC="${HOST_REPO}/empire_os"
CT_SRC="/root/empire_os/empire_os"
RESTART=1
SMOKE=0

for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=0 ;;
    --smoke)      SMOKE=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# sanity: container must exist
if ! incus list -c n --format csv | grep -qx "$CONTAINER"; then
  echo "FATAL: container '$CONTAINER' not found via 'incus list'" >&2
  exit 3
fi

echo "==> pushing host ${HOST_SRC}/*.py -> ${CONTAINER}:${CT_SRC}"
pushed=0
while IFS= read -r f; do
  rel="${f#${HOST_SRC}/}"                       # strip absolute host prefix
  incus file push "$f" "${CONTAINER}${CT_SRC}/${rel}" >/dev/null 2>&1 \
    && { printf '.'; pushed=$((pushed+1)); } \
    || { echo "  FAILED: $rel" >&2; }
done < <(find "$HOST_SRC" -name '*.py' -not -path '*/skills_library/*')
echo " pushed ${pushed} files"

if [[ "$RESTART" -eq 1 ]]; then
  echo "==> restarting pm2 services in ${CONTAINER}"
  incus exec "$CONTAINER" -- pm2 restart empire-hub-service empire-north-mini 2>&1 \
    | grep -E "restarting|online" || true
  # poll /health up to 15s (hub may take a few sec to rebind)
  ready=0
  for i in $(seq 1 15); do
    code=$(incus exec "$CONTAINER" -- curl -s -m 4 -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || true)
    if [[ "$code" == "200" ]]; then ready=1; break; fi
    sleep 4
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "WARN: hub /health not 200 after 15s (last=$code) — smoke may be unreliable"
  fi
fi

if [[ "$SMOKE" -eq 1 ]]; then
  echo "==> smoke: canonical USDT/BSC rail + hub health (no payment mutation)"
  incus exec "$CONTAINER" -- bash -c 'cd /root/empire_os && /root/venv/bin/python3 - <<PYEOF
import sys
sys.path.insert(0, "/root/empire_os")
from empire_os.payment_rail_policy import canonical_payment_rail
from empire_os.bsc_usdt_verifier import BSC_MAINNET_CHAIN_ID, BSC_USDT_CONTRACT
rail = canonical_payment_rail()
assert rail["asset"] == "USDT", rail
assert rail["network"] == "BSC", rail
assert rail["chain_id"] == 56 == BSC_MAINNET_CHAIN_ID, rail
assert BSC_USDT_CONTRACT.startswith("0x") and len(BSC_USDT_CONTRACT) == 42
assert rail["actual_revenue"] is False
print("SMOKE OK: canonical settlement=USDT/BSC chain=56; no payment mutation")
PYEOF'
fi
echo "==> deploy complete"
