#!/usr/bin/env bash
set -u

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
  if systemctl is-active --quiet "$unit"; then
    echo "ok $unit"
    continue
  fi

  echo "recover $unit"
  systemctl reset-failed "$unit" >/dev/null 2>&1 || true
  if ! systemctl start "$unit"; then
    echo "failed $unit" >&2
    failed=1
  fi
done

# If the governor itself is failed, clear the failed state. Its timer remains
# the cadence authority; do not create a second send loop here.
if systemctl is-failed --quiet empire-outbound-governor.service; then
  echo "reset failed governor service"
  systemctl reset-failed empire-outbound-governor.service || failed=1
fi

exit "$failed"
