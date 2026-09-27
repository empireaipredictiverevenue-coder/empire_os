#!/usr/bin/env bash
set -uo pipefail

[[ "$(id -u)" -eq 0 ]] || { echo "run as root"; exit 1; }

ROOT="/srv/empire_os"
FAILED=0

run_step() {
  local label="$1"
  shift
  echo
  echo "=== $label ==="
  if "$@"; then
    echo "OK: $label"
    return 0
  fi
  rc=$?
  echo "FAIL: $label rc=$rc"
  FAILED=1
  return 0
}

install -m 0644   "$ROOT/deploy/systemd/empire-data-cloud-backup-observer.service"   /etc/systemd/system/empire-data-cloud-backup-observer.service

install -m 0644   "$ROOT/deploy/systemd/empire-founder-dashboard-api.service"   /etc/systemd/system/empire-founder-dashboard-api.service

run_step "DAEMON RELOAD" systemctl daemon-reload
run_step "BACKUP OBSERVER START"   systemctl start empire-data-cloud-backup-observer.service

if ! test -s /run/empire-data-cloud/pgbackrest.json; then
  echo
  echo "=== BACKUP OBSERVER DIAGNOSTICS ==="
  systemctl --no-pager --full status     empire-data-cloud-backup-observer.service || true
  journalctl -u empire-data-cloud-backup-observer.service     -n 80 --no-pager || true
  namei -l "$ROOT/.venv/bin/python" || true
  namei -l /etc/pgbackrest/empiredb.conf || true
  FAILED=1
else
  echo
  echo "=== BACKUP OBSERVER SNAPSHOT ==="
  cat /run/empire-data-cloud/pgbackrest.json
fi

run_step "PRIVILEGED HELPER RESTART"   systemctl restart empire-ops-privileged-helper.service
run_step "RELIABILITY AGENT RESTART"   systemctl restart empire-reliability-agent.service
run_step "FOUNDER DASHBOARD RESTART"   systemctl restart empire-founder-dashboard-api.service

echo
echo "=== SERVICE STATES ==="
systemctl is-active empire-ops-privileged-helper.service || true
systemctl is-active empire-reliability-agent.service || true
systemctl is-active empire-founder-dashboard-api.service || true

echo
echo "=== INSTALL RESULT ==="
if [[ "$FAILED" -eq 0 ]]; then
  echo '{"empire_data_cloud_observability":"installed","verified":true,"production_cutover_authority":false}'
  exit 0
fi

echo '{"empire_data_cloud_observability":"degraded","verified":false,"production_cutover_authority":false}'
exit 2
