#!/bin/bash
# push_hub_env.sh — push missing keys from host /root/empire_os/.env into
# empire-hub container's .env without ever printing secrets to chat.
#
# This script:
#   1) Copies non-secret keys (USDC_MINT, SOLANA_NETWORK, HUB_URL, SMTP
#      host/port/user, EMPIRE_FROM, SENDGRID_FROM, EMAIL_BACKEND, SMTP_TLS)
#      directly from host .env. These are public addresses / transport
#      config, not credentials.
#   2) For SECRETS (SOLANA_VAULT_WALLET, SOLANA_RPC_URL, SOLANA_PAYER_SECRET,
#      SMTP_PASS, SENDGRID_API_KEY, RESEND_API_KEY), reads from files under
#      /root/.hermes/vault/ — YOU put them there, this script never echoes.
#   3) Assembles a fresh container .env and pushes via `incus file push`,
#      then restarts the hub and runs deploy_check.
#
# Vault side-channel (memory pattern):
#   printf 'VAULT_WALLET_PUBKEY_HERE' > /root/.hermes/vault/solana_vault_wallet
#   printf 'SOLANA_RPC_URL_HERE'     > /root/.hermes/vault/solana_rpc_url
#   printf 'SMTP_PASS_HERE'          > /root/.hermes/vault/smtp_pass
#   printf 'RESEND_API_KEY_HERE'     > /root/.hermes/vault/resend_api_key
#   printf 'SOLANA_PAYER_SECRET_HERE' > /root/.hermes/vault/solana_payer_secret
#
# Required vault files (any missing -> script aborts with file name):
#   - solana_vault_wallet
#   - solana_rpc_url
#   - solana_payer_secret
#   - smtp_pass   (or set USE_RESEND=1 and provide resend_api_key instead)
#
# Usage: sudo bash /root/empire_os/scripts/push_hub_env.sh

set -euo pipefail

HOST_ENV="/root/empire_os/.env"
VAULT_DIR="/root/.hermes/vault"
STAGE="$(mktemp -t hubenv.XXXXXX)"
trap 'shred -u "$STAGE" 2>/dev/null || rm -f "$STAGE"' EXIT

mkdir -p "$VAULT_DIR"
chmod 700 "$VAULT_DIR"

# 1. SECRETS — read from vault files; abort loudly if missing
read_secret() {
  local name="$1"
  local path="$VAULT_DIR/$name"
  if [[ ! -s "$path" ]]; then
    echo "ABORT: missing /root/.hermes/vault/$name" >&2
    echo "  create with: printf '%s' 'VALUE' > $path && chmod 600 $path" >&2
    exit 2
  fi
  chmod 600 "$path"
  cat "$path"
}

SOLANA_VAULT_WALLET="$(read_secret solana_vault_wallet)"
SOLANA_RPC_URL="$(read_secret solana_rpc_url)"
SOLANA_PAYER_SECRET="$(read_secret solana_payer_secret)"

# Email backend: SMTP (default) or Resend. Set USE_RESEND=1 in env to switch.
USE_RESEND="${USE_RESEND:-0}"
if [[ "$USE_RESEND" == "1" ]]; then
  RESEND_API_KEY="$(read_secret resend_api_key)"
  EMAIL_BACKEND="resend"
  SMTP_HOST=""
  SMTP_PORT=""
  SMTP_USER=""
  SMTP_PASS=""
else
  SMTP_PASS="$(read_secret smtp_pass)"
  EMAIL_BACKEND="smtp"
  SMTP_HOST="smtp.sendgrid.net"
  SMTP_PORT="587"
  SMTP_USER="apikey"
fi

# 2. NON-SECRETS — read from host .env (already public values there)
read_kv() {
  local key="$1"
  local def="${2:-}"
  local val
  val="$(grep -E "^${key}=" "$HOST_ENV" 2>/dev/null | head -1 | cut -d= -f2-)"
  echo "${val:-$def}"
}

USDC_MINT="$(read_kv USDC_MINT 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')"
SOLANA_NETWORK="$(read_kv SOLANA_NETWORK 'mainnet-beta')"
HUB_URL="$(read_kv HUB_URL 'http://127.0.0.1:8081')"
EMPIRE_FROM="$(read_kv EMPIRE_FROM 'Empire OS <founder@empire-ai.co.uk>')"
SENDGRID_FROM="$EMPIRE_FROM"
SMTP_TLS="1"

# 3. Assemble new container .env (no trailing-newline-pitfall — write one
#    final newline explicitly at the end). Each line written via printf so
#    no shell expansion happens on values.
{
  printf 'SOLANA_VAULT_WALLET=%s\n'        "$SOLANA_VAULT_WALLET"
  printf 'SOLANA_RPC_URL=%s\n'            "$SOLANA_RPC_URL"
  printf 'USDC_MINT=%s\n'                 "$USDC_MINT"
  printf 'SOLANA_NETWORK=%s\n'            "$SOLANA_NETWORK"
  printf 'SOLANA_PAYER_SECRET=%s\n'       "$SOLANA_PAYER_SECRET"
  printf 'EMAIL_BACKEND=%s\n'             "$EMAIL_BACKEND"
  printf 'HUB_URL=%s\n'                   "$HUB_URL"
  printf 'EMPIRE_FROM=%s\n'               "$EMPIRE_FROM"
  printf 'SENDGRID_FROM=%s\n'             "$SENDGRID_FROM"
  if [[ "$USE_RESEND" == "1" ]]; then
    printf 'RESEND_API_KEY=%s\n'          "$RESEND_API_KEY"
  else
    printf 'SMTP_HOST=%s\n'               "$SMTP_HOST"
    printf 'SMTP_PORT=%s\n'               "$SMTP_PORT"
    printf 'SMTP_USER=%s\n'               "$SMTP_USER"
    printf 'SMTP_PASS=%s\n'               "$SMTP_PASS"
    printf 'SMTP_TLS=%s\n'                "$SMTP_TLS"
  fi
  printf '\n'  # final newline — systemd env-files skip last line if missing
} > "$STAGE"

chmod 600 "$STAGE"

# 4. Push to container
incus file push "$STAGE" empire-hub/root/empire_os/.env
incus exec empire-hub -- chmod 600 /root/empire_os/.env

echo "==> pushed $(wc -l <"$STAGE") lines to empire-hub:/root/empire_os/.env"
echo "==> restarting hub..."
incus exec empire-hub -- systemctl restart empire-hub-8081
sleep 5

echo "==> hub status:"
incus exec empire-hub -- systemctl is-active empire-hub-8081
echo "==> /health:"
incus exec empire-hub -- curl -s http://127.0.0.1:8081/health
echo
echo "==> verify pay_url now mints (apply a test buyer):"
PAY_URL=$(incus exec empire-hub -- curl -s -X POST http://127.0.0.1:8081/v1/buyers/apply \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"VCHK\",\"niche\":\"roof_repair\",\"email\":\"vchk-$(date +%s)@v.co\",\"tier\":\"silver\",\"min_deposit\":0,\"source\":\"vault_push\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('payment',{}).get('pay_to_wallet','MISSING')[:20]+' ... '+d.get('payment',{}).get('pay_url','')[:60])")
echo "  $PAY_URL"

shred -u "$STAGE" 2>/dev/null || rm -f "$STAGE"
trap - EXIT
echo "==> DONE"