"""Read-only business portfolio skill routing, including trust and no-execution gates."""
from hashlib import sha256

import pytest

from empire_os.skill_exchange import recommend_work_item_skills
from empire_os.skill_trust import load_work_item_skill_context

PORTFOLIO = (
    ('sales_revenue', 'buyer_relationship_research', ('empire-lead-research', 'empire-identity-resolution')),
    ('market_intelligence', 'knowledge_factory_document_review', ('empire-evidence-verification', 'pdf', 'xlsx')),
    ('rd_innovation', 'data_brokerage_scientific_diligence', ('empire-scientific-evidence-diligence', 'pdf')),
    ('finance_capital', 'finance_source_document_review', ('empire-revenue-reconciliation', 'xlsx', 'pdf')),
    ('engineering', 'empire_product_ui_review', ('empire-engineering-verification', 'frontend-design', 'webapp-testing')),
    ('marketing_growth', 'media_os_editorial_review', ('empire-seo-intelligence', 'doc-coauthoring')),
    ('product', 'commerceos_catalogue_fulfilment_review', ('empire-product-catalog-verification', 'empire-fulfilment-verification')),
    ('rd_innovation', 'skillforge_quality_review', ('empire-skill-authoring', 'skill-creator')),
)


@pytest.mark.parametrize('department,component,expected', PORTFOLIO)
def test_exact_portfolio_components_select_relevant_local_candidates(tmp_path, department, component, expected):
    for name in expected:
        p = tmp_path / name
        p.mkdir()
        (p / 'SKILL.md').write_text(f'# {name}\n')
    review = recommend_work_item_skills({'id': 'portfolio-review', 'department_keys': [department],
                                         'target_component': component}, root=tmp_path)
    selection = review['skill_recommendations'][0]
    assert selection['selection_basis'] == 'component_allowlist'
    assert tuple(s['name'] for s in selection['skills']) == expected
    assert all(s['status'] == 'local_candidate_not_authorized' for s in selection['skills'])
    assert review['mode'] == 'OBSERVE' and review['execution_authority'] == 'none'
    assert review['queue_mutated'] is False
    assert review['external_download'] is False


@pytest.mark.parametrize('department,component,expected', PORTFOLIO)
def test_no_trust_approval_never_loads_portfolio_skill(tmp_path, department, component, expected):
    for name in expected:
        p = tmp_path / name
        p.mkdir()
        (p / 'SKILL.md').write_text('unapproved skill')
    result = load_work_item_skill_context({'department_keys': [department],
                                          'target_component': component}, root=tmp_path,
                                          registry={'schema_version': 'empire.skill_trust.v1', 'approved_skills': {}})
    assert result['skills'] == [] and result['scripts_executed'] is False
    assert result['execution_authority'] == 'none'
    assert all(r['reason'] == 'skill_not_approved' for r in result['rejected'])


def test_exact_name_prevents_fuzzy_or_spend_route(tmp_path):
    for n in ('empire-lead-research', 'empire-identity-resolution'):
        p = tmp_path / n
        p.mkdir()
        (p / 'SKILL.md').write_text('safe')
    result = recommend_work_item_skills({
        'department_keys': ['not_a_department'],
        'target_component': 'buyer_relationship_research_send_outbound_and_charge',
    }, root=tmp_path)
    assert result['skill_recommendations'][0]['status'] == 'unmapped_department'
    assert result['execution_authority'] == 'none'


def test_approved_single_skill_cannot_grant_external_action(tmp_path):
    name = 'empire-lead-research'
    skill = tmp_path / name
    skill.mkdir()
    body = b'Internal review procedure only'
    (skill / 'SKILL.md').write_bytes(body)
    registry = {'schema_version': 'empire.skill_trust.v1', 'approved_skills': {
        name: {'status': 'approved', 'sha256': sha256(body).hexdigest()}
    }}
    result = load_work_item_skill_context({
        'department_keys': ['sales_revenue'], 'target_component': 'buyer_relationship_research',
    }, root=tmp_path, registry=registry)
    assert [s['name'] for s in result['skills']] == [name]
    assert result['execution_authority'] == 'none' and result['scripts_executed'] is False
