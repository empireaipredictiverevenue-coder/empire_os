#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/bootstrap_omniroute.sh" >&2
  exit 1
fi

echo "=== QUIESCE HERMES WORKER DURING ROUTER CUTOVER ==="
systemctl stop empire-hermes-control.timer empire-hermes-control.service 2>/dev/null || true

TARGET_USER="${SUDO_USER:-ubuntu}"
if [[ "$TARGET_USER" == "root" ]]; then
  TARGET_USER="ubuntu"
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
if [[ -z "$TARGET_HOME" ]]; then
  echo "Cannot resolve home for $TARGET_USER" >&2
  exit 1
fi

echo "=== PREPARE OMNIROUTE STATE ==="
install -d -m 700 -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/.omniroute"
install -d -m 755 /etc/empire_os

PROVIDER_ENV=/etc/empire_os/omniroute-providers.env
if [[ ! -f "$PROVIDER_ENV" ]]; then
  cat >"$PROVIDER_ENV" <<'EOF'
# Optional EmpireOS provider keys. Values stay on the server and are never committed.
# Uncomment only providers/accounts you are authorised to use.
# GEMINI_API_KEY=
# NVIDIA_API_KEY=
# GROQ_API_KEY=
# CEREBRAS_API_KEY=
# OPENROUTER_API_KEY=
# DEEPSEEK_API_KEY=
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
  CLI_SALT="$(openssl rand -hex 32)"

  cat >"$ENV_FILE" <<EOF
JWT_SECRET=$JWT_SECRET
API_KEY_SECRET=$API_KEY_SECRET
STORAGE_ENCRYPTION_KEY=$STORAGE_ENCRYPTION_KEY
INITIAL_PASSWORD=$INITIAL_PASSWORD
MACHINE_ID_SALT=$MACHINE_ID_SALT
OMNIROUTE_CLI_SALT=$CLI_SALT
DATA_DIR=$TARGET_HOME/.omniroute
PORT=20128
OMNIROUTE_SERVER_HOST=127.0.0.1
HOSTNAME=127.0.0.1
NEXT_PUBLIC_BASE_URL=http://127.0.0.1:20128
BASE_URL=http://127.0.0.1:20128
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

echo "=== INSTALL / UPDATE OMNIROUTE ==="
runuser -u "$TARGET_USER" -- bash -lc '
  set -e
  export NVM_DIR="$HOME/.nvm"
  if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi
  node --version
  npm --version
  npm install -g omniroute@3.8.51
  command -v omniroute
  omniroute --version || true
'

echo "=== HERMES -> OMNIROUTE ENV ==="
cat >/etc/empire_os/omniroute-hermes.env <<'EOF'
EMPIRE_HERMES_PROVIDER=custom
EMPIRE_HERMES_MODEL=auto
OPENAI_BASE_URL=http://127.0.0.1:20128/v1
OPENAI_API_KEY=local-omniroute
EOF
chmod 640 /etc/empire_os/omniroute-hermes.env
chown root:ubuntu /etc/empire_os/omniroute-hermes.env

echo "=== INSTALL SERVICES ==="
install -m 0644 /srv/empire_os/deploy/systemd/empire-omniroute.service /etc/systemd/system/empire-omniroute.service
install -m 0644 /srv/empire_os/deploy/systemd/empire-hermes-control.service /etc/systemd/system/empire-hermes-control.service
install -m 0644 /srv/empire_os/deploy/systemd/empire-hermes-control.timer /etc/systemd/system/empire-hermes-control.timer
systemctl daemon-reload
systemctl enable --now empire-omniroute.service

echo "=== WAIT FOR LOCAL GATEWAY ==="
for _ in $(seq 1 40); do
  if curl -fsS --max-time 2 http://127.0.0.1:20128/v1/models >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS --max-time 5 http://127.0.0.1:20128/v1/models >/dev/null

echo "=== IMPORT DISCOVERED PROVIDER KEYS ==="
PYTHONPATH=/srv/empire_os   /srv/empire_os/.venv/bin/python   /srv/empire_os/scripts/import_omniroute_provider_keys.py   --home "$TARGET_HOME"   --user "$TARGET_USER" || true

echo "=== ENABLE DOCUMENTED NO-AUTH FALLBACK ==="
runuser -u "$TARGET_USER" -- bash -lc '
  set +e
  export NVM_DIR="$HOME/.nvm"
  if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi
  export EMPIRE_FREE_PROVIDER_KEY=free
  omniroute providers add pollinations --credential-env EMPIRE_FREE_PROVIDER_KEY >/tmp/omniroute-pollinations.out 2>&1
  rc=$?
  if [ $rc -ne 0 ]; then
    grep -Eiv "key|token|secret|credential" /tmp/omniroute-pollinations.out | tail -n 8 || true
  fi
  rm -f /tmp/omniroute-pollinations.out
  exit 0
'

echo "=== PROVIDER HEALTH ==="
runuser -u "$TARGET_USER" -- bash -lc '
  export NVM_DIR="$HOME/.nvm"
  if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi
  omniroute providers list --json 2>/dev/null |     python3 -c "import json,sys; x=json.load(sys.stdin); print(json.dumps(x, indent=2)[:12000])" || true
'

echo "=== OMNIROUTE AUTO TEST ==="
curl -fsS --max-time 90   -H 'Content-Type: application/json'   http://127.0.0.1:20128/v1/chat/completions   -d '{"model":"auto","messages":[{"role":"user","content":"Reply exactly OMNIROUTE_OK."}],"max_tokens":32}'   | python3 -c 'import json,sys; x=json.load(sys.stdin); print((x.get("choices") or [{}])[0].get("message",{}).get("content",""))'

echo "=== RESTART HERMES WORKER WITH OMNIROUTE ==="
systemctl reset-failed empire-hermes-control.service || true
systemctl enable --now empire-hermes-control.timer
systemctl start --no-block empire-hermes-control.service

echo "=== COMPLETE ==="
systemctl is-active empire-omniroute.service
systemctl is-enabled empire-hermes-control.timer
systemctl is-active empire-hermes-control.timer
systemctl show empire-hermes-control.service -p ActiveState -p SubState -p Result
echo "OmniRoute is bound to loopback only: http://127.0.0.1:20128"
