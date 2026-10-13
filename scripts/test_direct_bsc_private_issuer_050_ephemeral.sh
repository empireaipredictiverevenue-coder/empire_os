#!/usr/bin/env bash
# Disposable PG18-only issuer 050 proof. Never connects to production port 5432.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "$#" == 0 ]]; then exec pg_virtualenv -v 18 bash "$0" --isolated-inner; fi
[[ "$1" == --isolated-inner && -n "${PGPORT:-}" && "$PGPORT" != 5432 ]] || exit 70
pgdir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 71
# Reuse the existing audited 047/048 fixture prefix, don't invent a new schema.
source <(sed '/^# Deliberately make a login/,$d'  scripts/test_direct_bsc_private_reader_049_ephemeral.sh)
pg -f migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql >/dev/null
echo "EPHEMERAL_049_V2_ISOLATED_BASELINE=PASS"

# Unexpected incoming role is never regranted, including in negative tests.
pg -f migrations/empiredb/050_direct_bsc_buyer_status_private_issuer.sql >/dev/null
echo "EPHEMERAL_050_TWO_DISJOINT_NOLOGIN_ROLES_CREATED=PASS"
verification="$(pg -f scripts/inspect_direct_bsc_private_issuer_050_postcommit.sql)"
total="$(printf '%s\n' "$verification" |
 grep -Ec '^(0[1-9]|10)_[a-z0-9_]+\|PASS$' || true)"
[[ "$total" == 10 ]] ||
 { echo "EPHEMERAL_050_POSTCOMMIT_SECURITY_FAILED";printf '%s\n' "$verification";exit 72; }
echo "EPHEMERAL_050_TEN_POSTCOMMIT_SECURITY_CHECKS=PASS"

pg <<'SQL' >/dev/null
INSERT INTO public.fulfilment_orders VALUES (
 '11111111-1111-4111-8111-111111111111',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'accepted',24900,
 pg_catalog.jsonb_build_object('commercial_terms_sha256',repeat('a',64),
   'payer_wallet','0x1111111111111111111111111111111111111111'));
INSERT INTO public.bsc_payment_requests (
 id,buyer_id,fulfilment_order_id,settlement_mode,status,
 created_at,expires_at,approved_by,approved_at,
 commercial_terms_sha256,payer_address,treasury_address,amount_usdt)
 VALUES (
 '33333333-3333-4333-8333-333333333333',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111','direct','pending',
 now()-interval '5 minutes',now()+interval '1 hour',
 NULL,NULL,repeat('a',64),
 '0x1111111111111111111111111111111111111111',
 '0x1339b487046b0ad924a10c20b1791608ea8595a8',249.00);
SQL
issuer="$(pg -At -c "
BEGIN;
SET LOCAL ROLE empire_direct_checkout_status_issuer;
SELECT public.issue_direct_bsc_buyer_status(
  repeat('a',64),
  '11111111-1111-4111-8111-111111111111'::uuid,
  '33333333-3333-4333-8333-333333333333'::uuid,
  statement_timestamp()-interval '2 seconds',
  statement_timestamp()+interval '30 minutes')->>'decision';
COMMIT;")"
printf '%s\n' "$issuer" | grep -qx created ||
 { echo "EPHEMERAL_PRIVATE_ISSUE_FAILED";exit 74; }
echo "EPHEMERAL_PENDING_REQUEST_ISSUES_FINGERPRINT_ONLY=PASS"
[[ "$(pg -At -c "SELECT count(*) FROM public.direct_bsc_buyer_capabilities
  WHERE token_fingerprint=repeat('a',64)")" == 1 ]] ||
 { echo "EPHEMERAL_ISSUED_FINGERPRINT_NOT_STORED";exit 75; }

# Verify status reader consumes the newly issued capability end-to-end.
buyer="$(pg -At -c "
BEGIN;SET LOCAL ROLE empire_direct_checkout_status_reader;
SELECT public.read_direct_bsc_buyer_status(repeat('a',64))
  ->'payment'->>'status';
ROLLBACK;")"
printf '%s\n' "$buyer" | grep -qx pending ||
 { echo "EPHEMERAL_READER_CANNOT_READ_ISSUED_FINGERPRINT";exit 76; }
echo "EPHEMERAL_ISSUER_TO_READER_END_TO_END=PASS"

# Duplicate order capability, no second active token for order/request.
if pg -c "BEGIN;SET LOCAL ROLE empire_direct_checkout_status_issuer;
SELECT public.issue_direct_bsc_buyer_status(
 repeat('b',64),
 '11111111-1111-4111-8111-111111111111'::uuid,
 '33333333-3333-4333-8333-333333333333'::uuid,
 statement_timestamp()-interval '2 seconds',
 statement_timestamp()+interval '30 minutes');COMMIT;" >/dev/null 2>&1; then
 echo "EPHEMERAL_DUPLICATE_CAPABILITY_ACCEPTED=UNSAFE";exit 77
fi
echo "EPHEMERAL_DUPLICATE_ISSUANCE_DENIED=PASS"

# Different order against original request must deny before insert.
if pg -c "BEGIN;SET LOCAL ROLE empire_direct_checkout_status_issuer;
SELECT public.issue_direct_bsc_buyer_status(
 repeat('b',64),
 '22222222-2222-4222-8222-222222222222'::uuid,
 '33333333-3333-4333-8333-333333333333'::uuid,
 statement_timestamp()-interval '2 seconds',
 statement_timestamp()+interval '30 minutes');COMMIT;" >/dev/null 2>&1; then
 echo "EPHEMERAL_CROSS_ORDER_CAPABILITY_ISSUED=UNSAFE";exit 78
fi
echo "EPHEMERAL_CROSS_ORDER_ISSUANCE_DENIED=PASS"

pg -c "UPDATE public.bsc_payment_requests SET status='approved',
 approved_by='human',approved_at=now()
 WHERE id='33333333-3333-4333-8333-333333333333'" >/dev/null
if pg -c "BEGIN;SET LOCAL ROLE empire_direct_checkout_status_issuer;
SELECT public.issue_direct_bsc_buyer_status(
 repeat('c',64),
 '11111111-1111-4111-8111-111111111111'::uuid,
 '33333333-3333-4333-8333-333333333333'::uuid,
 statement_timestamp()-interval '2 seconds',
 statement_timestamp()+interval '30 minutes');COMMIT;" >/dev/null 2>&1; then
 echo "EPHEMERAL_ALREADY_APPROVED_REISSUANCE_ACCEPTED=UNSAFE";exit 79
fi
echo "EPHEMERAL_APPROVED_REQUEST_NEW_TOKEN_DENIED=PASS"

# Neither caller nor app can insert into table, or execute issuer's function.
priv="$(pg -At -c "
SELECT has_table_privilege('empire_direct_checkout_status_issuer',
 'public.direct_bsc_buyer_capabilities','INSERT')::int||'|'||
 has_function_privilege('empiredb_app',
 'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)',
 'EXECUTE')::int||'|'||
 has_function_privilege('empiredb_migrator_login',
 'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)',
 'EXECUTE')::int")"
[[ "$priv" == '0|0|0' ]] ||
 { echo "EPHEMERAL_ISSUER_AUTHORITY_BROADENED=UNSAFE";exit 80; }
echo "EPHEMERAL_NO_APP_OR_MIGRATOR_ISSUER_PERMISSION=PASS"

if pg -f migrations/empiredb/050_direct_bsc_buyer_status_private_issuer.sql >/dev/null 2>&1; then
 echo "EPHEMERAL_REPEAT_050_INSTALL_ALLOWED=UNSAFE";exit 81
fi
echo "EPHEMERAL_SECOND_INSTALL_REFUSED=PASS"
echo "PRODUCTION_POSTGRES_PORT_ACCESSED=NO"
echo "PRODUCTION_MIGRATION_APPLIED=NO"
