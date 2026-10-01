#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/empire_os
ASTRA_SERVICE=empire-astra-dispatcher.service
ASTRA_TIMER=empire-astra-dispatcher.timer
DEPT_SERVICE=empire-department-cycle.service
DEPT_TIMER=empire-department-cycle.timer

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root (sudo bash scripts/install_astra_orchestration_runtime.sh)" >&2
  exit 2
fi

cd "$ROOT"

echo "=== ASTRA ORCHESTRATION PRODUCTION INSTALL ==="

systemctl stop "$ASTRA_TIMER" "$DEPT_TIMER"

for unit in "$ASTRA_SERVICE" "$DEPT_SERVICE"; do
  for _ in $(seq 1 120); do
    if ! systemctl is-active --quiet "$unit"; then
      break
    fi
    sleep 1
  done
  if systemctl is-active --quiet "$unit"; then
    echo "ERROR: $unit did not quiesce within 120 seconds" >&2
    exit 3
  fi
done

install -m 0644   deploy/systemd/empire-astra-dispatcher.service   /etc/systemd/system/empire-astra-dispatcher.service
install -m 0644   deploy/systemd/empire-astra-dispatcher.timer   /etc/systemd/system/empire-astra-dispatcher.timer
install -m 0644   deploy/systemd/empire-department-cycle.service   /etc/systemd/system/empire-department-cycle.service
install -m 0644   deploy/systemd/empire-department-cycle.timer   /etc/systemd/system/empire-department-cycle.timer

# One-time ownership normalization. Queue files remain mode 0600; only the
# owning runtime identity changes from historical root to the least-privilege
# application user used by both producer and consumer.
chown -R ubuntu:ubuntu "$ROOT/runtime/departments/work"
chown ubuntu:ubuntu "$ROOT/runtime/astra"

systemctl daemon-reload
systemctl enable "$ASTRA_TIMER" "$DEPT_TIMER"

echo "=== FIRST GOVERNED CYCLE ==="
systemctl start "$ASTRA_SERVICE"
systemctl start "$DEPT_SERVICE"

systemctl restart "$ASTRA_TIMER" "$DEPT_TIMER"

echo "=== VERIFY IDENTITY ==="
test "$(systemctl show -p User --value "$ASTRA_SERVICE")" = "ubuntu"
test "$(systemctl show -p Group --value "$ASTRA_SERVICE")" = "ubuntu"
test "$(systemctl show -p User --value "$DEPT_SERVICE")" = "ubuntu"
test "$(systemctl show -p Group --value "$DEPT_SERVICE")" = "ubuntu"

if find "$ROOT/runtime/departments/work"   -type f ! -user ubuntu -print -quit | grep -q .; then
  echo "ERROR: department queue still contains non-ubuntu-owned files" >&2
  exit 4
fi

systemctl is-active --quiet "$ASTRA_TIMER"
systemctl is-active --quiet "$DEPT_TIMER"

echo "=== INSTALLED CONTRACT ==="
systemctl cat "$ASTRA_SERVICE" "$DEPT_SERVICE"   | grep -E 'User=|Group=|EnvironmentFile=|EMPIRE_ASTRA_DISPATCH_MODE|ExecStart='
systemctl cat "$ASTRA_TIMER" "$DEPT_TIMER"   | grep -E 'OnUnitInactiveSec='

echo "=== RESULT ==="
echo "astra_orchestration_runtime=ready"
echo "live_outbound_authority=unchanged"
echo "payment_authority=unchanged"
echo "revenue_recognition_authority=unchanged"
