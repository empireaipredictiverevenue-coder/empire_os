#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/bootstrap_space_agent.sh" >&2
  exit 1
fi

ROOT=/srv/empire_os
PREFIX=/opt/empire/space-agent
SOURCE="$PREFIX/source"
STATE=/var/lib/empire/space-agent
CUSTOMWARE="$STATE/customware"
CONFIG_DIR=/etc/empire_os
ADMIN_ENV="$CONFIG_DIR/space-agent-admin.env"
ADMIN_MARKER="$STATE/.admin_created"
REVISION=10f4ffdaf50a8136cf8450d17c11286178fd58e6
TARGET_USER="${SUDO_USER:-ubuntu}"
[[ "$TARGET_USER" == "root" ]] && TARGET_USER=ubuntu

echo "=== SPACE AGENT ARCHITECTURE GATE ==="
test -f "$ROOT/docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md"
test -f "$ROOT/docs/ARCHITECTURE_FIRST_ENGINEERING_DOCTRINE.md"

echo "=== NODE GATE ==="
NODE_SOURCE="$(command -v node || true)"
NPM_SOURCE="$(command -v npm || true)"
if [[ -z "$NODE_SOURCE" || -z "$NPM_SOURCE" ]]; then
  echo "BLOCKED: node/npm required" >&2
  exit 2
fi
"$NODE_SOURCE" -e '
const [M]=process.versions.node.split(".").map(Number);
if (M < 20) process.exit(3);
'
echo "Node=$("$NODE_SOURCE" -p 'process.versions.node')"

echo "=== PREPARE PATHS ==="
install -d -m 0755 "$PREFIX"
install -d -m 0755 "$PREFIX/bin"
install -m 0755 "$NODE_SOURCE" "$PREFIX/bin/node"
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER" "$STATE"
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER" "$CUSTOMWARE"
install -d -m 0755 "$CONFIG_DIR"

echo "=== PIN SPACE AGENT SOURCE ==="
if [[ ! -d "$SOURCE/.git" ]]; then
  rm -rf "$SOURCE"
  git clone https://github.com/agent0ai/space-agent.git "$SOURCE"
fi
git -C "$SOURCE" fetch --depth=1 origin "$REVISION"
git -C "$SOURCE" checkout --detach "$REVISION"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$REVISION"

echo "=== INSTALL DEPENDENCIES ==="
chown -R "$TARGET_USER:$TARGET_USER" "$SOURCE"
cd "$SOURCE"
sudo -u "$TARGET_USER" npm ci --ignore-scripts --no-audit --no-fund

echo "=== CONFIGURE LOOPBACK WORKSPACE ==="
"$PREFIX/bin/node" "$SOURCE/space.js" set   CUSTOMWARE_PATH="$CUSTOMWARE"   LOGIN_ALLOWED=true   ALLOW_GUEST_USERS=false   CLOUD_SHARE_ALLOWED=false   CUSTOMWARE_GIT_HISTORY=true   HOST=127.0.0.1   PORT=3010   WORKERS=1

echo "=== CREATE FOUNDER ADMIN IF NEEDED ==="
if [[ ! -f "$ADMIN_ENV" ]]; then
  ADMIN_PASSWORD="$(openssl rand -base64 36 | tr -d '\n')"
  cat >"$ADMIN_ENV" <<EOF
SPACE_AGENT_ADMIN_USER=empire-founder
SPACE_AGENT_ADMIN_PASSWORD=$ADMIN_PASSWORD
EOF
  chmod 0640 "$ADMIN_ENV"
  chown root:"$TARGET_USER" "$ADMIN_ENV"
fi

if [[ ! -f "$ADMIN_MARKER" ]]; then
  set -a
  source "$ADMIN_ENV"
  set +a
  sudo -u "$TARGET_USER"     "$PREFIX/bin/node" "$SOURCE/space.js" user create       "$SPACE_AGENT_ADMIN_USER"       --password "$SPACE_AGENT_ADMIN_PASSWORD"       --full-name "Empire Founder"       --groups _admin
  touch "$ADMIN_MARKER"
  chown "$TARGET_USER:$TARGET_USER" "$ADMIN_MARKER"
  chmod 0600 "$ADMIN_MARKER"
fi

echo "=== CONFIGURE EMPIRE LOCAL MODEL ==="
MODEL_ID="$(
  curl -fsS --max-time 3 http://127.0.0.1:11435/v1/models 2>/dev/null     | python3 -c '
import json,sys
try:
    payload=json.load(sys.stdin)
    rows=payload.get("data") or []
    print(str((rows[0] if rows else {}).get("id") or ""))
except Exception:
    print("")
' || true
)"
if [[ -z "$MODEL_ID" ]]; then
  echo "BLOCKED: local llama.cpp model not discoverable" >&2
  exit 3
fi

FOUNDER_ROOT="$CUSTOMWARE/L2/empire-founder"
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER"   "$FOUNDER_ROOT/conf"

cat >"$FOUNDER_ROOT/conf/admin-chat.yaml" <<EOF
api_endpoint: "http://127.0.0.1:11435/v1/chat/completions"
api_key: "local-only"
llm_provider: "api"
model: "$MODEL_ID"
max_tokens: 4096
params: "temperature:0.2"
supports_vision: false
custom_system_prompt: |
  You are the Empire Founder Workspace agent.
  Architecture first, implementation second, verification before promotion.
  Treat Empire read APIs as evidence, never as permission to mutate production.
  Never send outreach, accept terms, move funds, recognize revenue, deploy production,
  or bypass Control Fabric. Route build requests through the Empire Execution Plane.
EOF

cat >"$FOUNDER_ROOT/conf/onscreen-agent.yaml" <<EOF
api_endpoint: "http://127.0.0.1:11435/v1/chat/completions"
api_key: "local-only"
llm_provider: "api"
model: "$MODEL_ID"
max_tokens: 4096
params: "temperature:0.2"
supports_vision: false
custom_system_prompt: |
  You are a bounded Empire Founder Workspace assistant.
  Use workspace tools for presentation and internal UI only.
  Do not mutate Empire canonical systems directly.
EOF

chown "$TARGET_USER:$TARGET_USER"   "$FOUNDER_ROOT/conf/admin-chat.yaml"   "$FOUNDER_ROOT/conf/onscreen-agent.yaml"
chmod 0600   "$FOUNDER_ROOT/conf/admin-chat.yaml"   "$FOUNDER_ROOT/conf/onscreen-agent.yaml"

echo "SpaceModel=$MODEL_ID"

echo "=== INSTALL SERVICE ==="
install -m 0644   "$ROOT/deploy/systemd/empire-space-agent.service"   /etc/systemd/system/empire-space-agent.service
systemctl daemon-reload
systemctl enable --now empire-space-agent.service

echo "=== LOOPBACK HEALTH ==="
READY=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 2 http://127.0.0.1:3010/ >/dev/null; then
    READY=1
    break
  fi
  sleep 2
done
if [[ "$READY" -ne 1 ]]; then
  systemctl --no-pager --full status empire-space-agent.service | head -50 || true
  journalctl -u empire-space-agent.service -n 80 --no-pager || true
  exit 4
fi

if ss -ltnH '( sport = :3010 )' | awk '{print $4}'   | grep -Ev '^(127\.0\.0\.1|\[::1\]):3010$' | grep -q .; then
  echo "BLOCKED: Space Agent is not loopback-only" >&2
  ss -ltnp | grep ':3010' || true
  exit 5
fi

echo "=== COMPLETE ==="
echo "Revision=$REVISION"
echo "URL=http://127.0.0.1:3010"
echo "AdminCredentialsStored=$ADMIN_ENV"
echo "GuestAccess=false"
echo "CloudShare=false"
echo "EmpireWriteAuthority=none"
