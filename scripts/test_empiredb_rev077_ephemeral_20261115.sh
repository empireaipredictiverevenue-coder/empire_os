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
# Verify exact REV076 + REV077 coexist in one original EmpireDB-like cluster.
# All forecast fixture inserts are synthetic and fixture-admin only.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -f "$root/migrations/empiredb/076_predictive_forecast_registry_native_held.sql"
psql -X -v ON_ERROR_STOP=1 -q -d empiredb <<'SQL_REGISTRY'
GRANT empire_predictive_registry_reader TO census_a,census_b,census_unbound;
INSERT INTO public.predictive_forecasts(
  forecast_key,model_name,model_version,metric,dimension_key,
  horizon_days,sample_count,predicted_value,r_squared,
  evidence_confidence,direction,source
) VALUES
  ('fixture:a:2026-11-10','empire','fixture-v1','recognized_revenue_cents',
   'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',7,14,14000,0.7,0.8,'up','synthetic_fixture'),
  ('fixture:b:2026-11-10','empire','fixture-v1','recognized_revenue_cents',
   'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',7,14,21000,0.7,0.8,'up','synthetic_fixture');
SQL_REGISTRY
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -f "$root/migrations/empiredb/077_predictive_daily_revenue_census_native_held.sql"
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -f "$root/migrations/empiredb/078_predictive_future_forecast_registration_held.sql"
echo REV076_REV077_REV078_DISPOSABLE_DDL=PASS
if psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -f "$root/migrations/empiredb/078_predictive_future_forecast_registration_held.sql" >/dev/null 2>&1; then
 echo REV078_DUPLICATE_RELEASE_ALLOWED; exit 10
fi
echo REV078_REAPPLY_DENIED=PASS
if psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -f "$root/migrations/empiredb/077_predictive_daily_revenue_census_native_held.sql" >/dev/null 2>&1; then
 echo UNSAFE_DUPLICATE_MIGRATION_ALLOWED; exit 5
fi
echo REV077_DUPLICATE_FAIL_CLOSED=PASS
# Use existing production Python source reader with two actual bound sessions.
PGHOST="$PGHOST" PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY'
from datetime import datetime, date, timezone
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
from empire_os.predictive_revenue_canonical_reader import CanonicalRevenueEvidenceUnavailable
at=datetime.now(timezone.utc)
day=date(2026,11,10)
for user,tenant,amount in (
    ("census_a","aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",12345),
    ("census_b","bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",20000),
):
    try:
        read_daily_revenue_census(
            day_utc=day, tenant_id=tenant, as_of=at,
            dsn="dbname=empiredb user="+user,
            require_session_tenant_binding=True,
        )
    except CanonicalRevenueEvidenceUnavailable as error:
        assert str(error)=="DAY_CENSUS_READ_FAILED",str(error)
    else:
        raise AssertionError("unmapped global event must block source day")
    print("GLOBAL_INVALID_SOURCE_BLOCKS_"+user+"=PASS")
print("UNMAPPED_GLOBAL_RECORD_DENIED_WITH_NO_COUNTS=PASS")
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
assert r["global_event_count"] is None,r
assert r["unknown_or_invalid_global_event_count"] is None,r
assert r["global_counts_disclosed_to_tenant"] is False,r
assert r["tenant_event_count"]==1,r
assert r["daily_revenue_census_verified"] is False,r
assert r["ledger_backfill_finality_attested"] is False,r
assert r["tenant_authorization_proven"] is False,r
assert r["eligible_for_revenue_forecast_calibration"] is False,r
assert r["execution_authority"]=="none",r
for user,tenant,expected in (
    ("census_a","aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",12345),
    ("census_b","bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",20000),
):
    item=read_daily_revenue_census(
        day_utc=date(2026,11,10),tenant_id=tenant,
        as_of=datetime.now(timezone.utc),
        dsn="dbname=empiredb user="+user,
        require_session_tenant_binding=True)
    assert item["tenant_event_count"]==1,item
    assert item["tenant_candidate_amount_cents"]==expected,item
    assert item["global_event_count"] is None,item
    assert item["global_counts_disclosed_to_tenant"] is False,item
    print("PRIVATE_CANDIDATE_"+user+"=PASS")
print("SOURCE_CANDIDATE_NOT_SETTLED_CASH_OR_CALIBRATION=PASS")
PY
# Original registered forecast reader and census source preflight together.
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY_INTEGRATION'
from datetime import datetime,timezone,timedelta
from empire_os.predictive_revenue_tenant_registry_inspector import inspect_tenant_bound_predictive_registry
from empire_os.predictive_revenue_source_preflight import review_authenticated_sources
now=datetime.now(timezone.utc)
for name,tenant in (
  ('census_a','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
  ('census_b','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
):
    dsn='dbname=empiredb user='+name
    inventory=inspect_tenant_bound_predictive_registry(
      dsn=dsn,tenant_id=tenant,as_of=now,limit=10)
    assert inventory['observed_row_count']==1,inventory
    historical=inspect_tenant_bound_predictive_registry(
      dsn=dsn,tenant_id=tenant,as_of=now-timedelta(minutes=2),limit=10)
    assert historical['observed_row_count']==0,historical
    assert historical['status']=='REGISTRY_EMPTY_COVERAGE_UNKNOWN_HOLD',historical
    assert inventory['source_rows_are_complete_census'] is False,inventory
    assert inventory['original_forecast_immutable_registration_verified'] is False,inventory
    assert inventory['customer_delivery_enabled'] is False,inventory
    preflight=review_authenticated_sources(
      tenant_id=tenant,registry_dsn=dsn,census_dsn=dsn,as_of=now)
    assert preflight['registry_reader_authenticated_session'] is True,preflight
    assert preflight['census_reader_authenticated_session'] is True,preflight
    assert preflight['registry_scoped_rows_observed']==1,preflight
    assert preflight['independently_verified_forecast_actual_pairs']==0,preflight
    assert preflight['model_calibration_ready'] is False,preflight
    assert preflight['customer_revenue_amount_verified'] is False,preflight
    print('ORIGINAL_TENANT_READER_AND_PREFLIGHT_'+name+'=PASS')
print('INTEGRATED_REGISTRY_CENSUS_STILL_NOT_CALIBRATION=PASS')
PY_INTEGRATION
# REV078: only DB-clock prospective registration through a dedicated
# synthetic tenant session. No login/membership installed by production DDL.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb \
 -c "GRANT empire_predictive_forecast_registrar TO census_a,census_b,census_unbound"
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY_REGISTRATION'
from datetime import datetime,timedelta,timezone
import psycopg
from psycopg import Error
now=datetime.now(timezone.utc)
observed=(now.date()-timedelta(days=1))
signature="public.register_predictive_revenue_forecast_v1"
placeholder="%s::text,%s::text,%s::date,%s::integer,%s::integer,%s::numeric,%s::numeric,%s::numeric,%s::text,%s::text"
query=f"SELECT * FROM {signature}({placeholder})"
for login in ('census_a','census_b'):
    with psycopg.connect('dbname=empiredb user='+login) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
            cursor.execute(query,(
                'empire_baseline','v1',observed,7,14,12345,0.8,0.75,'up','f'*64,
            ))
            row=cursor.fetchone()
            assert len(row)==2,row
            assert row[0].startswith('efr:')
            assert row[1].tzinfo is not None
            assert abs((datetime.now(timezone.utc)-row[1]).total_seconds()) < 60
            key=row[0]
    # The first registration committed before we intentionally force errors.
    # A denied statement inside the first transaction would roll back its
    # source insert and invalidate the unique/replay assertion.
    with psycopg.connect('dbname=empiredb user='+login) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
            try:
                cursor.execute('SELECT count(*) FROM public.predictive_forecasts')
            except Error as exc:
                assert exc.sqlstate == '42501',exc
                connection.rollback()
            else:raise AssertionError('registrar obtained direct SELECT')
    # An identical model/source-day/horizon must not create a second row.
    with psycopg.connect('dbname=empiredb user='+login) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
            try:
                cursor.execute(query,(
                    'empire_baseline','v1',observed,7,14,99999,0.8,0.75,'up','f'*64,
                ))
            except Error as exc:
                assert exc.sqlstate=='23505',exc
                connection.rollback()
            else:raise AssertionError('duplicate registration was allowed')
    # A different recent source observation for the SAME target/horizon
    # must not create a second potentially cherry-picked prediction.
    with psycopg.connect('dbname=empiredb user='+login) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
            try:
                cursor.execute(query,(
                    'empire_baseline','v1',observed-timedelta(days=1),7,14,
                    99999,0.8,0.75,'up','f'*64,
                ))
            except Error as exc:
                assert exc.sqlstate=='23505',exc
                connection.rollback()
            else:
                raise AssertionError('alternate source day permitted forecast replay')
    print('SAME_TARGET_ALTERNATE_SOURCE_REPLAY_DENIED_'+login+'=PASS')
    # The original reader observes the newly registered row ONLY for own tenant.
    with psycopg.connect('dbname=empiredb user='+login) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute('SET LOCAL ROLE empire_predictive_registry_reader')
            cursor.execute('SELECT forecast_key,evidence,generated_at FROM public.predictive_forecasts WHERE forecast_key=%s',(key,))
            records=cursor.fetchall()
            assert len(records)==1,records
            assert records[0][1]['horizon_basis']=='registration_utc_day'
            assert records[0][1]['observed_through_utc']==observed.isoformat()
            assert records[0][1]['target_utc_date']==(
                records[0][2].date()+timedelta(days=7)).isoformat()
            assert records[0][1]['independent_timestamp_custody'] is False
            assert records[0][1]['original_source_authentication'] is False
            assert records[0][1]['independent_financial_actuals'] is False
            assert records[0][1]['calibration_authorized'] is False
    print('FUTURE_ONLY_REGISTRATION_'+login+'=PASS')
with psycopg.connect('dbname=empiredb user=census_unbound') as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
        try:
            cursor.execute(query,(
                'empire_baseline','v1',observed,7,14,12345,0.8,0.75,'up','f'*64,
            ))
        except Error as exc:
            assert exc.sqlstate=='P0001',exc
            connection.rollback()
        else:raise AssertionError('unbound tenant created a prediction')
print('UNBOUND_TENANT_FORECAST_REFUSED=PASS')
with psycopg.connect('dbname=empiredb user=census_a') as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
        for day,horizon in ((now.date(),7),(observed,0),(observed,366)) :
            try:
                cursor.execute(query,(
                    'empire_baseline','v2',day,horizon,14,12345,0.8,0.75,'up','f'*64,
                ))
            except Error as exc:
                assert exc.sqlstate=='P0001',exc
                connection.rollback()
                cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
            else:raise AssertionError('source day/horizon did not fail closed')
print('INVALID_OBSERVATION_DAY_OR_HORIZON_DENIED=PASS')
# A valid 1-day forecast may use an older but still recent observation.
# Previous implementation rejected this as nonprospective because it
# incorrectly measured horizon from the observation day.
with psycopg.connect('dbname=empiredb user=census_a') as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
        older=now.date()-timedelta(days=2)
        cursor.execute(query,(
            'empire_baseline','older_1day',older,1,14,11000,0.8,0.75,'up','f'*64,
        ))
        registration_ref,registered_at=cursor.fetchone()
with psycopg.connect('dbname=empiredb user=census_a') as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
        cursor.execute('SET LOCAL ROLE empire_predictive_registry_reader')
        cursor.execute('SELECT evidence FROM public.predictive_forecasts WHERE forecast_key=%s',
                       (registration_ref,))
        evidence=cursor.fetchone()[0]
        assert evidence['observed_through_utc']==older.isoformat()
        assert evidence['target_utc_date']==(
            registered_at.date()+timedelta(days=1)).isoformat()
        assert evidence['horizon_basis']=='registration_utc_day'
print('ONE_DAY_HORIZON_FROM_REGISTRATION_NOT_STALE_SOURCE=PASS')
with psycopg.connect('dbname=empiredb user=census_a') as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET LOCAL ROLE empire_predictive_forecast_registrar')
        try:
            cursor.execute(query,(
                'empire_baseline','v3',observed,7,14,12345.5,0.8,0.75,'up','f'*64,
            ))
        except Error as exc:
            assert exc.sqlstate=='P0001',exc
            connection.rollback()
        else:raise AssertionError('fractional cents passed the registration contract')
print('FRACTIONAL_CENTS_REGISTRATION_DENIED=PASS')
PY_REGISTRATION
# Only a dedicated role can call the original DB registration function.
# Even role members cannot change the registry table by bypassing the RPC.
if psql -X -v ON_ERROR_STOP=1 -qAt -U census_a -d empiredb \
 -c "BEGIN; SET LOCAL ROLE empire_predictive_forecast_registrar; INSERT INTO public.predictive_forecasts(forecast_key,model_name,model_version,metric,dimension_key,horizon_days,sample_count,predicted_value,r_squared,evidence_confidence,direction,source) VALUES ('forged','forged','v1','recognized_revenue_cents','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',7,14,100,0.8,0.8,'up','forged'); ROLLBACK;" >/dev/null 2>&1; then
 echo REV078_REGISTRAR_DIRECT_TABLE_INSERT_ALLOWED; exit 11
fi
if psql -X -v ON_ERROR_STOP=1 -qAt -U census_a -d empiredb \
 -c "BEGIN; SET LOCAL ROLE empire_predictive_forecast_registrar; DELETE FROM public.predictive_forecasts; ROLLBACK;" >/dev/null 2>&1; then
 echo REV078_REGISTRAR_DIRECT_TABLE_DELETE_ALLOWED; exit 12
fi
if psql -X -v ON_ERROR_STOP=1 -qAt -U census_a -d empiredb \
 -c "BEGIN; SET LOCAL ROLE empire_predictive_forecast_registrar; UPDATE public.predictive_forecasts SET predicted_value=0; ROLLBACK;" >/dev/null 2>&1; then
 echo REV078_REGISTRAR_DIRECT_TABLE_UPDATE_ALLOWED; exit 13
fi
echo REGISTRAR_DIRECT_WRITE_AND_REWRITE_DENIED=PASS
# Duplicate recognized events for one order cannot count twice as income.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "INSERT INTO public.commercial_events(id,event_type,occurred_at,fulfilment_order_id,buyer_id,product_id,amount_cents,payload) SELECT 'aaaa1111-aaaa-4111-8111-aaaaaaaaaaaa',event_type,occurred_at,fulfilment_order_id,buyer_id,product_id,amount_cents,payload FROM public.commercial_events WHERE id='77777777-7777-4777-8777-777777777777'"
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PYTEST_DUP'
from datetime import date,datetime,timezone
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
from empire_os.predictive_revenue_canonical_reader import CanonicalRevenueEvidenceUnavailable
try:
    read_daily_revenue_census(
      day_utc=date(2026,11,10),
      tenant_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      as_of=datetime.now(timezone.utc),
      dsn="dbname=empiredb user=census_a",
      require_session_tenant_binding=True)
except CanonicalRevenueEvidenceUnavailable as e:
    assert str(e)=="DAY_CENSUS_READ_FAILED",str(e)
else:
    raise AssertionError("duplicate recognition not blocked")
print("DUPLICATE_ORDER_RECOGNITION_BLOCKED=PASS")
PYTEST_DUP
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "DELETE FROM public.commercial_events WHERE id='aaaa1111-aaaa-4111-8111-aaaaaaaaaaaa'"
# Settlement after the forecast target day cannot be counted as a day-close.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "UPDATE public.fulfilment_orders SET settled_at='2026-11-12T00:00:00Z' WHERE id='33333333-3333-4333-8333-333333333333'"
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PYTEST_LATE'
from datetime import date,datetime,timezone
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
from empire_os.predictive_revenue_canonical_reader import CanonicalRevenueEvidenceUnavailable
try:
    read_daily_revenue_census(
      day_utc=date(2026,11,10),
      tenant_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      as_of=datetime.now(timezone.utc),
      dsn="dbname=empiredb user=census_a",
      require_session_tenant_binding=True)
except CanonicalRevenueEvidenceUnavailable as e:
    assert str(e)=="DAY_CENSUS_READ_FAILED",str(e)
else:
    raise AssertionError("late-settled outcome not blocked")
print("POST_TARGET_SETTLEMENT_BLOCKED=PASS")
PYTEST_LATE
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "UPDATE public.fulfilment_orders SET settled_at='2026-11-09T00:00:00Z' WHERE id='33333333-3333-4333-8333-333333333333'"
# Cross-day duplicate recognition on the same order is also excluded.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "INSERT INTO public.commercial_events(id,event_type,occurred_at,fulfilment_order_id,buyer_id,product_id,amount_cents,payload) SELECT 'bbbb1111-bbbb-4111-8111-bbbbbbbbbbbb',event_type,'2026-11-09T12:00:00Z',fulfilment_order_id,buyer_id,product_id,amount_cents,payload FROM public.commercial_events WHERE id='77777777-7777-4777-8777-777777777777'"
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY_CROSS_DAY'
from datetime import date,datetime,timezone
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
from empire_os.predictive_revenue_canonical_reader import CanonicalRevenueEvidenceUnavailable
try:
    read_daily_revenue_census(day_utc=date(2026,11,10),
      tenant_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      as_of=datetime.now(timezone.utc),dsn="dbname=empiredb user=census_a",
      require_session_tenant_binding=True)
except CanonicalRevenueEvidenceUnavailable as e:
    assert str(e)=="DAY_CENSUS_READ_FAILED",str(e)
else:raise AssertionError('cross-day duplicate was counted as revenue')
print('CROSS_DAY_DUPLICATE_RECOGNITION_BLOCKED=PASS')
PY_CROSS_DAY
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "DELETE FROM public.commercial_events WHERE id='bbbb1111-bbbb-4111-8111-bbbbbbbbbbbb'"
# Revenue event timestamp before settlement, even within the same day,
# must not be accepted as a source observation at event time.
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "UPDATE public.fulfilment_orders SET settled_at='2026-11-10T18:00:00Z' WHERE id='33333333-3333-4333-8333-333333333333'"
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY_PRE_SETTLE'
from datetime import date,datetime,timezone
from empire_os.predictive_revenue_daily_census import read_daily_revenue_census
from empire_os.predictive_revenue_canonical_reader import CanonicalRevenueEvidenceUnavailable
try:
    read_daily_revenue_census(day_utc=date(2026,11,10),
      tenant_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      as_of=datetime.now(timezone.utc),dsn="dbname=empiredb user=census_a",
      require_session_tenant_binding=True)
except CanonicalRevenueEvidenceUnavailable as e:
    assert str(e)=="DAY_CENSUS_READ_FAILED",str(e)
else:raise AssertionError('pre-settlement recognition was counted as revenue')
print('PRE_SETTLEMENT_RECOGNITION_BLOCKED=PASS')
PY_PRE_SETTLE
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -c "UPDATE public.fulfilment_orders SET settled_at='2026-11-09T00:00:00Z' WHERE id='33333333-3333-4333-8333-333333333333'"
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
