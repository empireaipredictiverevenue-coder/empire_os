#!/usr/bin/env bash
set -u

REPO=/srv/empire_os
SYSTEMD=/etc/systemd/system

UNITS=(
  empire-resend-inbound.service
  empire-outbound-governor.service
  empire-outbound-governor.timer
  empire-outbound-followup.service
  empire-outbound-followup.timer
  empire-gtm-pipeline.service
  empire-gtm-pipeline.timer
  empire-closer-reply-worker.service
  empire-closer-reply-worker.timer
  empire-revenue-runtime-supervisor.service
  empire-revenue-runtime-supervisor.timer
)

for unit in "${UNITS[@]}"; do
  cp "$REPO/deploy/systemd/$unit" "$SYSTEMD/$unit"
done

systemctl daemon-reload

for unit in   empire-outbound-governor.timer   empire-outbound-followup.timer   empire-gtm-pipeline.timer   empire-closer-reply-worker.timer   empire-revenue-runtime-supervisor.timer
do
  systemctl enable --now "$unit" || true
done

systemctl enable --now empire-resend-inbound.service || true

echo "=== ONE GOVERNOR RECOVERY RUN ==="
systemctl reset-failed empire-outbound-governor.service || true
if ! systemctl start empire-outbound-governor.service; then
  echo "governor start failed; journal follows"
  journalctl -u empire-outbound-governor.service -n 120 --no-pager
  exit 2
fi

echo "=== REVENUE RUNTIME STATUS ==="
for unit in   empire-resend-inbound.service   empire-outbound-governor.timer   empire-outbound-followup.timer   empire-gtm-pipeline.timer   empire-closer-reply-worker.timer   empire-revenue-runtime-supervisor.timer
do
  printf "%s: " "$unit"
  systemctl is-active "$unit" || true
done

echo "=== GOVERNOR JOURNAL ==="
journalctl -u empire-outbound-governor.service -n 80 --no-pager
