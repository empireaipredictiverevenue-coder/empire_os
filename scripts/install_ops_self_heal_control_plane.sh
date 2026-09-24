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
systemctl restart empire-ops-privileged-helper.service

test "$(systemctl is-active empire-ops-privileged-helper.service)" = "active"
test -S /run/empire-ops/privileged.sock

echo "EmpireOS ops self-heal control plane installed."
echo "Privileged helper: active"
echo "Socket: /run/empire-ops/privileged.sock"
