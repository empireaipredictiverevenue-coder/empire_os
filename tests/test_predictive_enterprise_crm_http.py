"""Actual original report/CRM adapters, isolated DB fixtures, no production writes."""
from datetime import datetime, timedelta, timezone
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.predictive_revenue_crm_diagnostic_api import (
    PREFIX, create_authenticated_predictive_diagnostic_router,
)
from empire_os.revenue_crm_api import build_authenticated_revenue_crm_resolver
from empire_os.revenue_crm_transport import PROSPECT_COLUMNS, PROSPECT_LIST_SQL, ROLE
from test_revenue_crm_transport import FakeCursor, FakeConnection

TENANT = '657b37ba-724a-44d8-a9d1-849a0af9065d'
OTHER = 'e5a7cd39-be6c-4a3b-86ab-ec54b379e56d'
PROSPECT = '37ae341d-2b2e-431f-bd3e-74876ca42ddb'
COLUMNS = tuple(x.strip() for x in PROSPECT_COLUMNS.split(','))


def fixture_client(root, *, authenticated=True, bound=TENANT, rows=None, role_failure=False):
    record = dict.fromkeys(COLUMNS)
    record.update(tenant_id=TENANT, prospect_id=PROSPECT, business_name='PRIVATE CUSTOMER FIXTURE', price_cents=10000)
    records = [record] if rows is None else rows
    cursor = FakeCursor([tuple(r.get(k) for k in COLUMNS) for r in records], COLUMNS,
        bound_tenant=bound)
    if role_failure:
        execute=cursor.execute
        def deny_role(sql, params=None):
            if sql == 'SET LOCAL ROLE ' + ROLE:
                raise RuntimeError('read role unavailable')
            return execute(sql,params)
        cursor.execute=deny_role
    reads = []
    def connect(dsn):
        reads.append(True)
        return FakeConnection(cursor)
    resolver = build_authenticated_revenue_crm_resolver(
        lambda request: TENANT if authenticated else None,
        {TENANT:'isolated-test-dsn'},connect_factory=connect)
    app = FastAPI()
    app.include_router(create_authenticated_predictive_diagnostic_router(resolver,repo_root=root))
    return TestClient(app), cursor, reads


@pytest.mark.parametrize('suffix,content', [('', 'application/json'),('/preview','text/html'),('/markdown','text/plain')])
def test_original_signed_scope_guarded_report_and_all_renderers(tmp_path, suffix, content):
    # pytest supplies tmp_path; no customer/source fixture is written to production.
    client,cursor,reads = fixture_client(tmp_path)
    response = client.get(PREFIX+suffix)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith(content)
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert len(reads) == 1
    assert 'PRIVATE CUSTOMER FIXTURE' not in response.text
    assert TENANT not in response.text and PROSPECT not in response.text
    assert cursor.calls[0][0] == 'SET TRANSACTION READ ONLY'
    assert any(sql==PROSPECT_LIST_SQL for sql,_ in cursor.calls)
    assert all(not sql.startswith(('INSERT','UPDATE','DELETE')) for sql,_ in cursor.calls)
    if not suffix:
        data=response.json()
        assert data['report_disposition'] == 'INTERNAL_DRAFT_NOT_CLIENT_DELIVERABLE'
        assert data['release_gate']['customer_delivery_enabled'] is False
        source=data['existing_crm_observation_review']
        assert source['bounded_observations']['observed_records'] == 1
        assert source['tenant_bound_existing_repository_read'] is True
        assert data['completeness']['findings_verified'] == 0


def test_unauthenticated_forged_tenant_headers_never_read_source(tmp_path):
    client,_,reads=fixture_client(tmp_path,authenticated=False)
    for suffix in ('','/preview','/markdown'):
        r=client.get(PREFIX+suffix,headers={'X-Tenant-ID':TENANT,'X-Role':'owner'})
        assert r.status_code == 401
    assert reads == []


def test_diagnostic_shell_has_no_private_data_and_uses_in_memory_session():
    client,_,reads=fixture_client('/unused',authenticated=False)
    page=client.get(PREFIX+'/app')
    script=client.get(PREFIX+'/app.js')
    assert page.status_code == 200 and script.status_code == 200
    assert page.headers['cache-control'] == 'no-store'
    assert page.headers['x-content-type-options'] == 'nosniff'
    assert "default-src 'none'" in page.headers['content-security-policy']
    assert TENANT not in script.text and PROSPECT not in script.text
    assert 'localStorage' not in script.text and 'sessionStorage' not in script.text
    assert "Authorization':'Bearer '+token" in script.text
    assert reads == []


@pytest.mark.parametrize('query',['?tenant_id='+OTHER,'?limit=0','?limit=501','?limit=abc'])
def test_untrusted_scope_and_invalid_bounds_never_read_source(tmp_path,query):
    client,_,reads=fixture_client(tmp_path)
    assert client.get(PREFIX+query).status_code == 422
    assert reads == []


@pytest.mark.parametrize('kind',['tenant','role_rejected','future','duplicate'])
def test_source_security_failures_never_become_reports(tmp_path,kind):
    kwargs={}
    if kind=='tenant':kwargs['bound']=OTHER
    elif kind=='role_rejected':kwargs['role_failure']=True
    else:
        row=dict.fromkeys(COLUMNS);row.update(tenant_id=TENANT,prospect_id=PROSPECT)
        if kind=='future':row['conversation_updated_at']=datetime.now(timezone.utc)+timedelta(days=1)
        kwargs['rows']=[row,row] if kind=='duplicate' else [row]
    client,_,_=fixture_client(tmp_path,**kwargs)
    r=client.get(PREFIX)
    assert r.status_code == 503
    assert TENANT not in r.text and OTHER not in r.text
    assert r.json()['detail']=='authenticated_diagnostic_source_unavailable'


def test_empty_and_truncated_sources_remain_explicit_holds(tmp_path):
    client,_,_=fixture_client(tmp_path,rows=[])
    report=client.get(PREFIX).json()
    assert report['existing_crm_observation_review']['status']=='CRM_SOURCE_EMPTY_UNKNOWN_COVERAGE_HOLD'
    client,_,_=fixture_client(tmp_path)
    report=client.get(PREFIX+'?limit=1').json()
    assert report['existing_crm_observation_review']['status']=='CRM_SOURCE_SNAPSHOT_BOUND_REACHED_HOLD'
    assert report['release_gate']['customer_delivery_enabled'] is False


def test_existing_report_release_guard_cannot_be_bypassed(tmp_path,monkeypatch):
    import empire_os.predictive_revenue_crm_diagnostic_api as api
    original=api.build_authenticated_crm_diagnostic_report
    def forged(*args,**kwargs):
        p=original(*args,**kwargs)
        p['release_gate']['customer_delivery_enabled']=True
        return p
    monkeypatch.setattr(api,'build_authenticated_crm_diagnostic_report',forged)
    client,_,_=fixture_client(tmp_path)
    assert client.get(PREFIX).status_code == 409
