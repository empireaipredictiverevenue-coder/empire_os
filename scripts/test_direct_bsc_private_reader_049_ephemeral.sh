#!/usr/bin/env bash
# EmpireDB 049 PRIVATE READER research harness, isolated PG18 only.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "$#" -eq 0 ]]; then
 exec pg_virtualenv -v 18 bash "$0" --isolated-inner
fi
[[ "$1" == "--isolated-inner" && -n "${PGPORT:-}" && "$PGPORT" != 5432 ]] || exit 70
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 71
pg() { psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture "$@"; }
psql -X -w -v ON_ERROR_STOP=1 -d postgres <<'SQL' >/dev/null
CREATE ROLE empiredb_migrator NOLOGIN INHERIT;
CREATE ROLE empiredb_tenant_reader NOLOGIN NOINHERIT;
GRANT empiredb_tenant_reader TO empiredb_migrator WITH INHERIT TRUE, SET TRUE, ADMIN FALSE;
CREATE ROLE empiredb_app NOLOGIN NOINHERIT;
CREATE ROLE empiredb_readonly NOLOGIN NOINHERIT;
CREATE ROLE empire_payment_approver NOLOGIN NOINHERIT;
CREATE ROLE empire_bsc_verifier NOLOGIN NOINHERIT;
CREATE ROLE fake_existing_reader NOLOGIN NOINHERIT;
CREATE DATABASE direct_bsc_capability_fixture;
SQL
pg <<'SQL' >/dev/null
CREATE TABLE public.fulfilment_orders (
 id uuid PRIMARY KEY,
 buyer_id uuid NOT NULL,
 state text NOT NULL,
 price_cents bigint NOT NULL,
 commercial_payload jsonb NOT NULL
);
CREATE TABLE public.bsc_payment_requests (
 id uuid PRIMARY KEY,
 buyer_id uuid NOT NULL,
 fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id),
 settlement_mode text NOT NULL,
 status text NOT NULL,
 created_at timestamptz NOT NULL,
 expires_at timestamptz NOT NULL,
 approved_by text,
 approved_at timestamptz,
 commercial_terms_sha256 text NOT NULL,
 payer_address text NOT NULL,
 treasury_address text NOT NULL,
 amount_usdt numeric NOT NULL
);
CREATE TABLE public.bsc_payment_evidence (
 id uuid PRIMARY KEY,
 request_id uuid NOT NULL,
 fulfilment_order_id uuid NOT NULL,
 chain_id integer NOT NULL,
 token_contract text NOT NULL,
 treasury_address text NOT NULL,
 commercial_terms_sha256 text NOT NULL,
 confirmations integer NOT NULL
);
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
GRANT SELECT,REFERENCES ON public.fulfilment_orders,public.bsc_payment_requests
 TO empiredb_migrator;
GRANT SELECT ON public.bsc_payment_evidence TO empiredb_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO empiredb_app;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT ON TABLES TO empiredb_readonly;
SQL
pg -f migrations/empiredb/047_direct_bsc_buyer_status_capability.sql >/dev/null
pg -f migrations/empiredb/048_direct_bsc_buyer_capability_acl_seal.sql >/dev/null
echo "EPHEMERAL_047_048_SEALED_BASELINE=PASS"

# Deliberately make a login a member of migrator: no 049 RLS policy may be
# created even though it can pass the earlier migration 047 gate.
psql -X -w -v ON_ERROR_STOP=1 -d postgres -c \
 "GRANT empiredb_migrator TO fake_existing_reader WITH INHERIT TRUE, SET TRUE" >/dev/null
log="$(mktemp)"
if pg -f migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql >"$log" 2>&1; then
 rm -f "$log";echo "EPHEMERAL_REVERSE_MIGRATOR_MEMBER_ACCEPTED=UNSAFE";exit 72
fi
grep -q 'DIRECT049_ROLE_MEMBERSHIP_OR_PRIVILEGE_UNSAFE' "$log" ||
 { tail -15 "$log";rm -f "$log";echo "EPHEMERAL_ROLE_DENIAL_NOT_VERIFIED";exit 73; }
rm -f "$log"
[[ "$(psql -X -w -At -d postgres -c \
 "SELECT to_regrole('empire_direct_checkout_status_reader') IS NULL")" == t ]] ||
 { echo "EPHEMERAL_FAILED_MIGRATION_LEFT_PRIVILEGE_ROLE=UNSAFE";exit 74; }
psql -X -w -v ON_ERROR_STOP=1 -d postgres -c \
 "REVOKE empiredb_migrator FROM fake_existing_reader" >/dev/null
echo "EPHEMERAL_REVERSE_MIGRATOR_MEMBERSHIP_FAIL_CLOSED=PASS"

pg -f migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql >/dev/null
echo "EPHEMERAL_INTERNAL_049_ROLE_AND_FUNCTION_CREATED=PASS"

# The dedicated NOLOGIN role can execute the restricted function, and has
# no direct SELECT privilege on the buyer order, payment or capability tables.
pg <<'SQL' >/dev/null
INSERT INTO public.fulfilment_orders VALUES
('11111111-1111-4111-8111-111111111111',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'accepted',24900,
 pg_catalog.jsonb_build_object('commercial_terms_sha256',repeat('a',64),
   'payer_wallet','0x1111111111111111111111111111111111111111'));
INSERT INTO public.bsc_payment_requests(
 id,buyer_id,fulfilment_order_id,settlement_mode,status,created_at,expires_at,
 approved_by,approved_at,commercial_terms_sha256,payer_address,
 treasury_address,amount_usdt) VALUES (
 '33333333-3333-4333-8333-333333333333',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111','direct','approved',
 now()-interval '25 minutes',now()+interval '3 hours',
 'human-reviewer',now()-interval '3 minutes',
 repeat('a',64),'0x1111111111111111111111111111111111111111',
 '0x1339b487046b0ad924a10c20b1791608ea8595a8',249.00);
INSERT INTO public.direct_bsc_buyer_capabilities(
 token_fingerprint,fulfilment_order_id,request_id,issued_at,expires_at
) VALUES (
 repeat('f',64),'11111111-1111-4111-8111-111111111111',
 '33333333-3333-4333-8333-333333333333',
 now()-interval '15 minutes',now()+interval '2 hours');
SQL
role_result="$(pg -At -c "
BEGIN;
SET LOCAL ROLE empire_direct_checkout_status_reader;
SELECT COALESCE(public.read_direct_bsc_buyer_status(repeat('f',64))->'payment'->>'status','NOT_FOUND');
SELECT (public.read_direct_bsc_buyer_status(repeat('0',64)) IS NULL)::int;
ROLLBACK;
")"
printf '%s\n' "$role_result" | grep -qx approved ||
 { echo "EPHEMERAL_AUTHORIZED_FINGERPRINT_NOT_READABLE";exit 75; }
printf '%s\n' "$role_result" | grep -qx 1 ||
 { echo "EPHEMERAL_GUESSED_FINGERPRINT_NOT_REJECTED";exit 76; }
echo "EPHEMERAL_EXACT_FINGERPRINT_READ_AND_UNKNOWN_DENIAL=PASS"

direct_privs="$(pg -At -c "SELECT has_table_privilege('empire_direct_checkout_status_reader','public.direct_bsc_buyer_capabilities','SELECT')::int||'|'||has_table_privilege('empire_direct_checkout_status_reader','public.fulfilment_orders','SELECT')::int||'|'||has_table_privilege('empire_direct_checkout_status_reader','public.bsc_payment_requests','SELECT')::int||'|'||has_function_privilege('empiredb_app','public.read_direct_bsc_buyer_status(text)','EXECUTE')::int")"
[[ "$direct_privs" == '0|0|0|0' ]] ||
 { echo "EPHEMERAL_READER_BROAD_TABLE_OR_APP_FUNCTION_GRANT=UNSAFE";exit 77; }
echo "EPHEMERAL_ROLE_HAS_NO_DIRECT_TABLE_READ_AND_APP_EXECUTE=PASS"

# Independent canonical price check is enforced by the DB query as well as
# the private Python projector: manipulating a payable amount yields no row.
pg -c "UPDATE public.bsc_payment_requests
 SET amount_usdt=250.00
 WHERE id='33333333-3333-4333-8333-333333333333'" >/dev/null
bad_amount="$(pg -At -c "
BEGIN;SET LOCAL ROLE empire_direct_checkout_status_reader;
SELECT (public.read_direct_bsc_buyer_status(repeat('f',64)) IS NULL)::int;
ROLLBACK;")"
printf '%s\n' "$bad_amount" | grep -qx 1 ||
 { echo "EPHEMERAL_TAMPERED_PAYMENT_AMOUNT_DISCLOSED=UNSAFE";exit 80; }
pg -c "UPDATE public.bsc_payment_requests
 SET amount_usdt=249.00
 WHERE id='33333333-3333-4333-8333-333333333333'" >/dev/null
echo "EPHEMERAL_ORDER_PRICE_CENTS_MATCH_REQUIRED=PASS"

pg -c "UPDATE public.bsc_payment_requests
 SET buyer_id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
 WHERE id='33333333-3333-4333-8333-333333333333'" >/dev/null
bad_buyer="$(pg -At -c "
BEGIN;SET LOCAL ROLE empire_direct_checkout_status_reader;
SELECT (public.read_direct_bsc_buyer_status(repeat('f',64)) IS NULL)::int;
ROLLBACK;")"
printf '%s\n' "$bad_buyer" | grep -qx 1 ||
 { echo "EPHEMERAL_CROSS_BUYER_DB_READ_UNSAFE";exit 81; }
pg -c "UPDATE public.bsc_payment_requests
 SET buyer_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
 WHERE id='33333333-3333-4333-8333-333333333333'" >/dev/null
echo "EPHEMERAL_CROSS_BUYER_DB_READ_FAIL_CLOSED=PASS"

# No bearer passed => no function output; revocation must immediately block.
pg -c "UPDATE public.direct_bsc_buyer_capabilities SET revoked_at=now()" >/dev/null
revoked="$(pg -At -c "BEGIN;SET LOCAL ROLE empire_direct_checkout_status_reader;SELECT (public.read_direct_bsc_buyer_status(repeat('f',64)) IS NULL)::int;ROLLBACK;")"
printf '%s\n' "$revoked" | grep -qx 1 ||
 { echo "EPHEMERAL_REVOKED_BUYER_CAPABILITY_READABLE=UNSAFE";exit 78; }
echo "EPHEMERAL_REVOKED_TOKEN_DENIAL=PASS"

if pg -f migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql >/dev/null 2>&1; then
 echo "EPHEMERAL_REPEATED_049_INSTALLATION_ALLOWED=UNSAFE";exit 79
fi
echo "EPHEMERAL_049_SECOND_APPLY_FAIL_CLOSED=PASS"
echo "PRODUCTION_POSTGRES_PORT_ACCESSED=NO"
echo "PRODUCTION_MIGRATION_APPLIED=NO"
