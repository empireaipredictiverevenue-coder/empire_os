"""Adversarial contract tests; no production DB, services or network required."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from starlette.requests import Request

from empire_os.owned_campaign_content import (
    PRIVACY, build_asset, prepare_marketing, public_owner_scope, render_asset, review_asset,
)
from empire_os.owned_campaign_intake import accept, validate_enquiry, validate_event
from empire_os.owned_campaign_preflight import digest, inspect_campaigns, _landing
from empire_os.owned_campaign_release import load_release, released_html, released_paths, SCRIPT, RELEASE
from empire_os.owned_campaign_http import IntakeLimiter, handle_intake
from empire_os.data_backends.owned_campaign_repository import OwnedCampaignRepository

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def marketing():
    return json.loads((ROOT / 'runtime/astra/department_cycle_latest.json').read_text())['marketing_growth']


@pytest.fixture
def prepared(marketing):
    return prepare_marketing(marketing, ROOT)


def enquiry(m):
    c = m['campaigns'][0]
    return {'campaign_id': c['campaign_id'], 'asset_id': c['campaign_id'] + ':landing',
            'reply_email': ' READER@EXAMPLE.COM ', 'research_question': 'Which source needs further review?'}


def event(m):
    return {k: v for k, v in enquiry(m).items() if k in ('campaign_id', 'asset_id')} | {
        'event_id': str(uuid4()), 'event_type': 'campaign_page_view', 'source': 'owned_site',
        'channel': 'organic', 'occurred_at': datetime.now(timezone.utc).isoformat()}


def infrastructure():
    from empire_os.owned_campaign_preflight import INFRASTRUCTURE_GATES
    return {k: {'status': 'PASS', 'evidence_refs': ['test:verified']} for k in INFRASTRUCTURE_GATES}


def test_public_owner_has_no_customer_authority(marketing):
    c = marketing['campaigns'][0]
    scope = public_owner_scope(c)
    assert scope['status'] == 'PUBLIC_OWNER_SCOPE_RESOLVED'
    assert scope['ownership_scope'] == 'empire_owned'
    assert scope['account_id'] is scope['tenant_id'] is scope['customer_tenant'] is None
    assert not scope['customer_access_authorized'] and not scope['customer_tenant_resolved']
    for key in ('tenant_id', 'account_id'):
        changed = deepcopy(c); changed[key] = str(uuid4())
        assert public_owner_scope(changed)['status'] == 'UNRESOLVED'
    c['tenant_scope']['customer_access_authorized'] = True
    assert public_owner_scope(c)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('missing', ['campaign_id', 'asset_id', 'reply_email', 'research_question'])
def test_required_enquiry_fields(marketing, missing):
    p = enquiry(marketing); p.pop(missing)
    with pytest.raises(ValueError): validate_enquiry(p, marketing)


@pytest.mark.parametrize('field,value', [
    ('campaign_id', 'campaign_' + '0' * 24), ('asset_id', 'other'),
    ('reply_email', 'no-at-sign'), ('reply_email', 'a\n@example.com'),
    ('research_question', 'short'), ('research_question', 'x' * 4001),
    ('company', 'x' * 201), ('role', 'x' * 101), ('research_question', None),
])
def test_enquiry_validation(marketing, field, value):
    p = enquiry(marketing); p[field] = value
    with pytest.raises(ValueError): validate_enquiry(p, marketing)


@pytest.mark.parametrize('field', ['prospect_id','conversation_id','terms_id','payment_id','revenue_id',
                                  'marketing_consent','outbound_authorized','automatic_followup','qualified_buyer'])
def test_browser_authority_rejected(marketing, field):
    for validator, p in ((validate_enquiry, enquiry(marketing)), (validate_event, event(marketing))):
        p[field] = 'true'
        with pytest.raises(ValueError): validator(p, marketing)


@pytest.mark.parametrize('field,value', [('event_type','purchase'), ('asset_id','wrong'),
    ('source','paid'), ('channel','email'), ('event_id','not-uuid'), ('session_id','email@example.com'),
    ('occurred_at','2020-01-01T00:00:00Z'), ('occurred_at','2026-09-30'), ('occurred_at','bad')])
def test_event_validation(marketing, field, value):
    p = event(marketing); p[field] = value
    with pytest.raises(ValueError): validate_event(p, marketing)


def test_events_are_observations_and_binding_is_required(marketing):
    p = event(marketing)
    for name in ('campaign_page_view','campaign_cta_click','campaign_enquiry_started','campaign_enquiry_submitted'):
        p['event_type'] = name
        assert validate_event(p, marketing)['event_type'] == name
    p['campaign_id'] = marketing['campaigns'][1]['campaign_id']
    with pytest.raises(ValueError): validate_event(p, marketing)


class FakeRepository:
    """Deterministic DB-contract double, deliberately only in tests."""
    def __init__(self): self.events = {}; self.enquiries = {}
    def event(self, p):
        if p['event_id'] in self.events and self.events[p['event_id']] != p:
            raise ValueError('conflicting event replay')
        self.events[p['event_id']] = p
        return p['event_id']
    def enquiry(self, p):
        key = digest(p)
        if key not in self.enquiries: self.enquiries[key] = (str(uuid4()), p)
        return self.enquiries[key][0]


def test_dedupe_and_no_commercial_authority(marketing):
    store = FakeRepository(); p = enquiry(marketing)
    first = accept('enquiry', p, marketing, store)
    assert first == accept('enquiry', p, marketing, store)
    assert len(store.enquiries) == 1 and len(store.events) == 0
    saved = next(iter(store.enquiries.values()))[1]
    assert saved['reply_email'] == 'reader@example.com'
    assert set(saved) == {'campaign_id','asset_id','reply_email','research_question'}
    assert set(first) == {'accepted','receipt_id','campaign_id'}
    ev = event(marketing)
    assert accept('event', ev, marketing, store) == accept('event', ev, marketing, store)
    assert len(store.events) == 1
    ev['event_type'] = 'campaign_cta_click'
    with pytest.raises(ValueError): accept('event', ev, marketing, store)


def test_managed_service_form_does_not_require_company_or_grant_terms(prepared):
    c = next(c for c in prepared['campaigns'] if c['product_code'] == 'managed_service')
    m = {'campaigns': [c]}
    assert validate_enquiry(enquiry(m), m)['reply_email'] == 'reader@example.com'
    a = _landing(c)
    assert a['cta'] == 'Discuss product fit'
    assert 'verified catalog' in render_asset(a)
    assert 'payment' not in validate_enquiry(enquiry(m), m)


def test_unique_substantive_assets_exact_review_and_no_state_mutation(marketing, prepared):
    assert prepared == prepare_marketing(marketing, ROOT)
    assert prepared['campaigns'][0]['stage_history'] == marketing['campaigns'][0]['stage_history']
    assets = [_landing(c) for c in prepared['campaigns']]
    assert len({a['seo_title'] for a in assets}) == len(assets) == 5
    assert len({a['meta_description'] for a in assets}) == 5
    assert len({digest(a['sections']) for a in assets}) == 5
    for c, a in zip(prepared['campaigns'], assets):
        review = c['owned_publication_review']; html = render_asset(a)
        assert review['status'] == 'PASS'
        assert review['asset_sha256'] == hashlib.sha256(html.encode()).hexdigest()
        assert len(' '.join(s['body'] for s in a['sections']).split()) >= 300
        assert PRIVACY in html and 'Limitations' in html and 'canonical' in html
        assert 'name="phone"' not in html and 'name="budget"' not in html
        assert review['claim_inventory'] == a['claims']
        assert review['claim_verification_result']['market_claims_verified'] is False
        if c['product_code'] is None:
            assert a['cta'] == 'Enquire about the research' and not a['product_refs']
        changed = deepcopy(a); changed['sections'][0]['body'] = 'Guaranteed demand'
        assert review_asset(c, changed, ROOT)['status'] == 'BLOCKED'
        c['assets'][c['assets'].index(a)] = changed
    report = inspect_campaigns(prepared, infrastructure())
    assert report['campaigns_blocked'] == 5


def test_preflight_independent_and_schema_held(prepared):
    infra = infrastructure()
    assert inspect_campaigns(prepared, infra)['campaigns_preflight_passed'] == 5
    infra['canonical_intake_schema']['status'] = 'HELD_FOR_FOUNDER_DB_APPROVAL'
    r = inspect_campaigns(prepared, infra)
    assert r['campaigns_preflight_passed'] == 0 and r['campaigns_blocked'] == 5
    assert all(c['blockers'] == ['canonical_intake_schema'] for c in r['campaigns'])
    assert not r['publication_performed'] and not r['campaign_state_mutated']


def test_release_absent_and_sitemap_excludes_blocked(tmp_path, marketing):
    from empire_os.public_gateway import _sitemap_xml, research_page
    assert load_release(tmp_path) is None and released_paths(tmp_path) == []
    for c in marketing['campaigns']:
        assert released_html(c['campaign_id'], tmp_path) is None
        assert research_page(c['campaign_id']).status_code == 404
        assert c['campaign_id'] not in _sitemap_xml(tmp_path, tmp_path)


def test_release_requires_exact_assets_and_current_campaigns(tmp_path, marketing, prepared):
    for rel in ('runtime/astra/department_cycle_latest.json', 'runtime/opportunity_radar/latest.json',
                'runtime/commercial_catalog/latest.json', str(SCRIPT)):
        target = tmp_path / rel; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / rel).read_bytes())
    r = {'deployment_verified': True, 'deployment_evidence_refs': ['test:live'],
         'canonical_campaigns_sha256': digest(marketing['campaigns']),
         'infrastructure_review': infrastructure(),
         'script_sha256': hashlib.sha256((tmp_path / SCRIPT).read_bytes()).hexdigest(),
         'asset_digests': {c['campaign_id']: c['owned_publication_review']['asset_sha256'] for c in prepared['campaigns']}}
    path = tmp_path / RELEASE
    path.write_text(json.dumps(r))
    assert len(load_release(tmp_path)['campaigns']) == 5
    r['asset_digests'][prepared['campaigns'][0]['campaign_id']] = 'bad'
    path.write_text(json.dumps(r)); assert load_release(tmp_path) is None
    r['deployment_verified'] = False
    path.write_text(json.dumps(r)); assert load_release(tmp_path) is None


def test_rate_limiter_bounded_without_raw_ip():
    limiter = IntakeLimiter()
    assert all(limiter.allow('test-peer', 'enquiry', now=1) for _ in range(5))
    assert not limiter.allow('test-peer', 'enquiry', now=1)
    assert limiter.allow('test-peer', 'enquiry', now=62)
    assert all(isinstance(key[0], bytes) for key in limiter.buckets)


def request(payload, origin='https://empire-ai.co.uk', raw=None):
    data = raw if raw is not None else json.dumps(payload).encode()
    async def receive(): return {'type': 'http.request', 'body': data, 'more_body': False}
    return Request({'type':'http', 'method':'POST', 'path':'/api/research/enquiry',
                    'headers': [(b'origin', origin.encode()), (b'content-type',b'application/json')],
                    'client': ('test-peer', 1)}, receive)


def test_http_origin_body_limits_and_unpublished_fail_closed(monkeypatch):
    import empire_os.owned_campaign_http as h
    monkeypatch.setattr(h, 'LIMITER', IntakeLimiter())
    # Avoid environment TestClient threadpool hang; dependency stays in this event loop.
    async def direct(fn, *args): return fn(*args)
    monkeypatch.setattr(h, 'run_in_threadpool', direct)
    monkeypatch.setattr(h, 'load_release', lambda: None)
    assert asyncio.run(handle_intake(request({}, origin='https://evil.invalid'), 'enquiry')).status_code == 403
    assert asyncio.run(handle_intake(request({}, raw=b'x'*12001), 'enquiry')).status_code == 413
    assert asyncio.run(handle_intake(request({}), 'enquiry')).status_code == 503


def test_http_safe_receipt_and_failure_redaction(monkeypatch, prepared):
    import empire_os.owned_campaign_http as h
    monkeypatch.setattr(h, 'LIMITER', IntakeLimiter())
    async def direct(fn, *args): return fn(*args)
    monkeypatch.setattr(h, 'run_in_threadpool', direct)
    monkeypatch.setattr(h, 'load_release', lambda: prepared)
    monkeypatch.setattr(OwnedCampaignRepository, 'from_environment', lambda: FakeRepository())
    response = asyncio.run(handle_intake(request(enquiry(prepared)), 'enquiry'))
    assert response.status_code == 202 and 'reply_email' not in response.body.decode()
    p = enquiry(prepared); p['marketing_consent'] = 'true'
    assert asyncio.run(handle_intake(request(p), 'enquiry')).status_code == 422
    def fail(): raise RuntimeError('SECRET-MUST-NOT-LEAK')
    monkeypatch.setattr(OwnedCampaignRepository, 'from_environment', fail)
    response = asyncio.run(handle_intake(request(enquiry(prepared)), 'enquiry'))
    assert response.status_code == 503 and b'SECRET' not in response.body


def test_transport_parameterization_commit_rollback_role():
    class Connection:
        def __init__(self): self.calls = []; self.committed = self.rolled_back = self.closed = False
        def execute(self, sql, params=()): self.calls.append((sql, params)); return self
        def fetchone(self): return ('empire_owned_campaign_ingest' if self.calls[-1][0] == 'SELECT current_user' else 'receipt',)
        def commit(self): self.committed = True
        def rollback(self): self.rolled_back = True
        def close(self): self.closed = True
    class Connector:
        def __init__(self): self.conn = Connection()
        def _open_connection(self): return self.conn
    connector = Connector(); repo = OwnedCampaignRepository(connector)
    payload = {'research_question': "x'); DROP TABLE prospects; --"}
    assert repo.enquiry(payload) == 'receipt'
    assert connector.conn.committed and connector.conn.closed
    sql, params = connector.conn.calls[-1]
    assert 'DROP TABLE' not in sql and json.loads(params[0]) == payload
    connector = Connector(); connector.conn.fetchone = lambda: ('empiredb_app',)
    with pytest.raises(RuntimeError): OwnedCampaignRepository(connector).event({})
    assert connector.conn.rolled_back and connector.conn.closed and not connector.conn.committed


def test_no_generic_database_fallback(monkeypatch):
    monkeypatch.setenv('EMPIRE_DATA_BACKEND','empiredb')
    monkeypatch.setenv('EMPIREDB_DSN','unused-generic')
    monkeypatch.delenv('EMPIRE_OWNED_CAMPAIGN_DSN', raising=False)
    with pytest.raises(ValueError): OwnedCampaignRepository.from_environment()


def test_held_sql_restricts_authority_and_atomic_dedupe():
    sql = (ROOT / 'migrations/empiredb/025_owned_campaign_intake.sql').read_text()
    assert 'HELD_FOR_FOUNDER_DB_APPROVAL' in sql
    assert 'ON CONFLICT (event_id) DO NOTHING' in sql
    assert 'conflicting event replay' in sql
    assert 'ON CONFLICT (dedupe_key) DO NOTHING' in sql
    assert "CHECK (NOT marketing_consent)" in sql and 'CHECK (NOT outbound_authorized)' in sql
    assert 'CHECK (NOT automatic_followup)' in sql
    assert 'enquiry_receipt uuid REFERENCES public.owned_campaign_enquiries(receipt_id)' in sql
    assert 'GRANT EXECUTE' in sql and 'TO empiredb_app' not in sql
    assert 'INSERT INTO public.prospects' not in sql and 'INSERT INTO public.outbound' not in sql


def test_locked_formulas_and_migration():
    for path, expected in {
        'empire_os/predictive_revenue_formula.py': 'ed258882dd71a4292fea670807f5e5a451cdc4482f2da2204d5f6a2293e5bc2e',
        'empire_os/predictive_cloud_formula.py': 'ccbb9b49c31bd4aca57e9d5312de034d20624f3db0344ab0cffed8ed1b99c406',
        'migrations/empiredb/018_tenant_context_foundation.sql': 'e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21',
    }.items(): assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected



def test_source_binding_refresh_is_identity_safe(marketing):
    from copy import deepcopy
    import hashlib
    import json
    from empire_os.owned_campaign_content import refresh_source_bindings

    stale = deepcopy(marketing)
    refreshed = refresh_source_bindings(stale, ROOT)
    assert stale == marketing

    catalog = json.loads((ROOT / 'runtime/commercial_catalog/latest.json').read_text())
    current_hash = hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()
    expected = 'runtime/commercial_catalog/latest.json#sha256=' + current_hash
    managed = [c for c in refreshed['campaigns'] if c.get('product_code') == 'managed_service']
    assert managed
    assert all(expected in c['product_evidence_refs'] for c in managed)
    assert all(expected in c['opportunity_evidence_refs'] for c in managed)


def test_source_binding_refresh_rejects_product_identity_change(marketing, tmp_path):
    import json
    import pytest
    from empire_os.owned_campaign_content import refresh_source_bindings

    radar = json.loads((ROOT / 'runtime/opportunity_radar/latest.json').read_text())
    catalog = json.loads((ROOT / 'runtime/commercial_catalog/latest.json').read_text())
    catalog['products'] = [
        p for p in catalog['products']
        if p.get('product_code') != 'managed_service'
    ]
    (tmp_path / 'runtime/opportunity_radar').mkdir(parents=True)
    (tmp_path / 'runtime/commercial_catalog').mkdir(parents=True)
    (tmp_path / 'runtime/opportunity_radar/latest.json').write_text(json.dumps(radar))
    (tmp_path / 'runtime/commercial_catalog/latest.json').write_text(json.dumps(catalog))

    with pytest.raises(ValueError, match='verified product identity changed'):
        refresh_source_bindings(marketing, tmp_path)
