from pathlib import Path
from empire_os.skill_exchange import discover_task_skills

def test_task_discovers_local_skill_without_execution(tmp_path):
    p = tmp_path / 'empire-evidence-verification';p.mkdir();(p/'SKILL.md').write_text('# approved candidate')
    r = discover_task_skills('evidence_analysis', root=tmp_path)
    assert [x['name'] for x in r['skills']] == ['empire-evidence-verification']
    assert r['execution_authority'] == 'none'
    assert r['external_download'] is False

def test_missing_skill_is_explicit(tmp_path):
    assert discover_task_skills('entity_resolution', root=tmp_path)['status'] == 'missing_local_skills'

def test_unmapped_task_is_not_guessed(tmp_path):
    assert discover_task_skills('send_payment', root=tmp_path)['status'] == 'unmapped_task'

def test_symlink_escape_not_loaded(tmp_path):
    external = tmp_path.parent / 'outside_skill_exchange.md';external.write_text('unsafe')
    p=tmp_path/'empire-evidence-verification';p.mkdir();(p/'SKILL.md').symlink_to(external)
    assert discover_task_skills('evidence_analysis', root=tmp_path)['skills'] == []
    external.unlink()

from empire_os.skill_exchange import recommend_work_item_skills

def test_department_work_item_gets_local_advice_without_dispatch(tmp_path):
    p = tmp_path/'empire-reply-triage';p.mkdir();(p/'SKILL.md').write_text('safe')
    result = recommend_work_item_skills({'id': 'work-1', 'department_keys': ['sales', 'unknown']}, root=tmp_path)
    assert result['execution_authority'] == 'none'
    assert result['queue_mutated'] is False
    assert result['skill_recommendations'][0]['skills'][0]['name'] == 'empire-reply-triage'
    assert result['skill_recommendations'][1]['status'] == 'unmapped_department'

def test_malformed_department_contract_fails_closed(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        recommend_work_item_skills({'department_keys': 'sales'}, root=tmp_path)

def test_skill_manifest_is_content_pinned(tmp_path):
    p = tmp_path/'empire-evidence-verification';p.mkdir();skill=p/'SKILL.md';skill.write_text('version 1')
    before=discover_task_skills('evidence_analysis', root=tmp_path)['skills'][0]
    skill.write_text('version 2')
    after=discover_task_skills('evidence_analysis', root=tmp_path)['skills'][0]
    assert before['sha256'] != after['sha256']
    assert before['status'] == 'local_candidate_not_authorized'


def test_real_department_keys_map_to_empire_skills(tmp_path):
    from empire_os.skill_exchange import recommend_work_item_skills
    expected = {
        'product': 'empire-product-catalog-verification',
        'market_intelligence': 'empire-evidence-verification',
        'sales_revenue': 'empire-reply-triage',
        'rd_innovation': 'empire-skill-authoring',
        'data_quant': 'empire-forecast-validation',
        'marketing_growth': 'empire-seo-intelligence',
        'finance_capital': 'empire-revenue-reconciliation',
        'operations_fulfilment': 'empire-fulfilment-verification',
    }
    for department, name in expected.items():
        p=tmp_path/name;p.mkdir(exist_ok=True);(p/'SKILL.md').write_text('Empire advisory instructions')
        result=recommend_work_item_skills({'department_keys':[department]},root=tmp_path)
        assert result['skill_recommendations'][0]['skills'][0]['name']==name
        assert result['skill_recommendations'][0]['selection_basis']=='department_allowlist'


def test_exact_component_precedes_department_default(tmp_path):
    from empire_os.skill_exchange import recommend_work_item_skills
    for name in ('empire-forecast-validation', 'empire-evidence-verification'):
        p=tmp_path/name;p.mkdir();(p/'SKILL.md').write_text('instructions')
    result=recommend_work_item_skills({
        'department_keys':['market_intelligence'],
        'target_component':'predictive_cloud_opportunity_loop',
    },root=tmp_path)
    chosen=result['skill_recommendations'][0]
    assert chosen['skills'][0]['name']=='empire-forecast-validation'
    assert chosen['selection_basis']=='component_allowlist'
    assert result['execution_authority']=='none'


def test_unknown_component_does_not_expand_authority(tmp_path):
    from empire_os.skill_exchange import recommend_work_item_skills
    result=recommend_work_item_skills({
        'department_keys':['unrecognized_department'],
        'target_component':'send_outbound_and_pay_money',
    },root=tmp_path)
    assert result['skill_recommendations'][0]['status']=='unmapped_department'
    assert result['queue_mutated'] is False
