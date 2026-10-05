#!/usr/bin/env bash
set -euo pipefail

REPO=/srv/empire_os
UNIT_SRC="$REPO/deploy/systemd/empire-ops-mcp.service"
UNIT_DST=/etc/systemd/system/empire-ops-mcp.service
DROPIN_DIR=/etc/systemd/system/empire-ops-mcp.service.d
ENV_FILE=/etc/empire_os/remote-commander.env
ACTIVATE=0

if [[ "${1:-}" == "--activate" ]]; then
  ACTIVATE=1
fi

cd "$REPO"

echo "=== EMPIRE REMOTE COMMANDER BOOTSTRAP ==="
echo "repo=$REPO"
echo "activation_requested=$ACTIVATE"

test -f "$UNIT_SRC"
test -f empire_os/remote_commander.py
test -f empire_os/ops_mcp.py

"$REPO/.venv/bin/python" -m py_compile   empire_os/remote_commander.py   empire_os/ops_mcp.py

"$REPO/.venv/bin/python" -m pytest -q   tests/test_remote_commander.py   tests/test_ops_mcp_auth.py   tests/test_hermes_ops_bridge.py

if [[ ! -f "$ENV_FILE" ]]; then
  sudo "$REPO/.venv/bin/python"     "$REPO/scripts/rotate_empire_remote_commander_token.py"
fi

sudo install -m 0644 "$UNIT_SRC" "$UNIT_DST"
sudo mkdir -p "$DROPIN_DIR"
sudo tee "$DROPIN_DIR/30-remote-commander.conf" >/dev/null <<'EOF'
[Service]
EnvironmentFile=-/etc/empire_os/remote-commander.env
EOF

sudo systemctl daemon-reload

if [[ "$ACTIVATE" -eq 1 ]]; then
  sudo systemctl enable --now empire-ops-privileged-helper.service
  sudo systemctl enable --now empire-ops-mcp.service
  sudo systemctl restart empire-ops-mcp.service
  systemctl --no-pager --full status empire-ops-mcp.service || true
else
  echo "activation=HELD"
  echo "reason=founder_gate"
fi

echo "bootstrap=complete"
