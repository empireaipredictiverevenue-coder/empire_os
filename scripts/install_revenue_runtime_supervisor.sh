#!/usr/bin/env bash
set -u

REPO=/srv/empire_os
SYSTEMD=/etc/systemd/system

cp "$REPO/deploy/systemd/empire-revenue-runtime-supervisor.service"   "$SYSTEMD/empire-revenue-runtime-supervisor.service"
cp "$REPO/deploy/systemd/empire-revenue-runtime-supervisor.timer"   "$SYSTEMD/empire-revenue-runtime-supervisor.timer"

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
