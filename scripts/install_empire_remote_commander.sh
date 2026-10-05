#!/usr/bin/env bash
set -euo pipefail

TARGET_REPO="${EMPIRE_REMOTE_COMMANDER_TARGET_REPO:-/srv/empire_os}"
CODE_ROOT="${EMPIRE_REMOTE_COMMANDER_CODE_ROOT:-$TARGET_REPO}"
PYTHON="${EMPIRE_REMOTE_COMMANDER_PYTHON:-$TARGET_REPO/.venv/bin/python}"

UNIT_SRC="$CODE_ROOT/deploy/systemd/empire-ops-mcp.service"
UNIT_DST=/etc/systemd/system/empire-ops-mcp.service
HELPER_UNIT_SRC="$CODE_ROOT/deploy/systemd/empire-ops-privileged-helper.service"
HELPER_UNIT_DST=/etc/systemd/system/empire-ops-privileged-helper.service
MCP_DROPIN_DIR=/etc/systemd/system/empire-ops-mcp.service.d
HELPER_DROPIN_DIR=/etc/systemd/system/empire-ops-privileged-helper.service.d
ENV_FILE=/etc/empire_os/remote-commander.env
ACTIVATE=0

if [[ "${1:-}" == "--activate" ]]; then
  ACTIVATE=1
fi

echo "=== EMPIRE REMOTE COMMANDER BOOTSTRAP ==="
echo "target_repo=$TARGET_REPO"
echo "code_root=$CODE_ROOT"
echo "python=$PYTHON"
echo "activation_requested=$ACTIVATE"

test -d "$TARGET_REPO/.git"
test -x "$PYTHON"
test -f "$UNIT_SRC"
test -f "$HELPER_UNIT_SRC"
test -f "$CODE_ROOT/empire_os/remote_commander.py"
test -f "$CODE_ROOT/empire_os/ops_mcp.py"

"$PYTHON" - <<'PY'
import importlib
for name in ("mcp", "yaml"):
    importlib.import_module(name)
print("runtime_dependencies=ready")
PY

cd "$CODE_ROOT"
PYTHONPATH="$CODE_ROOT" "$PYTHON" -m py_compile   empire_os/remote_commander.py   empire_os/ops_mcp.py   empire_os/ops_privileged_helper.py

PYTHONPATH="$CODE_ROOT" "$PYTHON" -m pytest -q   tests/test_remote_commander.py   tests/test_ops_mcp_auth.py   tests/test_hermes_ops_bridge.py

if [[ ! -s "$ENV_FILE" ]]; then
  sudo "$PYTHON" "$CODE_ROOT/scripts/rotate_empire_remote_commander_token.py"
fi

sudo install -m 0644 "$UNIT_SRC" "$UNIT_DST"
sudo install -m 0644 "$HELPER_UNIT_SRC" "$HELPER_UNIT_DST"
sudo mkdir -p "$MCP_DROPIN_DIR" "$HELPER_DROPIN_DIR"

sudo tee "$MCP_DROPIN_DIR/40-remote-commander-release.conf" >/dev/null <<EOF
[Service]
WorkingDirectory=$CODE_ROOT
Environment=PYTHONPATH=$CODE_ROOT
EnvironmentFile=-/etc/empire_os/remote-commander.env
ExecStart=
ExecStart=$PYTHON -m empire_os.ops_mcp --transport streamable-http --host 127.0.0.1 --port 8765
EOF

sudo tee "$HELPER_DROPIN_DIR/40-remote-commander-release.conf" >/dev/null <<EOF
[Service]
WorkingDirectory=$CODE_ROOT
Environment=PYTHONPATH=$CODE_ROOT
ExecStart=
ExecStart=$PYTHON -m empire_os.ops_privileged_helper --socket /run/empire-ops/privileged.sock --allowed-user ubuntu
EOF

sudo systemctl daemon-reload

if [[ "$ACTIVATE" -eq 1 ]]; then
  sudo systemctl enable --now empire-ops-privileged-helper.service
  sudo systemctl restart empire-ops-privileged-helper.service
  sudo systemctl enable --now empire-ops-mcp.service
  sudo systemctl restart empire-ops-mcp.service
  systemctl is-active --quiet empire-ops-privileged-helper.service
  systemctl is-active --quiet empire-ops-mcp.service
  echo "local_activation=complete"
else
  echo "activation=HELD"
  echo "reason=founder_gate"
fi

echo "bootstrap=complete"
