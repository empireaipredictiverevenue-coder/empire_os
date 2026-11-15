#!/usr/bin/env bash
# Disposable PostgreSQL 18, Unix-socket-only EmpireDB REV077 source-census test.
# No live database, customer data, real identities or service changes.
set -euo pipefail
export PATH=/usr/lib/postgresql/18/bin:/usr/bin:/bin
test "$(id -u)" != 0 || { echo REFUSE_ROOT_FIXTURE; exit 2; }
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d /tmp/empiredb-rev077-XXXXXXXX)"
trap 'pg_ctl -D "$tmp/data" -m immediate stop >/dev/null 2>&1 || :; rm -rf "$tmp"' EXIT
initdb -D "$tmp/data" -U ubuntu -A trust -E UTF8 --no-sync >/dev/null
mkdir "$tmp/socket"
pg_ctl -D "$tmp/data" -l "$tmp/log" -o "-c listen_addresses= -c unix_socket_directories=$tmp/socket" start >/dev/null
export PGHOST="$tmp/socket" PGUSER=ubuntu
createdb empiredb
psql -X -v ON_ERROR_STOP=1 -q -d empiredb <<'SQL'
CREATE ROLE empiredb_migrator NOLOGIN;
CREATE ROLE empire_predictive_revenue_evidence_reader NOLOGIN NOINHERIT NOBYPASSRLS;
CREATE ROLE census_a LOGIN NOINHERIT;
CREATE ROLE census_b LOGIN NOINHERIT;
CREATE ROLE census_unbound LOGIN NOINHERIT;
GRANT empire_predictive_revenue_evidence_reader TO census_a,census_b,census_unbound;
GRANT CREATE,USAGE ON SCHEMA public TO empiredb_migrator;
GRANT USAGE ON SCHEMA public TO empire_predictive_revenue_evidence_reader;
SET ROLE empiredb_migrator;
CREATE TABLE public.empire_tenant_role_bindings(
 role_name name PRIMARY KEY, tenant_id uuid NOT NULL, active boolean NOT NULL DEFAULT true
);
CREATE TABLE public.buyers(id uuid PRIMARY KEY,org_id uuid);
CREATE TABLE public.fulfilment_orders(
 id uuid PRIMARY KEY,buyer_id uuid,product_id uuid,state text,
 settled_at timestamptz,price_cents bigint,commercial_payload jsonb
);
CREATE TABLE public.commercial_events(
 id uuid PRIMARY KEY,event_type text,occurred_at timestamptz,
 fulfilment_order_id uuid,buyer_id uuid,product_id uuid,amount_cents bigint,payload jsonb
);
CREATE FUNCTION public.empire_current_tenant_id() RETURNS uuid
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public
 AS $$SELECT tenant_id FROM public.empire_tenant_role_bindings
 WHERE role_name=session_user AND active LIMIT 1$$;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
 TO empire_predictive_revenue_evidence_reader;
-- REV051 prior installation is separately tested. Only existence required here.
CREATE FUNCTION public.read_predictive_revenue_event_v1(uuid,text)
 RETURNS integer LANGUAGE sql STABLE SECURITY DEFINER SET search_path=''
 AS $$SELECT 0$$;
RESET ROLE;
INSERT INTO public.empire_tenant_role_bindings(role_name,tenant_id) VALUES
 ('census_a','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('census_b','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO public.buyers(id,org_id) VALUES
 ('11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('22222222-2222-4222-8222-222222222222','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO public.fulfilment_orders(
 id,buyer_id,product_id,state,settled_at,price_cents,commercial_payload)
 VALUES
 ('33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111',
 '44444444-4444-4444-8444-444444444444','settled','2026-11-09T00:00:00Z',12345,
 '{"causal_lineage":{"source":"a"}}'),
 ('55555555-5555-4555-8555-555555555555','22222222-2222-4222-8222-222222222222',
 '66666666-6666-4666-8666-666666666666','settled','2026-11-09T00:00:00Z',20000,
 '{"causal_lineage":{"source":"b"}}');
INSERT INTO public.commercial_events(
 id,event_type,occurred_at,fulfilment_order_id,buyer_id,
 product_id,amount_cents,payload) VALUES
 ('77777777-7777-4777-8777-777777777777','revenue_recognized','2026-11-10T12:00:00Z',
 '33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111',
 '44444444-4444-4444-8444-444444444444',12345,
 '{"actual_revenue":true,"causal_lineage":{"source":"a"}}'),
 ('88888888-8888-4888-8888-888888888888','revenue_recognized','2026-11-10T12:00:00Z',
 '55555555-5555-4555-8555-555555555555','22222222-2222-4222-8222-222222222222',
 '66666666-6666-4666-8666-666666666666',20000,
 '{"actual_revenue":true,"causal_lineage":{"source":"b"}}'),
 ('99999999-9999-4999-8999-999999999999','revenue_recognized','2026-11-10T12:00:00Z',
 NULL,NULL,NULL,777,'{"actual_revenue":true}');
SQL
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -f "$root/migrations/empiredb/077_predictive_daily_revenue_census_native_held.sql"
echo REV077_DISPOSABLE_DDL=PASS
if psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -f "$root/migrations/empiredb/077_predictive_daily_revenue_census_native_held.sql" >/dev/null 2>&1; then
 echo UNSAFE_DUPLICATE_MIGRATION_ALLOWED; exit 5
fi
echo REV077_DUPLICATE_FAIL_CLOSED=PASS
# Use existing production Python source reader with two actual bound sessions.
PGHOST="$PGHOST" PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY'
from datetime import datetime, date, timezone
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
at=datetime.now(timezone.utc)
day=date(2026,11,10)
for user,tenant,amount in (
    ("census_a","aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",12345),
    ("census_b","bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",20000),
):
    row=read_daily_revenue_census(
        day_utc=day, tenant_id=tenant, as_of=at,
        dsn="dbname=empiredb user="+user, require_session_tenant_binding=True,
    )
    assert row["global_event_count"]==3,row
    assert row["tenant_event_count"]==1,row
    assert row["unknown_or_invalid_global_event_count"]==1,row
    assert row["tenant_candidate_amount_cents"] is None,row
    assert row["status"]=="DAY_CENSUS_INCOMPLETE_HOLD",row
    assert row["eligible_for_revenue_forecast_calibration"] is False,row
    assert row["database_session_tenant_identity_matched"] is True,row
    print("RESTRICTED_SOURCE_"+user+"=PASS")
print("UNMAPPED_GLOBAL_RECORD_BLOCKS_CALIBRATION=PASS")
PY
if psql -X -v ON_ERROR_STOP=1 -qAt -U census_a -d empiredb \
 -c "BEGIN READ ONLY; SET LOCAL ROLE empire_predictive_revenue_evidence_reader; SELECT count(*) FROM public.commercial_events; ROLLBACK;" >/dev/null 2>&1; then
 echo UNAUTHORIZED_DIRECT_LEDGER_READ_ALLOWED; exit 6
fi
if psql -X -v ON_ERROR_STOP=1 -qAt -U census_a -d empiredb \
 -c "BEGIN READ ONLY; SET LOCAL ROLE empire_predictive_revenue_evidence_reader; SELECT * FROM public.read_predictive_revenue_day_v1('2026-11-10','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'); ROLLBACK;" >/dev/null 2>&1; then
 echo UNAUTHORIZED_CROSS_TENANT_DAY_ALLOWED; exit 7
fi
if psql -X -v ON_ERROR_STOP=1 -qAt -U census_unbound -d empiredb \
 -c "BEGIN READ ONLY; SET LOCAL ROLE empire_predictive_revenue_evidence_reader; SELECT * FROM public.read_predictive_revenue_day_v1('2026-11-10','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'); ROLLBACK;" >/dev/null 2>&1; then
 echo UNBOUND_TENANT_DAY_ALLOWED; exit 8
fi
echo SOURCE_CENSUS_TENANT_AND_DIRECT_LEDGER_GATES=PASS
# Once invalid input is removed, source candidate is admitted, never finality.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -c "DELETE FROM public.commercial_events WHERE id='99999999-9999-4999-8999-999999999999'"
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY'
from datetime import date,datetime,timezone
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
r=read_daily_revenue_census(
  day_utc=date(2026,11,10),
  tenant_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  as_of=datetime.now(timezone.utc),
  dsn="dbname=empiredb user=census_a",
  require_session_tenant_binding=True)
assert r["status"]=="DAY_SOURCE_CENSUS_CANDIDATE",r
assert r["tenant_candidate_amount_cents"]==12345,r
assert r["global_event_count"]==2,r
assert r["daily_revenue_census_verified"] is False,r
assert r["ledger_backfill_finality_attested"] is False,r
assert r["tenant_authorization_proven"] is False,r
assert r["eligible_for_revenue_forecast_calibration"] is False,r
print("SOURCE_CANDIDATE_NOT_SETTLED_CASH_OR_CALIBRATION=PASS")
PY
# A later source FORCE RLS change can hide rows from the definer. Detect
# ownership/policy drift at query time rather than emitting false totals.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -c "ALTER TABLE public.commercial_events FORCE ROW LEVEL SECURITY"
if psql -X -v ON_ERROR_STOP=1 -qAt -U census_a -d empiredb \
 -c "BEGIN READ ONLY; SET LOCAL ROLE empire_predictive_revenue_evidence_reader; SELECT * FROM public.read_predictive_revenue_day_v1('2026-11-10','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'); ROLLBACK;" >/dev/null 2>&1; then
 echo SOURCE_FORCE_RLS_DRIFT_WENT_UNDETECTED; exit 9
fi
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -c "ALTER TABLE public.commercial_events NO FORCE ROW LEVEL SECURITY"
echo SOURCE_VISIBILITY_DRIFT_DENIAL=PASS
echo REV077_DISPOSABLE_POSTGRESQL18=PASS
