#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/srv/empire_os}"
SYSTEMD_DIR="/etc/systemd/system"

install_unit() {
  local source="$1"
  local name
  name="$(basename "$source")"
  test -f "$ROOT/$source"
  install -m 0644 "$ROOT/$source" "$SYSTEMD_DIR/$name"
}

install_unit "deploy/systemd/empire-ops-privileged-helper.service"
install_unit "deploy/systemd/empire-ops-control.service"
install_unit "deploy/systemd/empire-commercial-product-catalog.service"

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

echo "EmpireOS ops self-heal control plane installed."
echo "Privileged helper: active"
echo "Socket: /run/empire-ops/privileged.sock"
