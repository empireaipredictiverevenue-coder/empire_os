#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/bootstrap_promptfoo_runtime.sh" >&2
  exit 1
fi

ROOT=/srv/empire_os
PREFIX=/opt/empire/promptfoo
PACKAGE='promptfoo@0.123.1'
TARGET_USER="${SUDO_USER:-ubuntu}"
[[ "$TARGET_USER" == "root" ]] && TARGET_USER=ubuntu

echo "=== PROMPTFOO ARCHITECTURE GATE ==="
test -f "$ROOT/docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md"
test -f "$ROOT/evals/empire_core_policy/promptfooconfig.yaml"

NODE_SOURCE="$(command -v node || true)"
NPM_SOURCE="$(command -v npm || true)"
if [[ -z "$NODE_SOURCE" || -z "$NPM_SOURCE" ]]; then
  echo "BLOCKED: node/npm required" >&2
  exit 2
fi

echo "=== PIN NODE + PROMPTFOO ==="
install -d -m 0755 "$PREFIX/bin"
install -m 0755 "$NODE_SOURCE" "$PREFIX/bin/node"
npm install   --prefix "$PREFIX"   --omit=optional   --ignore-scripts   --no-audit   --no-fund   "$PACKAGE"

ENTRY="$PREFIX/node_modules/promptfoo/dist/src/main.js"
if [[ ! -f "$ENTRY" ]]; then
  ENTRY="$(readlink -f "$PREFIX/node_modules/.bin/promptfoo")"
fi
test -f "$ENTRY"

cat >"$PREFIX/bin/promptfoo" <<EOF
#!/usr/bin/env bash
exec "$PREFIX/bin/node" "$ENTRY" "\$@"
EOF
chmod 0755 "$PREFIX/bin/promptfoo"

"$PREFIX/bin/promptfoo" --version

echo "=== PREPARE VERIFICATION STATE ==="
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER"   "$ROOT/runtime/execution_plane"   "$ROOT/runtime/execution_plane/promptfoo_requests"   "$ROOT/runtime/execution_plane/promptfoo_results"   "$ROOT/runtime/execution_plane/candidate_patches"   /var/tmp/empire-promptfoo

echo "=== INSTALL WORKER UNITS ==="
install -m 0644   "$ROOT/deploy/systemd/empire-execution-plane-promptfoo.service"   /etc/systemd/system/empire-execution-plane-promptfoo.service
install -m 0644   "$ROOT/deploy/systemd/empire-execution-plane-promptfoo.timer"   /etc/systemd/system/empire-execution-plane-promptfoo.timer

systemctl daemon-reload
systemctl enable --now empire-execution-plane-promptfoo.timer

echo "=== COMPLETE ==="
echo "Promptfoo=$PREFIX/bin/promptfoo"
echo "ExecutionAuthority=none"
