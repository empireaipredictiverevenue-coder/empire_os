#!/usr/bin/env bash
set -euo pipefail

[[ "$(id -u)" -eq 0 ]] || { echo "run as root"; exit 1; }

ROOT="/srv/empire_os"

install -m 0644   "$ROOT/deploy/systemd/empire-data-cloud-backup-observer.service"   /etc/systemd/system/empire-data-cloud-backup-observer.service

install -m 0644   "$ROOT/deploy/systemd/empire-founder-dashboard-api.service"   /etc/systemd/system/empire-founder-dashboard-api.service

systemctl daemon-reload

systemctl start empire-data-cloud-backup-observer.service
systemctl restart empire-ops-privileged-helper.service
systemctl restart empire-reliability-agent.service
systemctl restart empire-founder-dashboard-api.service

systemctl is-active --quiet empire-ops-privileged-helper.service
systemctl is-active --quiet empire-reliability-agent.service
systemctl is-active --quiet empire-founder-dashboard-api.service

test -s /run/empire-data-cloud/pgbackrest.json

echo '{"empire_data_cloud_observability":"installed","verified":true,"production_cutover_authority":false}'
