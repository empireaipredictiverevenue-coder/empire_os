#!/usr/bin/env bash
# Test held migration ONLY in a new, temporary, UNIX-socket PostgreSQL cluster.
# No production DB, service, role, password, localhost TCP or payment is used.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_BIN=/usr/lib/postgresql/18/bin
scratch="$(mktemp -d /tmp/empire-rev051-fixture-XXXXXXXX)"
chmod 0700 "$scratch"
mkdir -m 0700 "$scratch/socket"
stopped=0
cleanup() {
  if [[ "$stopped" == 1 ]]; then
    "$PG_BIN/pg_ctl" -D "$scratch/db" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$scratch"
}
trap cleanup EXIT
"$PG_BIN/initdb" -D "$scratch/db" -A trust -U fixture_admin --no-instructions >"$scratch/initdb.log" 2>&1
# Listen on temp UNIX socket only; no TCP or production PostgreSQL touched.
"$PG_BIN/pg_ctl" -D "$scratch/db" -o "-c listen_addresses='' -k $scratch/socket -p 59631" -w start >"$scratch/pg.log" 2>&1
stopped=1
psql() {
  "$PG_BIN/psql" -X -w -v ON_ERROR_STOP=1 -h "$scratch/socket" -p 59631 "$@"
}
psql -U fixture_admin -d postgres -q <<'SQL'
CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE revenue_alpha LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE revenue_beta LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE empiredb OWNER fixture_admin;
SQL
psql -U fixture_admin -d empiredb -q <<'SQL'
GRANT CREATE, USAGE ON SCHEMA public TO empiredb_migrator;
SET ROLE empiredb_migrator;
CREATE TABLE public.empire_tenant_role_bindings (
  role_name name PRIMARY KEY,
  tenant_id uuid NOT NULL,
  active boolean NOT NULL
);
CREATE TABLE public.buyers (
  id uuid PRIMARY KEY,
  org_id uuid
);
CREATE TABLE public.fulfilment_orders (
  id uuid PRIMARY KEY,
  buyer_id uuid,
  product_id uuid,
  state text NOT NULL,
  settled_at timestamptz,
  price_cents bigint NOT NULL,
  commercial_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE public.commercial_events (
  id uuid PRIMARY KEY,
  event_type text NOT NULL,
  fulfilment_order_id uuid,
  buyer_id uuid,
  product_id uuid,
  amount_cents bigint,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.empire_tenant_role_bindings VALUES
 ('revenue_alpha','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true),
 ('revenue_beta','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
INSERT INTO public.buyers VALUES
 ('11111111-1111-4111-8111-111111111111',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('22222222-2222-4222-8222-222222222222',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO public.fulfilment_orders VALUES
 ('33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',
  'settled',now(),12345,
  '{"causal_lineage":{"example":"alpha"}}'::jsonb),
 ('55555555-5555-4555-8555-555555555555',
  '22222222-2222-4222-8222-222222222222',
  '66666666-6666-4666-8666-666666666666',
  'settled',now(),77889,
  '{"causal_lineage":{"example":"beta"}}'::jsonb),
 ('88888888-8888-4888-8888-888888888888',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',
  'settled',now(),9000,
  '{"causal_lineage":{"example":"mismatch"}}'::jsonb);
INSERT INTO public.commercial_events VALUES
 ('77777777-7777-4777-8777-777777777777',
  'revenue_recognized',
  '33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',12345,
  '{"actual_revenue":true,"causal_lineage":{"example":"alpha"}}'::jsonb,now()),
 ('99999999-9999-4999-8999-999999999999',
  'revenue_recognized',
  '55555555-5555-4555-8555-555555555555',
  '22222222-2222-4222-8222-222222222222',
  '66666666-6666-4666-8666-666666666666',77889,
  '{"actual_revenue":true,"causal_lineage":{"example":"beta"}}'::jsonb,now()),
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaac',
  'revenue_recognized',
  '88888888-8888-4888-8888-888888888888',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',9001,
  '{"actual_revenue":true,"causal_lineage":{"example":"mismatch"}}'::jsonb,now());
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
  SELECT tenant_id FROM public.empire_tenant_role_bindings
   WHERE role_name=session_user AND active IS TRUE LIMIT 1
$$;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
RESET ROLE;
SQL
psql -U fixture_admin -d empiredb -q -f "$repo/migrations/empiredb/051_predictive_revenue_event_reader_held.sql" >"$scratch/migration.log"
# The held migration intentionally lacks a dedicated login grant: catalog
# preflight MUST remain HOLD even though the role/function are now present.
psql -U fixture_admin -d empiredb -Atq \
  -f "$repo/scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql" \
  > "$scratch/before_grant.json"
python3 - "$scratch/before_grant.json" <<'PYREAD'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="HOLD_EVENT_READER_CATALOG_NOT_PROVEN",x
assert x["function_exists"] is True and x["capability_exists"] is True
assert x["dedicated_login_member_exists"] is False
PYREAD
# Dedicated ephemeral login(s) for testing only; migration never creates them.
psql -U fixture_admin -d empiredb -q <<'SQL'
GRANT empire_predictive_revenue_evidence_reader TO revenue_alpha
  WITH INHERIT FALSE, SET TRUE;
GRANT empire_predictive_revenue_evidence_reader TO revenue_beta
  WITH INHERIT FALSE, SET TRUE;
SQL
echo -n 'FIXTURE_FUNCTION_PROCONFIG='
psql -U fixture_admin -d empiredb -Atq -c "SELECT proconfig::text FROM pg_catalog.pg_proc WHERE oid=pg_catalog.to_regprocedure('public.read_predictive_revenue_event_v1(uuid,text)')"
# After ephemeral login grants, exact real catalog checker should PASS,
# without confusing catalog attributes with a verified customer event.
psql -U fixture_admin -d empiredb -Atq \
  -f "$repo/scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql" \
  > "$scratch/after_grant.json"
python3 - "$scratch/after_grant.json" <<'PYREAD'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="CATALOG_PREREQUISITES_PRESENT_NOT_EVENT_PROVEN",x
assert x["function_body_independently_security_reviewed"] is False
assert x["canonical_event_fetched"] is False
assert x["customer_report_release_authorized"] is False
PYREAD
alpha="$(psql -U revenue_alpha -d empiredb -Atq <<'SQL'
BEGIN READ ONLY;
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
SELECT count(*)::text||':'||COALESCE(max(amount_cents),0)::text
  FROM public.read_predictive_revenue_event_v1(
   '77777777-7777-4777-8777-777777777777',
   'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
ROLLBACK;
SQL
)"
test "$alpha" = '1:12345'
denied="$(psql -U revenue_beta -d empiredb -Atq <<'SQL'
BEGIN READ ONLY;
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
SELECT count(*)::text
  FROM public.read_predictive_revenue_event_v1(
    '77777777-7777-4777-8777-777777777777',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
ROLLBACK;
SQL
)"
test "$denied" = 0
other="$(psql -U revenue_alpha -d empiredb -Atq <<'SQL'
BEGIN READ ONLY;
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
SELECT count(*)::text
  FROM public.read_predictive_revenue_event_v1(
    '99999999-9999-4999-8999-999999999999',
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
ROLLBACK;
SQL
)"
test "$other" = 0
bad="$(psql -U revenue_alpha -d empiredb -Atq <<'SQL'
BEGIN READ ONLY;
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
SELECT count(*)::text
  FROM public.read_predictive_revenue_event_v1(
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaac',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
ROLLBACK;
SQL
)"
test "$bad" = 0
# Direct source-table SELECT should fail even after SET LOCAL ROLE.
if psql -U revenue_alpha -d empiredb -Atq >"$scratch/direct.log" 2>&1 <<'SQL'
BEGIN READ ONLY;
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
SELECT count(*) FROM public.commercial_events;
ROLLBACK;
SQL
then
  echo "FAIL: table SELECT unexpectedly allowed" >&2
  exit 7
fi
# The role does not acquire financial write authority.
if psql -U revenue_alpha -d empiredb -Atq >"$scratch/write.log" 2>&1 <<'SQL'
BEGIN READ ONLY;
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
DELETE FROM public.commercial_events WHERE false;
ROLLBACK;
SQL
then
  echo "FAIL: financial write unexpectedly allowed" >&2
  exit 8
fi
echo "REV051_ISOLATED_POSTGRES_PASS tenant_alpha_own=1 tenant_beta_cross=0 tenant_alpha_cross=0 mismatched_price=0 direct_table_read=DENIED write=DENIED production=UNTOUCHED"
