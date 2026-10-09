#!/usr/bin/env bash
# Safe, founder-scoped systemd health visibility with NO new timer.
set -euo pipefail
umask 077
cd /srv/empire_os
SERVICE=empire-conversation-collector-health.service
SOURCE=deploy/systemd/$SERVICE
DROP=deploy/systemd/empire-department-cycle-conversation-health.conf
DEST_UNIT=/etc/systemd/system/$SERVICE
DEST_DROP=/etc/systemd/system/empire-department-cycle.service.d/99zz-conversation-collector-health.conf
if [[ "$#" -ne 1 || ( "$1" != "--check" && "$1" != "--apply" ) ]]; then
  echo 'USAGE: bash scripts/install_conversation_collector_health.sh --check|--apply' >&2
  exit 2
fi
test -s "$SOURCE" && test -s "$DROP"
test -f scripts/check_conversation_collector_systemd_health.py
grep -Fq 'Type=oneshot' "$SOURCE"
grep -Fq 'User=ubuntu' "$SOURCE"
grep -Fq 'ProtectSystem=strict' "$SOURCE"
grep -Fq 'ExecStartPost=-/usr/bin/systemctl start --no-block empire-conversation-collector-health.service' "$DROP"
if grep -Eq 'OnCalendar|OnUnitInactiveSec|OnBootSec|\\[Timer\\]' "$SOURCE" "$DROP"; then
  echo 'BLOCKED: new timers not permitted' >&2
  exit 3
fi
echo 'HEALTH_MONITOR_PACKAGE_PREFLIGHT=PASS'
echo 'NEW_TIMER_INSTALLED=NO'
echo 'DEPARTMENT_CYCLE_WILL_NOT_BE_BLOCKED=TRUE'
if [[ "$1" == "--check" ]]; then
  echo 'ACTIVATION=NOT_APPLIED'
  exit 0
fi
if [[ "$EUID" -ne 0 ]]; then
  echo 'BLOCKED: approved root session required' >&2
  exit 4
fi
test ! -L "$DEST_UNIT"
test ! -L "$DEST_DROP"
# Never silently replace a concurrent admin's variant of the service.
if [[ -e "$DEST_UNIT" ]]; then cmp -s "$SOURCE" "$DEST_UNIT" || {
  echo 'BLOCKED: existing health unit differs' >&2; exit 5; }; fi
if [[ -e "$DEST_DROP" ]]; then cmp -s "$DROP" "$DEST_DROP" || {
  echo 'BLOCKED: existing department cycle drop-in differs' >&2; exit 6; }; fi
install -o root -g root -m 0644 "$SOURCE" "$DEST_UNIT"
systemctl daemon-reload
# Proof is independent of department cycle; no changes to its current run.
systemctl start "$SERVICE"
test "$(systemctl show -p Result --value "$SERVICE")" = success
test "$(systemctl show -p ExecMainStatus --value "$SERVICE")" = 0
test "$(systemctl show -p ExecMainExitTimestamp --value "$SERVICE")" != n/a
install -d -o root -g root -m 0755 /etc/systemd/system/empire-department-cycle.service.d
install -o root -g root -m 0644 "$DROP" "$DEST_DROP"
systemctl daemon-reload
systemctl cat empire-department-cycle.service | grep -Fq 'ExecStartPost=-/usr/bin/systemctl start --no-block empire-conversation-collector-health.service'
echo 'HEALTH_MONITOR_LIVE_PROOF=PASS'
echo 'DEPARTMENT_CYCLE_RESTARTED=NO'
echo 'ORIGINAL_OPTIONAL_COLLECTOR_STEP_UNCHANGED=YES'
echo 'HEALTH_FAILURE_NOW_INDEPENDENTLY_SYSTEMD_VISIBLE=YES'
