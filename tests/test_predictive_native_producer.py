"""Full native integration on a disposable Unix-socket-only PostgreSQL cluster.

Every order, event, tenant and forecast here is synthetic isolated test data.
No production DSN, app import startup, service, migration or customer action.
"""
from datetime import date, timedelta
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

import psycopg
import pytest

from empire_os.predictive_materializer import (
    materialize_daily_actuals, produce_native_revenue_forecast,
)
from scripts.run_predictive_revenue_runtime_observer import run

ROOT = Path(__file__).resolve().parents[1]
PG = Path('/usr/lib/postgresql/18/bin')
TENANT = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'


@pytest.fixture(scope='module')
def cluster():
    assert os.geteuid() != 0, 'never start fixture as root'
    folder = Path(tempfile.mkdtemp(prefix='predictive-native-isolated-'))
    socket = folder / 'socket'
    socket.mkdir()
    def pg(cmd, *args):
        return subprocess.run([str(PG/cmd), *map(str,args)], check=True,
                              text=True, capture_output=True, timeout=30)
    pg('initdb', '-D', folder/'data', '-U', 'ubuntu', '-A', 'trust', '--no-sync')
    started = False
    try:
        pg('pg_ctl', '-D', folder/'data', '-l', folder/'log', '-o',
           f'-c listen_addresses= -c unix_socket_directories={socket}', 'start')
        started = True
        with psycopg.connect(host=str(socket), dbname='postgres', user='ubuntu',
                             autocommit=True) as c:
            c.execute('CREATE DATABASE empiredb')
        admin_dsn = f'host={socket} dbname=empiredb user=ubuntu'
        fixture = (ROOT/'scripts/test_empiredb_rev077_ephemeral_20261115.sh').read_text()
        setup = fixture.split("<<'SQL'\n",1)[1].split('\nSQL\n',1)[0]
        with psycopg.connect(admin_dsn, autocommit=True) as c:
            c.execute(setup)
            c.execute('DELETE FROM public.commercial_events')
            for f in ['076_predictive_forecast_registry_native_held.sql',
                      '077_predictive_daily_revenue_census_native_held.sql',
                      '078_predictive_future_forecast_registration_held.sql']:
                c.execute((ROOT/'migrations/empiredb'/f).read_text())
            c.execute('RESET ROLE')
            c.execute('GRANT empire_predictive_registry_reader TO census_a,census_b')
            c.execute('CREATE ROLE native_writer LOGIN NOINHERIT NOBYPASSRLS')
            c.execute('GRANT empire_predictive_forecast_registrar TO native_writer '
                      'WITH INHERIT FALSE, SET TRUE, ADMIN FALSE')
            c.execute("INSERT INTO public.empire_tenant_role_bindings(role_name,tenant_id) "
                      "VALUES ('native_writer',%s)", (TENANT,))
        yield admin_dsn, f'host={socket} dbname=empiredb user='
    finally:
        if started:
            pg('pg_ctl', '-D', folder/'data', '-m', 'immediate', 'stop')
        shutil.rmtree(folder)


@pytest.fixture
def source(cluster):
    admin, base = cluster
    with psycopg.connect(admin) as c:
        c.execute('DELETE FROM public.predictive_forecasts')
        c.execute('DELETE FROM public.commercial_events')
        c.execute("DELETE FROM public.fulfilment_orders WHERE commercial_payload->>'fixture'='native'")
        # Seven unique orders and recognized events. The original REV077
        # function checks order/buyer/product/price/time/lineage end to end.
        c.execute("""INSERT INTO public.fulfilment_orders
            (id,buyer_id,product_id,state,settled_at,price_cents,commercial_payload)
            SELECT md5('order'||i)::uuid,'11111111-1111-4111-8111-111111111111',
            '44444444-4444-4444-8444-444444444444','settled',
            ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date-i)::timestamp AT TIME ZONE 'UTC',
            (8-i)*100,'{"fixture":"native","causal_lineage":{"source":"isolated"}}'::jsonb
            FROM generate_series(1,7) i""")
        c.execute("""INSERT INTO public.commercial_events
            (id,event_type,occurred_at,fulfilment_order_id,buyer_id,product_id,amount_cents,payload)
            SELECT md5('event'||i)::uuid,'revenue_recognized',
            (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date-i)::timestamp AT TIME ZONE 'UTC')+interval '12 hours',
            md5('order'||i)::uuid,'11111111-1111-4111-8111-111111111111',
            '44444444-4444-4444-8444-444444444444',(8-i)*100,
            '{"actual_revenue":true,"causal_lineage":{"source":"isolated"}}'::jsonb
            FROM generate_series(1,7) i""")
    return dict(tenant_id=TENANT, census_dsn=base+'census_a',
                reader_dsn=base+'census_a', writer_dsn=base+'native_writer',
                registration_enabled=True, horizon_days=1)


def test_original_model_registration_day_alignment():
    origin = date(2026,11,16)
    rows = [dict(day=(origin-timedelta(days=7-i)).isoformat(), value=(i+1)*100,
                 source='canonical:commercial_events:rev077') for i in range(7)]
    m = materialize_daily_actuals(metric='recognized_revenue_cents', rows=rows,
        value_field='value', date_field='day', horizon_days=1, forecast_origin_date=origin)
    assert m.forecast.predicted_value == 900  # tomorrow, not today's 800
    assert m.forecast.horizon_days == 1


def test_real_sql_registration_independent_read_and_replay(source, cluster):
    result = produce_native_revenue_forecast(**source)
    assert result['status'] == 'NATIVE_FORECAST_REGISTERED_AND_READ_BACK', result
    assert result['registration_write_committed'] is True
    assert result['independent_registry_readback_verified'] is True
    assert not result['financial_actuals_verified']
    assert not result['calibration_authorized']
    assert not result['source_census_complete_as_of_snapshot']
    second = produce_native_revenue_forecast(**source)
    assert second['status'] == 'EXISTING_NATIVE_FORECAST_VERIFIED', second
    assert not second['registration_attempted']
    with psycopg.connect(cluster[0]) as c:
        assert c.execute('SELECT count(*) FROM public.predictive_forecasts').fetchone() == (1,)
        assert c.execute('SELECT predicted_value,horizon_days FROM public.predictive_forecasts').fetchone() == (900,1)
        # Original evidence-reader login has no writer membership or table DML.
        assert c.execute("SELECT pg_has_role('census_a','empire_predictive_forecast_registrar','MEMBER')").fetchone() == (False,)


def test_empty_day_not_imputed_and_no_model_or_registration(source, cluster):
    with psycopg.connect(cluster[0]) as c:
        c.execute("DELETE FROM public.commercial_events WHERE id=md5('event4')::uuid")
    r = produce_native_revenue_forecast(**source)
    assert r['status'] == 'AUTHENTICATED_SOURCE_DAY_EMPTY_OR_INCOMPLETE'
    assert not r['model_called'] and not r['registration_attempted']


def test_wrong_tenant_session_cannot_produce(source):
    source['tenant_id'] = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
    r = produce_native_revenue_forecast(**source)
    assert r['status'] == 'AUTHENTICATED_SOURCE_READ_FAILED'
    assert not r['model_called'] and not r['registration_attempted']


def test_writer_unactivated_still_validates_source_and_model(source):
    source['registration_enabled'] = False
    r = produce_native_revenue_forecast(**source)
    assert r['status'] == 'NATIVE_WRITER_ACTIVATION_REQUIRED', r
    assert r['model_called'] and not r['registration_attempted']


def test_evidence_login_refused_even_after_erroneous_writer_grant(source, cluster):
    # Isolated abuse case only: transport refuses a mistakenly elevated reader.
    with psycopg.connect(cluster[0]) as c:
        c.execute('GRANT empire_predictive_forecast_registrar TO census_a')
    try:
        source['writer_dsn'] = source['reader_dsn']
        r = produce_native_revenue_forecast(**source)
        assert r['status'] == 'NATIVE_REGISTRATION_NOT_VERIFIED_HOLD', r
        assert not r['independent_registry_readback_verified']
        with psycopg.connect(cluster[0]) as c:
            assert c.execute('SELECT count(*) FROM public.predictive_forecasts').fetchone() == (0,)
    finally:
        with psycopg.connect(cluster[0]) as c:
            c.execute('REVOKE empire_predictive_forecast_registrar FROM census_a')


def test_original_schedule_entry_executes_existing_producer(source, tmp_path):
    env = dict(EMPIRE_PREDICTIVE_NATIVE_SOURCE_ENABLED='1',
               EMPIRE_PREDICTIVE_NATIVE_REGISTRATION_ENABLED='1',
               EMPIRE_PREDICTIVE_TENANT_ID=source['tenant_id'],
               EMPIRE_PREDICTIVE_CENSUS_DSN=source['census_dsn'],
               EMPIRE_PREDICTIVE_REGISTRY_READER_DSN=source['reader_dsn'],
               EMPIRE_PREDICTIVE_REGISTRAR_DSN=source['writer_dsn'])
    r = run(root=tmp_path, producer_environment=env)
    assert r['native_producer']['status'] == 'NATIVE_FORECAST_REGISTERED_AND_READ_BACK', r
    assert r['governance']['db_write'] is True
    r = run(root=tmp_path, producer_environment=env)
    assert r['native_producer']['status'] == 'EXISTING_NATIVE_FORECAST_VERIFIED'
    assert r['governance']['db_write'] is False


def test_observer_readonly_flag_never_writes_registry(source, tmp_path):
    env = dict(EMPIRE_PREDICTIVE_NATIVE_SOURCE_ENABLED='1',
               EMPIRE_PREDICTIVE_NATIVE_REGISTRATION_ENABLED='1',
               EMPIRE_PREDICTIVE_TENANT_ID=source['tenant_id'],
               EMPIRE_PREDICTIVE_CENSUS_DSN=source['census_dsn'],
               EMPIRE_PREDICTIVE_REGISTRY_READER_DSN=source['reader_dsn'],
               EMPIRE_PREDICTIVE_REGISTRAR_DSN=source['writer_dsn'])
    r = run(root=tmp_path, write=False, producer_environment=env)
    assert r['native_producer']['status'] == 'NATIVE_WRITER_ACTIVATION_REQUIRED'
    assert not r['governance']['db_write']


def test_changed_source_cannot_replace_immutable_forecast(source, cluster):
    r = produce_native_revenue_forecast(**source)
    assert r['status'] == 'NATIVE_FORECAST_REGISTERED_AND_READ_BACK'
    with psycopg.connect(cluster[0]) as c:
        c.execute("UPDATE public.fulfilment_orders SET price_cents=price_cents+100 WHERE id=md5('order1')::uuid")
        c.execute("UPDATE public.commercial_events SET amount_cents=amount_cents+100 WHERE id=md5('event1')::uuid")
    r = produce_native_revenue_forecast(**source)
    assert r['status'] == 'IMMUTABLE_FORECAST_INPUT_CONFLICT_HOLD'
    assert not r['registration_attempted']
    with psycopg.connect(cluster[0]) as c:
        assert c.execute('SELECT count(*) FROM public.predictive_forecasts').fetchone() == (1,)


def test_lost_commit_acknowledgement_is_resolved_by_separate_read(source, monkeypatch):
    from empire_os.predictive_registry_transport import EmpireDbProspectiveForecastRegistration
    original = EmpireDbProspectiveForecastRegistration.register
    def lost(self, **kwargs):
        original(self, **kwargs)
        raise RuntimeError('simulated lost acknowledgement')
    monkeypatch.setattr(EmpireDbProspectiveForecastRegistration, 'register', lost)
    r = produce_native_revenue_forecast(**source)
    assert r['status'] == 'NATIVE_FORECAST_REGISTERED_AND_READ_BACK', r
    assert r['registration_commit_state'] == 'EXACT_RECORD_PRESENT'
    assert r['independent_registry_readback_verified']
    assert not r['registration_write_committed']  # own commit acknowledgement unknown


def test_invalid_source_record_fails_closed_before_model(source, cluster):
    with psycopg.connect(cluster[0]) as c:
        c.execute("UPDATE public.commercial_events SET payload='{}'::jsonb WHERE id=md5('event4')::uuid")
    r = produce_native_revenue_forecast(**source)
    assert r['status'] == 'AUTHENTICATED_SOURCE_READ_FAILED'
    assert not r['model_called'] and not r['registration_attempted']


def test_exact_guarded_grant_only_for_existing_dedicated_writer(source, cluster):
    from empire_os.predictive_registry_transport import prepare_native_writer_grant
    with psycopg.connect(cluster[0], autocommit=True) as c:
        c.execute('REVOKE empire_predictive_forecast_registrar FROM native_writer')
        c.execute(prepare_native_writer_grant(writer_login='native_writer', tenant_id=TENANT))
        assert c.execute("SELECT pg_has_role('native_writer','empire_predictive_forecast_registrar','SET')").fetchone() == (True,)
        with pytest.raises(psycopg.Error):
            c.execute(prepare_native_writer_grant(writer_login='census_a', tenant_id=TENANT))
        c.execute('ROLLBACK')
        assert c.execute("SELECT pg_has_role('census_a','empire_predictive_forecast_registrar','MEMBER')").fetchone() == (False,)
    with pytest.raises(ValueError):
        prepare_native_writer_grant(writer_login='empiredb_app', tenant_id=TENANT)
    with pytest.raises(ValueError):
        prepare_native_writer_grant(writer_login='evil;DROP ROLE x', tenant_id=TENANT)


def test_mature_native_records_reach_census_but_never_invent_finality(source, cluster):
    from empire_os.predictive_revenue_daily_census import review_native_outcome_readiness
    kwargs = dict(tenant_id=TENANT, reader_dsn=source['reader_dsn'], census_dsn=source['census_dsn'])
    assert review_native_outcome_readiness(**kwargs)['status'] == 'NO_MATURE_NATIVE_FORECASTS'
    with psycopg.connect(cluster[0]) as c:
        # Isolated fixture admin inserts a historical record, never backfill
        # a production forecast. Native writer cannot set registration time.
        c.execute("""INSERT INTO public.predictive_forecasts
            (forecast_key,model_name,model_version,metric,dimension_key,
             horizon_days,sample_count,predicted_value,r_squared,evidence_confidence,
             direction,source,evidence,generated_at)
             VALUES ('efr:11111111111111111111111111111111','empire-directional-linear',
             'v3-registration-day-v1','recognized_revenue_cents',%s,
             1,7,700,1,0.2,'up','empiredb_prospective_registration_source_claim_unverified',
             jsonb_build_object('target_utc_date',((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date-1)::text),
             CURRENT_TIMESTAMP-interval '2 days')""", ('tenant:'+TENANT,))
    r = review_native_outcome_readiness(**kwargs)
    assert r['status'] == 'INDEPENDENT_FINANCIAL_FINALITY_REQUIRED_NO_SCORING', r
    assert r['mature_registered_forecasts_observed'] == 1
    assert r['authenticated_candidate_outcome_days'] == 1
    assert r['financially_final_forecast_outcome_pairs'] == 0
    assert not r['scorecard_executed'] and not r['calibration_authorized']


def test_service_credentials_refuse_unmanaged_directory():
    from scripts.run_predictive_revenue_runtime_observer import _service_reader_configuration
    with pytest.raises(ValueError):
        _service_reader_configuration({'CREDENTIALS_DIRECTORY':'/tmp/fake-credentials'})


def test_missing_service_credentials_is_sanitized_and_never_registers(tmp_path):
    r = run(root=tmp_path, write=False, producer_environment={
        'EMPIRE_PREDICTIVE_NATIVE_SOURCE_ENABLED':'1',
        'CREDENTIALS_DIRECTORY':'/tmp/fake-credentials'})
    assert r['native_reader_credential_delivery'] == 'SERVICE_SCOPED_CREDENTIAL_UNAVAILABLE'
    assert r['native_producer']['status'] == 'NATIVE_SOURCE_CONFIGURATION_HOLD'
    assert not r['native_producer']['registration_attempted']


def test_approved_missing_writer_provision_uses_only_existing_capability(cluster):
    from empire_os.predictive_registry_transport import prepare_native_writer_login, NATIVE_FORECAST_WRITER_LOGIN
    from scripts.provision_crm_dedicated_logins import scram_verifier
    verifier = scram_verifier('isolated-test-password-not-production')
    with psycopg.connect(cluster[0], autocommit=True) as c:
        c.execute('ALTER TABLE public.empire_tenant_role_bindings ADD COLUMN IF NOT EXISTS evidence_ref text')
        c.execute("UPDATE public.empire_tenant_role_bindings SET evidence_ref='isolated-fixture'")
        c.execute(prepare_native_writer_login(tenant_id=TENANT, scram=verifier))
        flags = c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s',(NATIVE_FORECAST_WRITER_LOGIN,)).fetchone()
        assert flags == (True,False,False,False,False,False,False)
        assert c.execute('SELECT count(*) FROM pg_auth_members WHERE member=to_regrole(%s)',(NATIVE_FORECAST_WRITER_LOGIN,)).fetchone() == (1,)
        assert c.execute('SELECT tenant_id::text FROM public.empire_tenant_role_bindings WHERE role_name=%s',(NATIVE_FORECAST_WRITER_LOGIN,)).fetchone() == (TENANT,)
        with pytest.raises(psycopg.Error):
            c.execute(prepare_native_writer_login(tenant_id=TENANT, scram=verifier))
        c.execute('ROLLBACK')
    with pytest.raises(ValueError):
        prepare_native_writer_login(tenant_id=TENANT, scram='plaintext-password')


def test_actual_systemd_root_service_group_credential_layout():
    import stat
    from types import SimpleNamespace
    from scripts.run_predictive_revenue_runtime_observer import _service_credential_metadata_safe
    def info(mode, uid=0, gid=None):
        return SimpleNamespace(st_mode=stat.S_IFREG|mode, st_uid=uid,
                               st_gid=os.getegid() if gid is None else gid)
    assert _service_credential_metadata_safe(info(0o440))
    assert _service_credential_metadata_safe(info(0o400, uid=os.geteuid()))
    assert not _service_credential_metadata_safe(info(0o444))
    assert not _service_credential_metadata_safe(info(0o460))
    assert not _service_credential_metadata_safe(info(0o440, gid=os.getegid()+1))
    assert not _service_credential_metadata_safe(info(0o640))
