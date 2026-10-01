import copy
import json
import pytest
from empire_os import marketing_agency as agency
from empire_os.departments import default_departments

NOW = '2026-09-30T12:00:00+00:00'


def inputs():
    return {
        'radar': {'generated_at': NOW, 'candidates': [{
            'opportunity_key': 'observed:test', 'evidence_refs': ['canonical:test'],
            'products': ['test_product'], 'niche': 'test audience', 'metro': 'test geography',
        }]},
        'catalog': {'generated_at': NOW, 'products': [{
            'product_code': 'test_product', 'product_id': 'test-id',
            'product_name': 'Test product', 'binding_terms_ready': False,
        }]},
    }


def build(data=None):
    return agency.build_marketing_agency(data or inputs(), generated_at=NOW)


def test_canonical_department_roles_and_determinism():
    departments = default_departments()
    marketing = [d for d in departments if d.key == 'marketing_growth']
    assert len(marketing) == 1
    assert not any(d.key in {'marketing_agency', 'ai_marketing_agency', 'marketing'} for d in departments)
    assert set(agency.ROLES) <= set(marketing[0].agent_roles)
    source = inputs()
    before = copy.deepcopy(source)
    assert build(source) == build(source)
    assert source == before


def test_specialist_reuse_and_director(monkeypatch):
    calls = []
    for module, name in [(agency.copywriter, 'build_copy'),
                         (agency.traffic_specialist, 'review_organic_traffic'),
                         (agency.media_content_pipeline, 'build_content_pipeline')]:
        original = getattr(module, name)
        def wrapper(*args, _original=original, _name=name, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, wrapper)
    result = build()
    assert set(calls) == {'build_copy', 'review_organic_traffic', 'build_content_pipeline'}
    job = result['jobs'][0]
    assert all(a['coordinator'] == 'marketing_director' for a in job['specialist_assignments'])
    assert 'specialist_review' in job['conversion_plan']
    assert 'search_intelligence' in result['roles']['market_intelligence_strategist']
    assert 'search_intelligence.attribution' in result['roles']['attribution_agent']


def test_unknowns_evidence_and_authority():
    result = build()
    job = result['jobs'][0]
    assert result['agency_job_count'] == 1
    assert result['zero_cash_action_count'] > 0
    assert not any(result['authority'].values())
    assert result['paid_acquisition_plan']['budget'] is None
    assert result['paid_acquisition_authorized'] is False
    assert job['canonical_prediction']['status'] == 'UNAVAILABLE'
    assert job['canonical_prediction']['unknown_is_zero'] is False
    assert job['next_best_action']['economics']['status'] == 'UNAVAILABLE'
    assert job['attribution_plan']['revenue_linkage_status'] == 'UNAVAILABLE'
    assert job['lifecycle_plan']['send_authorized'] is False
    assert job['quality_review']['publish_ready'] is False
    assert 'canonical:test' in job['source_evidence_refs']
    assert job['why_now']['current_urgency'] is None
    assert job['conversion_plan']['campaign_conversion_rate'] is None
    assert job['tenant_id'] is None
    encoded = json.dumps(result)
    for forbidden in ['marketing_score', 'agency_revenue_score', 'traffic_revenue_score', 'conversion_revenue_score']:
        assert forbidden not in encoded


@pytest.mark.parametrize('case', ['no_evidence', 'duplicate_identity', 'tenant', 'stale', 'future', 'ambiguous_product'])
def test_fail_closed_intake(case):
    data = inputs()
    row = data['radar']['candidates'][0]
    if case == 'missing_product': row['products'] = []
    if case == 'no_evidence': row['evidence_refs'] = []
    if case == 'duplicate_identity': data['radar']['candidates'].append(copy.deepcopy(row))
    if case == 'tenant': row['tenant_id'] = 'tenant-not-authorized'
    if case == 'stale': data['radar']['generated_at'] = '2020-01-01T00:00:00+00:00'
    if case == 'future': data['radar']['generated_at'] = '2030-01-01T00:00:00+00:00'
    if case == 'ambiguous_product': data['catalog']['products'] *= 2
    assert build(data)['agency_job_count'] == 0


def test_formula_only_uses_evidenced_inputs():
    from empire_os.predictive_revenue_formula import CORE_FACTORS, predictive_revenue_formula
    data = inputs()
    row = data['radar']['candidates'][0]
    values = dict.fromkeys(CORE_FACTORS, .5)
    values['ltv_cents'] = 1000
    row['predictive_revenue_inputs'] = values
    assert build(data)['predictive_revenue_available_count'] == 0
    row['predictive_revenue_evidence_refs'] = {k: ['canonical:factor:' + k] for k in values}
    assert build(data)['jobs'][0]['canonical_prediction'] == predictive_revenue_formula(values)


def test_record_preserves_existing_snapshot_and_never_runs_queue(tmp_path, monkeypatch):
    path = tmp_path / agency.OUTPUT
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'worker': {'untouched': True}, 'concurrent_field': 42}))
    monkeypatch.setattr(agency, 'observe_marketing_agency', lambda root: build())
    agency.record_marketing_agency(tmp_path)
    result = json.loads(path.read_text())
    assert result['worker'] == {'untouched': True}
    assert result['concurrent_field'] == 42
    assert result['marketing_growth']['agency_job_count'] == 1


def test_record_refuses_concurrent_change(tmp_path, monkeypatch):
    path = tmp_path / agency.OUTPUT
    path.parent.mkdir(parents=True)
    path.write_text('{}')
    def observe(root):
        path.write_text('{"concurrent": true}')
        return build()
    monkeypatch.setattr(agency, 'observe_marketing_agency', observe)
    with pytest.raises(RuntimeError, match='concurrently'):
        agency.record_marketing_agency(tmp_path)
    assert json.loads(path.read_text()) == {'concurrent': True}


def test_empty_and_bounded():
    assert agency.build_marketing_agency({}, generated_at=NOW)['agency_job_count'] == 0
    with pytest.raises(ValueError): agency.build_marketing_agency({}, generated_at=NOW, limit=6)


def test_action_economics_requires_per_field_evidence():
    data = inputs()
    row = data['radar']['candidates'][0]
    row['action_economics'] = {'probability_action_changes_outcome': .5,
        'incremental_revenue_if_changed_cents': 100, 'action_cost_cents': 2, 'confidence': .8}
    assert build(data)['jobs'][0]['next_best_action']['economics']['status'] == 'UNAVAILABLE'
    row['action_economics_evidence_refs'] = {k: ['canonical:' + k] for k in row['action_economics']}
    economics = build(data)['jobs'][0]['next_best_action']['economics']
    assert economics['recommended_action']['expected_incremental_value_cents'] == 38


def test_attribution_requires_complete_matching_chain():
    data = inputs()
    row = data['radar']['candidates'][0]
    links = {stage: 'fixture:' + stage for stage in agency.ATTRIBUTION_CHAIN}
    row['attribution_evidence'] = {
        'opportunity_key': row['opportunity_key'], 'product_id': 'test-id',
        'evidence_refs': ['canonical:event'], 'site_id': 'fixture:site', 'links': links,
        'commercial_event': {'event_type': 'revenue_recognized', 'actual_revenue': True,
            'id': links['recognized_revenue'], 'fulfilment_order_id': links['fulfilment'],
            'occurred_at': NOW, 'amount_cents': 100}}
    assert build(data)['jobs'][0]['attribution_plan']['revenue_linkage_status'] == 'AVAILABLE'
    del links['payment']
    assert build(data)['jobs'][0]['attribution_plan']['revenue_linkage_status'] == 'UNAVAILABLE'


def test_top_five_and_stable_priority():
    data = inputs()
    original = data['radar']['candidates'][0]
    data['radar']['candidates'] = [{**original, 'opportunity_key': f'fixture:{i}'} for i in range(9)]
    result = build(data)
    assert result['agency_job_count'] == 5
    assert len({j['agency_job_id'] for j in result['jobs']}) == 5
    assert [j['opportunity_key'] for j in result['jobs']] == [f'fixture:{i}' for i in range(5)]


def test_unmatched_product_is_research_not_invented_product():
    data = inputs()
    data['radar']['candidates'][0]['products'] = []
    job = build(data)['campaigns'][0]
    assert job['product_id'] is None and job['product_code'] is None
    assert job['campaign_objective'] == 'research_enquiry'
    assert job['conversion_plan']['primary_cta'] == 'Enquire about the research'
    assert job['current_stage'] == 'READY_FOR_OWNED_ACTIVATION'


def test_campaign_lifecycle_assets_and_unknown_baseline():
    result = build()
    job = result['campaigns'][0]
    assert job['current_stage'] == 'READY_FOR_OWNED_ACTIVATION'
    assert [h['stage'] for h in job['stage_history']] == list(agency.CAMPAIGN_STAGES[:8])
    assert all('canonical:test' in h['evidence_refs'] for h in job['stage_history'])
    assert job['canonical_prediction']['status'] == 'UNAVAILABLE'
    assert all(job['readiness_gates'].values())
    assert len(job['assets']) == 4
    assert all(a['publication_status'] == 'NOT_PUBLISHED' for a in job['assets'])
    assert len({a['asset_id'] for a in job['assets']}) == 4
    assert job['assets'][0]['schema_version'] == 'empire.media.canonical_content.v1'
    assert job['assets'][0]['copy']['channel'] == 'campaign_research'
    assert job['measurement_plan']['visitors'] is None
    assert job['measurement_plan']['conversion_rate'] is None
    assert job['total_campaign_cost_cents'] is None
    assert job['paid_media_spend_cents'] == 0
    assert job['conversion_plan']['experiment_winner'] is None
    assert job['attribution_plan']['campaign_id'] == job['campaign_id']
    assert job['attribution_plan']['event_contract']['dedupe_key'] == 'event_id'
    assert len(job['evidence_collection_plan']) == 11
    assert all(a['status'] == 'MISSING' for a in job['evidence_collection_plan'])
    assert set(result['agency_roles']) <= set(next(d for d in default_departments() if d.key == 'marketing_growth').agent_roles)


@pytest.mark.parametrize('target', ['ACTIVE', 'MEASURING', 'OPTIMIZING', 'PAUSED', 'CLOSED'])
def test_activation_blocked(target):
    job = build()['campaigns'][0]
    with pytest.raises(ValueError, match='founder'):
        agency.advance_campaign(job, target)
    assert not any(build()['authority'].values())


def test_missing_asset_blocks_readiness():
    data = inputs()
    data['radar']['candidates'][0]['metro'] = None
    job = build(data)['campaigns'][0]
    assert job['current_stage'] == 'QUALITY_REVIEW'
    with pytest.raises(ValueError):
        agency.advance_campaign(job, 'READY_FOR_OWNED_ACTIVATION')


def test_canonical_order_includes_unmatched_top_five():
    data = inputs()
    template = data['radar']['candidates'][0]
    keys = ['competitor_coverage:roofing:denver', 'market:class action:atlanta',
            'market:general_contractor:nyc', 'market:hvac:dallas', 'market:hvac:denver']
    data['radar']['candidates'] = [{**template, 'opportunity_key': key,
        'products': ['test_product'] if i % 2 else []} for i, key in enumerate(keys)]
    result = build(data)
    assert [j['opportunity_key'] for j in result['campaigns']] == keys
    assert result['zero_cash_campaign_count'] == 5
    assert result['campaign_state_counts'] == {'READY_FOR_OWNED_ACTIVATION': 5}


def test_stale_conversion_cannot_be_campaign_evidence():
    data = inputs()
    data['conversion'] = {'generated_at': '2020-01-01T00:00:00Z',
                          'conversion_rate': .99, 'winner': True}
    job = build(data)['campaigns'][0]
    assert job['measurement_plan']['performance_evidence'] == []
    assert job['conversion_plan']['campaign_conversion_rate'] is None
    assert 'conversion:stale' in job['conversion_plan']['specialist_review']['blockers']


def test_formula_hashes_locked():
    from pathlib import Path
    import hashlib
    for name, expected in [
        ('predictive_revenue_formula', 'ed258882dd71a4292fea670807f5e5a451cdc4482f2da2204d5f6a2293e5bc2e'),
        ('predictive_cloud_formula', 'ccbb9b49c31bd4aca57e9d5312de034d20624f3db0344ab0cffed8ed1b99c406')]:
        assert hashlib.sha256(Path('empire_os', name + '.py').read_bytes()).hexdigest() == expected


def test_cycle_idempotence_and_objective_identity():
    first = build()
    second = build()
    assert first == second
    assert first['campaigns'][0]['campaign_id'] == second['campaigns'][0]['campaign_id']
    data = inputs()
    data['radar']['candidates'][0]['products'] = []
    assert build(data)['campaigns'][0]['campaign_id'] != first['campaigns'][0]['campaign_id']
