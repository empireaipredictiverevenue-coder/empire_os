"""Original V5: disabled public API and held tenant/domain PostgreSQL schema."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from empire_os.predictive_cloud_v5_held_api import create_v5_held_api_router

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/'migrations/empiredb/063_v5_whitelabel_candidate_registry_held.sql'
FIXTURE=ROOT/'scripts/rehearse_predictive_cloud_v5_pg_registry_20261024.sh'


def test_original_app_not_mounted():
    source=(ROOT/'empire_os/hub.py').read_text()
    assert 'create_v5_held_api_router' not in source
    assert 'predictive_cloud_v5_held_api' not in source


def test_shadow_status_read_only_and_never_active():
    app=FastAPI()
    app.include_router(create_v5_held_api_router())
    with TestClient(app) as client:
        response=client.get('/v5/status')
        assert response.status_code==200
        data=response.json()
        assert data['status']=='WHITE_LABEL_V5_NOT_ACTIVATED'
        assert data['canonical_database']=='EmpireDB_PostgreSQL'
        assert data['execution_authority']=='none'
        assert data['public_partner_api_enabled'] is False


@pytest.mark.parametrize('endpoint',['/v5/router/dispatch','/v5/admin/tenants'])
def test_unmounted_prototype_refuses_public_mutations_for_forged_headers(endpoint):
    app=FastAPI()
    app.include_router(create_v5_held_api_router())
    with TestClient(app) as client:
        response=client.post(endpoint,json={'tenant_id':'00000000-0000-0000-0000-000000000101',
            'active':True,'payment_authority':True},headers={
            'X-Tenant-ID':'00000000-0000-0000-0000-000000000101',
            'Authorization':'Bearer fake-token','Host':'portal.partner.example.org'})
        assert response.status_code==403
        assert 'owner_approval_required' in response.json()['detail']
        assert client.get(endpoint).status_code==405


def test_held_websocket_refuses_handshake_before_accept():
    app=FastAPI()
    app.include_router(create_v5_held_api_router())
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect('/v5/metrics/stream',headers={
                'X-Tenant-ID':'00000000-0000-0000-0000-000000000101'}) as stream:
                stream.receive_json()
        assert caught.value.code==1008


def test_063_schema_is_pending_only_with_no_grants_or_runnable_gateway():
    source=MIGRATION.read_text()
    for term in ('FORCE ROW LEVEL SECURITY','empiredb_migrator',
        'V5_063_WRONG_DATABASE','V5_063_EXISTING_REGISTRY_REQUIRES_REVIEW',
        'ownership_state','certificate_state','dns_state','activation_state',
        "CHECK (activation_state='HELD')",'UNIQUE',
    ):
        if term=='UNIQUE':
            assert 'hostname text PRIMARY KEY' in source
        else:
            assert term in source
    assert not any(line.strip().upper().startswith('GRANT EXECUTE')
                   for line in source.splitlines())
    assert 'CREATE ROLE' not in source
    assert 'CREATE FUNCTION' not in source


def test_v5_registry_fixture_refuses_production_port_without_connection():
    env=dict(os.environ)
    env.update(PGPORT='5432',PGHOST='localhost',PGDATABASE='postgres')
    result=subprocess.run(['bash',str(FIXTURE)],cwd=ROOT,env=env,
                          capture_output=True,text=True,timeout=5)
    assert result.returncode!=0
    assert 'V5_063_FIXTURE_COMPLETE' not in result.stdout


@pytest.mark.skipif(shutil.which('pg_virtualenv') is None,reason='no disposable PostgreSQL')
def test_063_real_pg_domain_uniqueness_routing_state_and_rls():
    process=subprocess.run(['pg_virtualenv','-t','bash',str(FIXTURE)],cwd=ROOT,
        capture_output=True,text=True,timeout=90)
    assert process.returncode==0,process.stdout[-5000:]+process.stderr[-3000:]
    for marker in ('V5_063_ISOLATED_TENANT_DOMAIN_UNIQUENESS_FORCE_RLS=PASS',
      'V5_063_UNTRUSTED_DOMAIN_CANNOT_ACTIVATE=PASS',
      'V5_063_FIXTURE_COMPLETE production_empiredb_writes=false live_domain_activated=false',
      'Dropping cluster 18/regress'):
        assert marker in process.stdout+process.stderr
