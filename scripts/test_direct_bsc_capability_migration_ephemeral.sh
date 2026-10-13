#!/usr/bin/env bash
# Disposable PostgreSQL 18 ONLY. Never touches production port 5432.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "$#" -eq 0 ]]; then
  exec pg_virtualenv -v 18 bash "$0" --ephemeral-inner
fi
[[ "$1" == "--ephemeral-inner" && -n "${PGPORT:-}" && "$PGPORT" != "5432" ]] || exit 70
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 71

psql -X -w -v ON_ERROR_STOP=1 -d postgres <<'SQL' >/dev/null
CREATE ROLE empiredb_migrator NOLOGIN INHERIT;
CREATE ROLE empiredb_tenant_reader NOLOGIN NOINHERIT;
GRANT empiredb_tenant_reader TO empiredb_migrator WITH INHERIT TRUE, SET TRUE, ADMIN FALSE;
CREATE ROLE empiredb_app NOLOGIN NOINHERIT;
CREATE DATABASE direct_bsc_capability_fixture;
SQL
psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture <<'SQL' >/dev/null
CREATE TABLE public.fulfilment_orders (
  id uuid PRIMARY KEY, buyer_id uuid NOT NULL, state text NOT NULL
);
CREATE TABLE public.bsc_payment_requests (
  id uuid PRIMARY KEY, buyer_id uuid NOT NULL,
  fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id),
  settlement_mode text NOT NULL, status text NOT NULL,
  created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL
);
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
GRANT SELECT,REFERENCES ON public.fulfilment_orders,public.bsc_payment_requests
  TO empiredb_migrator;
SQL

# Negative case: an additional inherited finance group must abort the exact
# migration BEFORE it creates any register/function. Only in isolated PG18.
psql -X -w -v ON_ERROR_STOP=1 -d postgres <<'SQL' >/dev/null
CREATE ROLE empire_payment_approver NOLOGIN NOINHERIT;
CREATE ROLE empire_bsc_verifier NOLOGIN NOINHERIT;
GRANT empire_payment_approver TO empiredb_migrator
  WITH INHERIT TRUE, SET TRUE, ADMIN FALSE;
SQL
deny_log="$(mktemp)"
if psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -f migrations/empiredb/047_direct_bsc_buyer_status_capability.sql >"$deny_log" 2>&1; then
  rm -f "$deny_log"
  echo "EPHEMERAL_UNEXPECTED_FINANCIAL_MEMBERSHIP_ALLOWED=UNSAFE";exit 79
fi
if ! grep -q 'DIRECT047_UNREVIEWED_MIGRATOR_INHERITED_AUTHORITY' "$deny_log"; then
  rm -f "$deny_log"
  echo "EPHEMERAL_UNEXPECTED_MEMBERSHIP_NOT_PROVEN=HELD";exit 80
fi
rm -f "$deny_log"
absent="$(psql -X -w -At -d direct_bsc_capability_fixture -c \
 "SELECT to_regclass('public.direct_bsc_buyer_capabilities') IS NULL")"
[[ "$absent" == "t" ]] || { echo "EPHEMERAL_FAILED_MIGRATION_WROTE_TABLE=UNSAFE";exit 81; }
psql -X -w -v ON_ERROR_STOP=1 -d postgres -c \
 "REVOKE empire_payment_approver FROM empiredb_migrator" >/dev/null
echo "EPHEMERAL_UNEXPECTED_FINANCIAL_MEMBERSHIP_FAIL_CLOSED=PASS"

psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -f migrations/empiredb/047_direct_bsc_buyer_status_capability.sql >/dev/null
flags="$(psql -X -w -At -d direct_bsc_capability_fixture -c "
SELECT relrowsecurity::int::text||'|'||relforcerowsecurity::int::text
FROM pg_catalog.pg_class WHERE oid='public.direct_bsc_buyer_capabilities'::regclass")"
[[ "$flags" == "1|1" ]] || { echo 'EPHEMERAL_RLS_SEAL=FAIL'; exit 72; }
acl="$(psql -X -w -At -d direct_bsc_capability_fixture -c "
SELECT has_table_privilege('empiredb_app','public.direct_bsc_buyer_capabilities','SELECT')::int")"
[[ "$acl" == "0" ]] || { echo 'EPHEMERAL_DIRECT_APP_TABLE_ACCESS=UNSAFE';exit 73; }
echo "EPHEMERAL_CAPABILITY_MIGRATION_AND_DENY_DEFAULT=PASS"

# Run the exact catalog-only postcommit forensic inspector on the PG18
# disposable migration, proving all nine checks PASS on a known-safe state.
catalog_report="$(psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -f scripts/inspect_direct_bsc_capability_047_postcommit.sql)"
valid_count="$(printf '%s\n' "$catalog_report" |
  grep -Ec '^[[:space:]]*0[1-9]_[[:alnum:]_]+[[:space:]]*\\|[[:space:]]*PASS[[:space:]]*$' || true)"
[[ "$valid_count" == 9 ]] ||
  { echo 'EPHEMERAL_NINE_SECURITY_CHECKS_NOT_ALL_PASS'; exit 82; }
echo "EPHEMERAL_NINE_NAMED_POSTCOMMIT_CHECKS=PASS"

psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture <<'SQL' >/dev/null
INSERT INTO public.fulfilment_orders VALUES
('11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','accepted'),
('22222222-2222-4222-8222-222222222222','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','accepted');
INSERT INTO public.bsc_payment_requests VALUES
('33333333-3333-4333-8333-333333333333',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111','direct','pending',
 now() - interval '1 minute',now()+interval '3 hours');
INSERT INTO public.direct_bsc_buyer_capabilities(
 token_fingerprint,fulfilment_order_id,request_id,issued_at,expires_at
) VALUES (
 repeat('a',64),'11111111-1111-4111-8111-111111111111',
 '33333333-3333-4333-8333-333333333333',now(),now()+interval '1 hour'
);
SQL
echo "EPHEMERAL_VERIFIED_ORDER_REQUEST_BINDING=PASS"

if psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -c "INSERT INTO public.direct_bsc_buyer_capabilities(token_fingerprint,fulfilment_order_id,request_id,issued_at,expires_at) VALUES (repeat('b',64),'22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333',now(),now()+interval '1 hour')" >/dev/null 2>&1; then
 echo "EPHEMERAL_CROSS_ORDER_BINDING_UNSAFE";exit 74
fi
if psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -c "INSERT INTO public.direct_bsc_buyer_capabilities(token_fingerprint,fulfilment_order_id,request_id,issued_at,expires_at) VALUES (repeat('c',64),'11111111-1111-4111-8111-111111111111','33333333-3333-4333-8333-333333333333',now(),now()+interval '1 hour')" >/dev/null 2>&1; then
 echo "EPHEMERAL_ACTIVE_TOKEN_REPLAY_UNSAFE";exit 75
fi
if psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -c "UPDATE public.direct_bsc_buyer_capabilities SET token_fingerprint=repeat('d',64)" >/dev/null 2>&1; then
 echo "EPHEMERAL_TOKEN_REWRITE_UNSAFE";exit 76
fi
psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -c "UPDATE public.direct_bsc_buyer_capabilities SET revoked_at=now()" >/dev/null
if psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -c "UPDATE public.direct_bsc_buyer_capabilities SET revoked_at=now()" >/dev/null 2>&1; then
 echo "EPHEMERAL_DUPLICATE_REVOCATION_UNSAFE";exit 77
fi
echo "EPHEMERAL_CROSS_ORDER_REPLAY_IMMUTABLE_REVOCATION=PASS"

# Intentionally grant SELECT to fake app in isolated fixture to PROVE FORCE RLS
# holds even against privilege accidents; no similar production GRANT.
psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -c "GRANT USAGE ON SCHEMA public TO empiredb_app; GRANT SELECT ON public.direct_bsc_buyer_capabilities TO empiredb_app" >/dev/null
unsafe_report="$(psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -f scripts/inspect_direct_bsc_capability_047_postcommit.sql)"
if ! printf '%s\n' "$unsafe_report" | grep -Eq \
  '^[[:space:]]*03_app_select_denied[[:space:]]*\|[[:space:]]*FAIL[[:space:]]*$'; then
  echo "EPHEMERAL_UNSAFE_APP_GRANT_NOT_DETECTED";exit 83
fi
echo "EPHEMERAL_UNSAFE_APP_GRANT_EXPLICITLY_DETECTED=PASS"
seen="$(psql -X -w -At -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture \
  -c 'BEGIN; SET LOCAL ROLE empiredb_app; SELECT count(*) FROM public.direct_bsc_buyer_capabilities; ROLLBACK;' | grep -x '0' || true)"
[[ "$seen" == "0" ]] || { echo "EPHEMERAL_FORCE_RLS_DENY_UNSAFE";exit 78; }
echo "EPHEMERAL_FORCE_RLS_DENIES_ACCIDENTAL_SELECT_GRANT=PASS"
echo "PRODUCTION_POSTGRESQL_PORT_TOUCHED=NO"
echo "PRODUCTION_MIGRATION_APPLIED=NO"
