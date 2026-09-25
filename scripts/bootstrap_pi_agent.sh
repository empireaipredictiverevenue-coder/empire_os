#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/bootstrap_pi_agent.sh" >&2
  exit 1
fi

ROOT=/srv/empire_os
PREFIX=/opt/empire/pi-agent
STATE=/var/lib/empire/pi-agent
CONFIG=/etc/empire_os/pi-agent
PACKAGE='@earendil-works/pi-coding-agent@0.87.1'
TARGET_USER="${SUDO_USER:-ubuntu}"
[[ "$TARGET_USER" == "root" ]] && TARGET_USER=ubuntu

echo "=== PI ARCHITECTURE GATE ==="
test -f "$ROOT/docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md"
test -f "$ROOT/docs/ARCHITECTURE_FIRST_ENGINEERING_DOCTRINE.md"

echo "=== NODE GATE ==="
NODE_SOURCE="$(command -v node || true)"
NPM_SOURCE="$(command -v npm || true)"
if [[ -z "$NODE_SOURCE" || -z "$NPM_SOURCE" ]]; then
  NVM_BIN="$(
    find "/home/$TARGET_USER/.nvm/versions/node" -mindepth 2 -maxdepth 2       -type d -name bin -print 2>/dev/null | sort -V | tail -n 1
  )"
  if [[ -n "$NVM_BIN" ]]; then
    [[ -x "$NVM_BIN/node" ]] && NODE_SOURCE="$NVM_BIN/node"
    [[ -x "$NVM_BIN/npm" ]] && NPM_SOURCE="$NVM_BIN/npm"
  fi
fi
if [[ -z "$NODE_SOURCE" || -z "$NPM_SOURCE" ]]; then
  echo "BLOCKED: node/npm required" >&2
  exit 2
fi
NODE_DIR="$(dirname "$NODE_SOURCE")"
NODE_VERSION="$("$NODE_SOURCE" -p 'process.versions.node')"
"$NODE_SOURCE" -e '
const [M,m]=process.versions.node.split(".").map(Number);
if (M < 22 || (M === 22 && m < 19)) process.exit(3);
'
echo "Node=$NODE_VERSION"

echo "=== INSTALL PINNED PI ==="
install -d -m 0755 "$PREFIX"
install -d -m 0755 "$PREFIX/bin"
install -m 0755 "$NODE_SOURCE" "$PREFIX/bin/node"
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER" "$STATE"
install -d -m 0755 "$CONFIG"
env PATH="$NODE_DIR:/usr/local/bin:/usr/bin:/bin"   "$NPM_SOURCE" install   --prefix "$PREFIX"   --omit=dev   --ignore-scripts   --no-audit   --no-fund   "$PACKAGE"

PI_LINK="$PREFIX/node_modules/.bin/pi"
test -x "$PI_LINK"
PI_ENTRY="$(readlink -f "$PI_LINK")"
test -f "$PI_ENTRY"
cat >"$PREFIX/bin/pi" <<EOF
#!/usr/bin/env bash
exec "$PREFIX/bin/node" "$PI_ENTRY" "\$@"
EOF
chmod 0755 "$PREFIX/bin/pi"
PI_BIN="$PREFIX/bin/pi"
"$PI_BIN" --version

echo "=== DISCOVER LOCAL CODING MODEL ==="
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
  echo "BLOCKED: local llama.cpp model not discoverable on 127.0.0.1:11435" >&2
  exit 4
fi
echo "LocalModel=$MODEL_ID"

cat >"$CONFIG/models.json" <<EOF
{
  "providers": {
    "empire-local": {
      "baseUrl": "http://127.0.0.1:11435/v1",
      "api": "openai-completions",
      "apiKey": "local-only",
      "models": [
        {
          "id": "$MODEL_ID",
          "name": "Empire Local Coding Model",
          "reasoning": false,
          "input": ["text"],
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          },
          "contextWindow": 8192,
          "maxTokens": 4096
        }
      ]
    }
  }
}
EOF
chmod 0644 "$CONFIG/models.json"
chown root:root "$CONFIG/models.json"

cat >"$CONFIG/empire-policy.txt" <<'EOF'
EmpireOS governed coding worker.
Architecture first; implement only the supplied bounded task.
Unknown stays unknown.
Do not read or modify production secrets, runtime state, recovery/, toop/, payment,
outbound, canonical database state, service control, or infrastructure.
Do not send external communications, accept terms, move funds, confirm payment,
recognize revenue, deploy production, or expand authority.
Work only in the disposable repository clone supplied as the current directory.
Prefer the smallest production-quality patch and focused tests.
EOF
chmod 0644 "$CONFIG/empire-policy.txt"
chown root:root "$CONFIG/empire-policy.txt"

echo "=== READ-ONLY MODEL CHECK ==="
CHECK_CONFIG="$STATE/check-config"
rm -rf "$CHECK_CONFIG"
install -d -m 0700 -o "$TARGET_USER" -g "$TARGET_USER" "$CHECK_CONFIG"
install -m 0600 -o "$TARGET_USER" -g "$TARGET_USER"   "$CONFIG/models.json" "$CHECK_CONFIG/models.json"
install -m 0600 -o "$TARGET_USER" -g "$TARGET_USER"   "$CONFIG/empire-policy.txt" "$CHECK_CONFIG/empire-policy.txt"
sudo -u "$TARGET_USER" env   PI_CODING_AGENT_DIR="$CHECK_CONFIG"   PI_OFFLINE=1   PI_TELEMETRY=0   "$PI_BIN" --list-models "$MODEL_ID" | head -20
rm -rf "$CHECK_CONFIG"

echo "=== COMPLETE ==="
echo "PiBinary=$PI_BIN"
echo "Config=$CONFIG"
echo "Authority=none"
