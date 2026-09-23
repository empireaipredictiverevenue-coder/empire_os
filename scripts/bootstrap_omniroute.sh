#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/bootstrap_omniroute.sh" >&2
  exit 1
fi

REPO_ROOT=/srv/empire_os
TARGET_USER="${SUDO_USER:-ubuntu}"
if [[ "$TARGET_USER" == "root" ]]; then
  TARGET_USER="ubuntu"
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
if [[ -z "$TARGET_HOME" ]]; then
  echo "Cannot resolve home for $TARGET_USER" >&2
  exit 1
fi

echo "=== QUIESCE HERMES DURING ROUTER CUTOVER ==="
systemctl stop empire-hermes-control.timer empire-hermes-control.service 2>/dev/null || true

echo "=== ENSURE DOCKER ==="
if ! command -v docker >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y docker.io
fi
systemctl enable --now docker
docker version --format '{{.Server.Version}}' >/dev/null

echo "=== PREPARE OMNIROUTE STATE ==="
install -d -m 700 -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/.omniroute"
install -d -m 755 /etc/empire_os

PROVIDER_ENV=/etc/empire_os/omniroute-providers.env
if [[ ! -f "$PROVIDER_ENV" ]]; then
  cat >"$PROVIDER_ENV" <<'EOF'
# Optional provider keys for EmpireOS OmniRoute.
# Values stay on this server and are never committed.
# OPENROUTER_API_KEY=
# GEMINI_API_KEY=
# GOOGLE_API_KEY=
# NVIDIA_API_KEY=
# DEEPSEEK_API_KEY=
# GROQ_API_KEY=
# CEREBRAS_API_KEY=
# SILICONFLOW_API_KEY=
# GLM_API_KEY=
# HF_TOKEN=
# MISTRAL_API_KEY=
# TOGETHER_API_KEY=
# FIREWORKS_API_KEY=
# COHERE_API_KEY=
# XAI_API_KEY=
EOF
  chmod 600 "$PROVIDER_ENV"
  chown root:root "$PROVIDER_ENV"
fi

ENV_FILE="$TARGET_HOME/.omniroute/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n')"
  API_KEY_SECRET="$(openssl rand -hex 32)"
  STORAGE_ENCRYPTION_KEY="$(openssl rand -hex 32)"
  INITIAL_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
  MACHINE_ID_SALT="$(openssl rand -hex 32)"
  WS_BRIDGE_SECRET="$(openssl rand -hex 32)"

  cat >"$ENV_FILE" <<EOF
JWT_SECRET=$JWT_SECRET
API_KEY_SECRET=$API_KEY_SECRET
STORAGE_ENCRYPTION_KEY=$STORAGE_ENCRYPTION_KEY
STORAGE_ENCRYPTION_KEY_VERSION=v1
INITIAL_PASSWORD=$INITIAL_PASSWORD
MACHINE_ID_SALT=$MACHINE_ID_SALT
OMNIROUTE_WS_BRIDGE_SECRET=$WS_BRIDGE_SECRET
DATA_DIR=/app/data
PORT=20128
HOSTNAME=0.0.0.0
OMNIROUTE_SERVER_HOST=0.0.0.0
BASE_URL=http://127.0.0.1:20128
NEXT_PUBLIC_BASE_URL=http://127.0.0.1:20128
NODE_ENV=production
REQUIRE_API_KEY=false
ALLOW_API_KEY_REVEAL=false
APP_LOG_TO_FILE=true
OMNIROUTE_MEMORY_MB=512
EOF
  chown "$TARGET_USER:$TARGET_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
else
  echo "Preserving existing $ENV_FILE"
fi

echo "=== NORMALIZE DOCKER RUNTIME ENV ==="
set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^$key=" "$ENV_FILE"; then
    sed -i "s|^$key=.*|$key=$value|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

set_env DATA_DIR /app/data
set_env PORT 20128
set_env HOSTNAME 0.0.0.0
set_env OMNIROUTE_SERVER_HOST 0.0.0.0
set_env BASE_URL http://127.0.0.1:20128
set_env NEXT_PUBLIC_BASE_URL http://127.0.0.1:20128
set_env NODE_ENV production
set_env REQUIRE_API_KEY false
set_env ALLOW_API_KEY_REVEAL false
set_env APP_LOG_TO_FILE true
set_env OMNIROUTE_MEMORY_MB 512
set_env STORAGE_ENCRYPTION_KEY_VERSION v1

if ! grep -q '^OMNIROUTE_WS_BRIDGE_SECRET=' "$ENV_FILE"; then
  echo "OMNIROUTE_WS_BRIDGE_SECRET=$(openssl rand -hex 32)" >>"$ENV_FILE"
fi
chown "$TARGET_USER:$TARGET_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "=== RECOVER EXISTING HERMES / EMPIRE KEYS INTO PRIVATE ENV ==="
PYTHONPATH="$REPO_ROOT"   "$REPO_ROOT/.venv/bin/python"   "$REPO_ROOT/scripts/export_omniroute_provider_env.py"   --home "$TARGET_HOME"   --output "$PROVIDER_ENV"

echo "=== INSTALL SYSTEMD UNITS ==="
install -m 0644 "$REPO_ROOT/deploy/systemd/empire-omniroute.service"   /etc/systemd/system/empire-omniroute.service
install -m 0644 "$REPO_ROOT/deploy/systemd/empire-hermes-control.service"   /etc/systemd/system/empire-hermes-control.service
install -m 0644 "$REPO_ROOT/deploy/systemd/empire-hermes-control.timer"   /etc/systemd/system/empire-hermes-control.timer
systemctl daemon-reload

echo "=== START OMNIROUTE ==="
systemctl enable --now empire-omniroute.service

echo "=== WAIT FOR LOOPBACK API ==="
for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 http://127.0.0.1:20128/v1/models >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS --max-time 5 http://127.0.0.1:20128/v1/models >/dev/null

echo "=== VERIFY LISTEN IS LOOPBACK-ONLY ==="
if ss -ltnH '( sport = :20128 )' | awk '{print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]):20128$' | grep -q .; then
  echo "ERROR: OmniRoute port 20128 is not loopback-only" >&2
  ss -ltnp | grep ':20128' || true
  exit 1
fi

echo "=== HERMES -> OMNIROUTE ENV ==="
cat >/etc/empire_os/omniroute-hermes.env <<'EOF'
EMPIRE_HERMES_PROVIDER=custom
EMPIRE_HERMES_MODEL=auto
OPENAI_BASE_URL=http://127.0.0.1:20128/v1
OPENAI_API_KEY=local-omniroute
EOF
chmod 640 /etc/empire_os/omniroute-hermes.env
chown root:ubuntu /etc/empire_os/omniroute-hermes.env

echo "=== ROUTER MODEL CATALOG ==="
curl -fsS --max-time 10 http://127.0.0.1:20128/v1/models   | python3 -c 'import json,sys; x=json.load(sys.stdin); print("models:", len(x.get("data", [])))'

echo "=== ROUTER AUTO TEST ==="
AUTO_TMP="$(mktemp)"
HTTP_CODE="$(curl -sS --max-time 90   -o "$AUTO_TMP"   -w '%{http_code}'   -H 'Content-Type: application/json'   http://127.0.0.1:20128/v1/chat/completions   -d '{"model":"auto","messages":[{"role":"user","content":"Reply exactly OMNIROUTE_OK."}],"max_tokens":32}' || true)"
python3 - "$AUTO_TMP" "$HTTP_CODE" <<'PY'
import json, sys
path, code = sys.argv[1], sys.argv[2]
try:
    payload = json.load(open(path))
except Exception:
    payload = {}
content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content")
print("HTTP:", code)
print("response:", content or payload.get("error") or "<no response>")
if code != "200" or not content:
    print("NOTE: gateway is healthy but no usable provider is active yet.")
PY
rm -f "$AUTO_TMP"

echo "=== RESTORE HERMES WORKER ==="
systemctl reset-failed empire-hermes-control.service || true
systemctl enable --now empire-hermes-control.timer
systemctl start --no-block empire-hermes-control.service

echo "=== COMPLETE ==="
echo "OmniRoute:"
systemctl show empire-omniroute.service -p ActiveState -p SubState -p Result
echo "Hermes:"
systemctl show empire-hermes-control.service -p ActiveState -p SubState -p Result
echo "Timer:"
systemctl is-enabled empire-hermes-control.timer
systemctl is-active empire-hermes-control.timer
echo "Loopback:"
ss -ltnp | grep ':20128' || true
