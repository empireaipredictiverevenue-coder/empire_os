#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

echo "========================================================"
echo " EMPIRE OUTBOUND — READ-ONLY PRODUCTION READINESS PROBE"
echo " NO MIGRATION / NO ROLE CHANGE / NO SERVICE CHANGE / NO SEND"
echo "========================================================"

fail=0

check_cmd() {
  local label="$1"
  shift
  echo
  echo "=== $label ==="
  if "$@"; then
    :
  else
    rc=$?
    echo "BLOCKED: $label (exit=$rc)"
    fail=1
  fi
}

echo
echo "=== RELEASE IDENTITY ==="
git rev-parse --short HEAD || true
git branch --show-current || true

check_cmd "RINGLEADER PREFLIGHT"   ./.venv/bin/python -m empire_os.outbound_ringleader_preflight

echo
echo "=== RESEND PROVIDER-EVENT INGEST HEALTH ==="
if curl --fail --silent --show-error   --max-time 3   http://127.0.0.1:8097/health
then
  echo
else
  echo "BLOCKED: provider-event ingest health unavailable"
  fail=1
fi

echo
echo "=== OBSERVER HEARTBEAT WATCHDOG ==="
if ./.venv/bin/python -m empire_os.outbound_ringleader_watchdog; then
  :
else
  rc=$?
  echo "BLOCKED: observer heartbeat not current (exit=$rc)"
  fail=1
fi

echo
echo "=== SYSTEMD STATE ==="
units=(
  empire-resend-inbound.service
  empire-outbound-ringleader-observer.service
  empire-outbound-ringleader-observer.timer
  empire-outbound-ringleader-watchdog.service
  empire-outbound-ringleader-watchdog.timer
)

for unit in "${units[@]}"; do
  active="$(systemctl is-active "$unit" 2>/dev/null || true)"
  enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
  printf '%-48s active=%-10s enabled=%s\n' "$unit" "$active" "$enabled"

  case "$unit" in
    *.timer)
      if [[ "$active" != "active" ]]; then
        fail=1
      fi
      ;;
    empire-resend-inbound.service)
      if [[ "$active" != "active" ]]; then
        fail=1
      fi
      ;;
    *)
      # oneshot observer/watchdog services are timer-driven; inactive after a
      # successful run is normal. Failed is not.
      if [[ "$active" == "failed" ]]; then
        fail=1
      fi
      ;;
  esac
done

echo
echo "=== EMPIREDB ACTIVATION PROBE ==="
probe_dsn="${EMPIRE_OUTBOUND_ACTIVATION_PROBE_DSN:-${EMPIREDB_MIGRATOR_DSN:-}}"
if [[ -z "$probe_dsn" ]]; then
  echo "BLOCKED: EMPIRE_OUTBOUND_ACTIVATION_PROBE_DSN or EMPIREDB_MIGRATOR_DSN required"
  fail=1
else
  if EMPIRE_OUTBOUND_ACTIVATION_PROBE_DSN="$probe_dsn"     ./.venv/bin/python -m empire_os.outbound_empiredb_activation_probe
  then
    :
  else
    rc=$?
    echo "BLOCKED: EmpireDB outbound schema/role probe failed (exit=$rc)"
    fail=1
  fi
fi

echo
echo "=== AUTHORITY ASSERTIONS ==="
echo "database_activation_authorized=false"
echo "service_activation_authorized=false"
echo "dns_mutation_authorized=false"
echo "provisioning_authorized=false"
echo "send_authorized=false"

echo
if [[ "$fail" -eq 0 ]]; then
  echo "RESULT: OBSERVE_PRODUCTION_PREREQUISITES_VISIBLE"
  echo "NOTE: this probe does not activate or authorize anything."
  exit 0
fi

echo "RESULT: BLOCKED"
exit 2
