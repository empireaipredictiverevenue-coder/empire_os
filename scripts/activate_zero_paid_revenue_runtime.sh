#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/empire_os
ENV_DB=/etc/empiredb.env
A2A_ENV=/etc/empire_a2a.env
DROPIN_SRC="$ROOT/deploy/systemd/empire-public-gateway.service.d/20-a2a-runtime.conf"
DROPIN_DST=/etc/systemd/system/empire-public-gateway.service.d/20-a2a-runtime.conf

[[ "$(id -u)" -eq 0 ]] || { echo "run as root"; exit 2; }
cd "$ROOT"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
git merge-base --is-ancestor e78801a0 HEAD

set -a
. "$ENV_DB"
set +a
: "${EMPIREDB_MIGRATOR_DSN:?EMPIREDB_MIGRATOR_DSN required}"

db_bits() {
  psql "$EMPIREDB_MIGRATOR_DSN" -X -Atqc "$1"
}

echo "=== BOOTSTRAP RUNTIME CAPABILITY ROLES ==="
bash "$ROOT/scripts/bootstrap_empiredb_runtime_roles.sh"

apply_if_absent() {
  local label="$1" migration="$2" probe_sql="$3"
  local state
  state="$(db_bits "$probe_sql")"
  case "$state" in
    absent)
      echo "=== APPLY $label ==="
      psql "$EMPIREDB_MIGRATOR_DSN" -X -v ON_ERROR_STOP=1 -f "$migration"
      ;;
    ready)
      echo "=== $label ALREADY READY ==="
      ;;
    *)
      echo "$label partial/inconsistent state: $state" >&2
      exit 3
      ;;
  esac
}

apply_if_absent "MIGRATION 025"   "$ROOT/migrations/empiredb/025_owned_campaign_intake.sql"   "SELECT CASE WHEN to_regclass('public.owned_campaign_enquiries') IS NULL
                   AND to_regclass('public.owned_campaign_events') IS NULL
                   AND to_regprocedure('public.record_owned_campaign_event(jsonb)') IS NULL
                   AND to_regprocedure('public.record_owned_campaign_enquiry(jsonb)') IS NULL
              THEN 'absent'
              WHEN to_regclass('public.owned_campaign_enquiries') IS NOT NULL
                   AND to_regclass('public.owned_campaign_events') IS NOT NULL
                   AND to_regprocedure('public.record_owned_campaign_event(jsonb)') IS NOT NULL
                   AND to_regprocedure('public.record_owned_campaign_enquiry(jsonb)') IS NOT NULL
              THEN 'ready'
              ELSE 'partial' END;"

apply_if_absent "MIGRATION 026"   "$ROOT/migrations/empiredb/026_a2a_commercial_intent_authority.sql"   "SELECT CASE WHEN to_regclass('public.a2a_identity_nonces') IS NULL
                   AND to_regclass('public.a2a_commercial_intents') IS NULL
                   AND to_regprocedure('public.consume_a2a_identity_nonce(text,text,text,timestamptz)') IS NULL
                   AND to_regprocedure('public.record_a2a_commercial_intent(text,text,text,timestamptz,text,text,jsonb,jsonb)') IS NULL
              THEN 'absent'
              WHEN to_regclass('public.a2a_identity_nonces') IS NOT NULL
                   AND to_regclass('public.a2a_commercial_intents') IS NOT NULL
                   AND to_regprocedure('public.consume_a2a_identity_nonce(text,text,text,timestamptz)') IS NOT NULL
                   AND to_regprocedure('public.record_a2a_commercial_intent(text,text,text,timestamptz,text,text,jsonb,jsonb)') IS NOT NULL
              THEN 'ready'
              ELSE 'partial' END;"

echo "=== VERIFY DATABASE AUTHORITY ==="
db_bits "SELECT
  has_function_privilege('empire_owned_campaign_ingest','public.record_owned_campaign_enquiry(jsonb)','EXECUTE'),
  has_function_privilege('empire_a2a_identity_nonce_writer','public.consume_a2a_identity_nonce(text,text,text,timestamptz)','EXECUTE'),
  has_function_privilege('empire_a2a_intent_writer','public.record_a2a_commercial_intent(text,text,text,timestamptz,text,text,jsonb,jsonb)','EXECUTE');"   | grep -qx 't|t|t'

echo "=== PROVISION LEAST-PRIVILEGE RUNTIME ==="
EMPIREDB_MIGRATOR_DSN="$EMPIREDB_MIGRATOR_DSN"   "$ROOT/.venv/bin/python" "$ROOT/scripts/provision_zero_paid_revenue_runtime.py"

echo "=== INSTALL SYSTEMD CONFIG ==="
install -d -m 0755 /etc/systemd/system/empire-public-gateway.service.d
install -m 0644 "$DROPIN_SRC" "$DROPIN_DST"
install -m 0644 "$ROOT/deploy/systemd/empire-organic-search-recovery.service"   /etc/systemd/system/empire-organic-search-recovery.service
install -m 0644 "$ROOT/deploy/systemd/empire-organic-search-recovery.timer"   /etc/systemd/system/empire-organic-search-recovery.timer
systemctl daemon-reload

echo "=== RESTART CONFIGURED-UNVERIFIED RUNTIME ==="
systemctl restart empire-public-gateway.service
systemctl restart empire-founder-dashboard-api.service
systemctl restart empire-founder-console.service
systemctl enable --now empire-organic-search-recovery.timer

for unit in empire-public-gateway.service empire-founder-dashboard-api.service empire-founder-console.service; do
  for _ in {1..30}; do
    [[ "$(systemctl is-active "$unit" || true)" == "active" ]] && break
    sleep 1
  done
  [[ "$(systemctl is-active "$unit" || true)" == "active" ]] || {
    systemctl status "$unit" --no-pager -l || true
    exit 4
  }
done

echo "=== VERIFY CONFIGURED A2A WITH SIGNED LOOPBACK ==="
"$ROOT/.venv/bin/python" - <<'PY'
import base64, json, urllib.request, uuid
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization

key = serialization.load_pem_private_key(
    Path("/etc/empire_a2a_agent_ed25519.pem").read_bytes(),
    password=None,
)
agent_id = "empire-activation-verifier"
key_id = "empire-astra-v1"
nonce = str(uuid.uuid4())
issued_at = datetime.now(timezone.utc).isoformat()
scope = "commerce.intent"
payload = f"{agent_id}\n{key_id}\n{nonce}\n{issued_at}\n{scope}".encode()
signature = base64.b64encode(key.sign(payload)).decode()
body = {
    "identity": {
        "agent_id": agent_id,
        "key_id": key_id,
        "nonce": nonce,
        "issued_at": issued_at,
        "signature": signature,
    },
    "capability": "commerce.quote.request",
    "idempotency_key": "activation-" + str(uuid.uuid4()),
    "request": {"purpose": "zero_paid_runtime_activation_verification"},
    "evidence": {
        "source": "founder_approved_activation",
        "authority": "non_binding_intent_only",
    },
}
req = urllib.request.Request(
    "http://127.0.0.1/v1/a2a-commerce/intents",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=15) as response:
    result = json.load(response)
decision = result["decision"]
assert decision["status"] == "pending_approval", decision
assert decision["execution_authority"] == "none", decision
assert decision["payment_authority"] is False, decision
assert decision["allocation_authority"] is False, decision
print("A2A_SIGNED_LOOPBACK=PASS")
PY

echo "=== MARK A2A LIVE-VERIFIED ==="
"$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
p=Path("/etc/empire_a2a.env")
s=p.read_text()
old="EMPIRE_A2A_LIVE_VERIFIED=false"
new="EMPIRE_A2A_LIVE_VERIFIED=true"
if old in s:
    p.write_text(s.replace(old,new,1))
elif new not in s:
    raise SystemExit("A2A live-verified flag missing")
p.chmod(0o600)
PY
systemctl restart empire-public-gateway.service

echo "=== APPLY ZERO-PAID RELEASE MANIFESTS ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" "$ROOT/scripts/release_owned_campaigns.py"   --apply   --evidence-ref "founder:approved:2026-10-01"   --evidence-ref "empiredb:migration025:live"   --evidence-ref "gateway:live-verified"

PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" "$ROOT/scripts/release_aeo_cohort.py"   --apply   --page general_contractor:NYC   --page hvac:DFW   --page roofing:DFW   --evidence-ref "founder:approved:2026-10-01"   --evidence-ref "market-radar:current"   --evidence-ref "aeo-recovery:zero-risk"

echo "=== FINAL LIVE VERIFY ==="
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" "$ROOT/scripts/verify_zero_paid_revenue_activation.py"

echo "=== SERVICE STATUS ==="
systemctl show   empire-public-gateway.service   empire-founder-dashboard-api.service   empire-founder-console.service   empire-organic-search-recovery.timer   -p Id -p ActiveState -p SubState -p Result --no-pager

echo "ZERO_PAID_REVENUE_ACTIVATION=PASS"
