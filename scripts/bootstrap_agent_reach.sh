#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/bootstrap_agent_reach.sh" >&2
  exit 1
fi

ROOT=/srv/empire_os
PREFIX=/opt/empire/agent-reach
STATE=/var/lib/empire/agent-reach
HOME_DIR="$STATE/home"
REVISION=a19a171fa980a0785849596492e0af4db800c82f
TARGET_USER="${SUDO_USER:-ubuntu}"
[[ "$TARGET_USER" == "root" ]] && TARGET_USER=ubuntu

echo "=== AGENT REACH ARCHITECTURE GATE ==="
test -f "$ROOT/docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md"
test -f "$ROOT/docs/ARCHITECTURE_FIRST_ENGINEERING_DOCTRINE.md"

echo "=== PYTHON GATE ==="
PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "BLOCKED: python3 required" >&2
  exit 2
fi
"$PYTHON_BIN" --version

echo "=== PREPARE ISOLATED RUNTIME ==="
install -d -m 0755 "$PREFIX"
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER" "$STATE"
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER" "$HOME_DIR"

rm -rf "$PREFIX/venv"
"$PYTHON_BIN" -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$PREFIX/venv/bin/pip" install   "git+https://github.com/Panniantong/Agent-Reach.git@$REVISION"
export PATH="$PREFIX/venv/bin:/usr/local/bin:/usr/bin:/bin"

echo "=== VERSION ==="
HOME="$HOME_DIR"   "$PREFIX/venv/bin/agent-reach" version

echo "=== SAFE INSTALL AUDIT ONLY ==="
set +e
HOME="$HOME_DIR"   "$PREFIX/venv/bin/agent-reach" install --env=server --safe
SAFE_RC=$?
set -e
echo "SafeAuditExit=$SAFE_RC"

echo "=== MACHINE-READABLE DOCTOR ==="
set +e
HOME="$HOME_DIR"   "$PREFIX/venv/bin/agent-reach" doctor --json   >"$STATE/doctor.json"
DOCTOR_RC=$?
set -e
chmod 0600 "$STATE/doctor.json"
chown "$TARGET_USER:$TARGET_USER" "$STATE/doctor.json"
echo "DoctorExit=$DOCTOR_RC"

echo "=== COMPLETE ==="
echo "AgentReach=$PREFIX/venv/bin/agent-reach"
echo "IsolatedHome=$HOME_DIR"
echo "SystemDependencyInstallPerformed=false"
echo "BrowserCookieReusePerformed=false"
echo "TruthAuthority=none"
