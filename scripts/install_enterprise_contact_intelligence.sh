#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/srv/empire_os}"
SYSTEMD_DIR="/etc/systemd/system"

install -d -m 0750 -o ubuntu -g ubuntu \
  /home/ubuntu/empire_os_repair_worktrees

install_unit() {
  local source="$1"
  local name
  name="$(basename "$source")"
  test -f "$ROOT/$source"
  install -m 0644 "$ROOT/$source" "$SYSTEMD_DIR/$name"
}

install_unit "deploy/systemd/empire-ops-privileged-helper.service"
install_unit "deploy/systemd/empire-buyer-deferred-enrichment.service"
install_unit "deploy/systemd/empire-buyer-deferred-enrichment.timer"
install_unit "deploy/systemd/empire-predictive-revenue-enterprise-activation.service"
install_unit "deploy/systemd/empire-predictive-revenue-enterprise-activation.timer"
install_unit "deploy/systemd/empire-enterprise-contact-sync.service"
install_unit "deploy/systemd/empire-enterprise-contact-repair.service"
install_unit "deploy/systemd/empire-enterprise-contact-repair.timer"

systemctl daemon-reload

systemctl enable empire-ops-privileged-helper.service
systemctl reset-failed empire-ops-privileged-helper.service || true
systemctl restart empire-ops-privileged-helper.service

READY=0
for _ in $(seq 1 20); do
  if [ "$(systemctl is-active empire-ops-privileged-helper.service 2>/dev/null || true)" = "active" ] \
    && [ -S /run/empire-ops/privileged.sock ]; then
    READY=1
    break
  fi
  sleep 0.5
done
if [ "$READY" -ne 1 ]; then
  echo "ERROR: privileged helper did not become ready"
  systemctl status empire-ops-privileged-helper.service --no-pager -l || true
  journalctl -u empire-ops-privileged-helper.service -n 100 --no-pager || true
  exit 1
fi

systemctl enable --now empire-buyer-deferred-enrichment.timer
systemctl enable --now empire-predictive-revenue-enterprise-activation.timer
systemctl enable --now empire-enterprise-contact-repair.timer

test "$(systemctl is-active empire-buyer-deferred-enrichment.timer)" = "active"
test "$(systemctl is-active empire-predictive-revenue-enterprise-activation.timer)" = "active"
test "$(systemctl is-active empire-enterprise-contact-repair.timer)" = "active"

echo "EmpireOS enterprise contact intelligence installed."
echo "Privileged helper: active"
echo "Deferred buyer enrichment timer: active"
echo "Enterprise contact refresh timer: active"
echo "Enterprise contact repair timer: active"
echo "Live outbound authority: unchanged"
