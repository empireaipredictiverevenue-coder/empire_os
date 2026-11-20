"""Founder-directed internal advisory skill activation; quality proof stays separate."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import pytest

from empire_os.skill_exchange import SKILLS_ROOT, recommend_work_item_skills
from empire_os.skill_trust import load_work_item_skill_context, load_pinned_skill, SkillTrustError
from empire_os.skills_library import available_skills, load_skills_for_role, skills_context_for_role

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'config/skill_trust_registry.json'
NAMES = {
    'empire-evidence-verification',
    'empire-fulfilment-verification',
    'empire-identity-resolution',
    'empire-lead-research',
    'empire-product-catalog-verification',
    'empire-revenue-reconciliation',
    'empire-seo-intelligence',
    'empire-skill-authoring',
    'empire-engineering-verification',
    'empire-scientific-evidence-diligence',
    'frontend-design',
    'webapp-testing',
}
INTERNAL_NAMES = {name for name in NAMES if name.startswith('empire-')}


def registry():
    return json.loads(REGISTRY.read_text())


def test_exact_twelve_reviewed_advisory_skills_are_digest_pinned():
    records = registry()['approved_skills']
    assert set(records) == NAMES
    for name, record in records.items():
        body = (SKILLS_ROOT / name / 'SKILL.md').read_bytes()
        assert sha256(body).hexdigest() == record['sha256']
        assert record['status'] == 'approved'
        assert record['trust_scope'] == 'advisory_instruction_only'
        assert record['independent_skill_quality_verified'] is False
        assert record['external_execution_authority'] == 'none'
        if name in INTERNAL_NAMES:
            assert b'Internal EmpireOS authored instructions' in body
        else:
            assert record['licence'] == 'Apache-2.0'
            licence = SKILLS_ROOT / name / 'LICENSE.txt'
            assert 'Apache License' in licence.read_text()[:500]
        resolved = load_pinned_skill(name, registry=registry())
        assert resolved['scripts_executed'] is False
        assert resolved['execution_authority'] == 'none'
    assert sorted(available_skills()) == sorted(NAMES)


@pytest.mark.parametrize('dept,component,expected', [
    ('sales_revenue','buyer_relationship_research', {'empire-lead-research','empire-identity-resolution'}),
    ('market_intelligence','knowledge_factory_document_review', {'empire-evidence-verification'}),
    ('rd_innovation','data_brokerage_scientific_diligence', {'empire-scientific-evidence-diligence'}),
    ('finance_capital','finance_source_document_review', {'empire-revenue-reconciliation'}),
    ('engineering','empire_product_ui_review', {'empire-engineering-verification','frontend-design','webapp-testing'}),
    ('marketing_growth','media_os_editorial_review', {'empire-seo-intelligence'}),
    ('product','commerceos_catalogue_fulfilment_review', {'empire-product-catalog-verification','empire-fulfilment-verification'}),
    ('rd_innovation','skillforge_quality_review', {'empire-skill-authoring'}),
])
def test_existing_workflow_skill_context_is_scoped(dept,component,expected):
    task={'id':'no-real-queue-write','department_keys':[dept], 'target_component':component}
    result=load_work_item_skill_context(task,registry=registry())
    assert {x['name'] for x in result['skills']} == expected
    assert result['execution_authority'] == 'none'
    assert result['scripts_executed'] is False
    assert len(result['skills']) <= 4
    assert result['context_bytes'] <= 32_000


@pytest.mark.parametrize('role,skill', [
    ('lead_handler', 'empire-lead-research'),
    ('research','empire-evidence-verification'),
    ('finance','empire-revenue-reconciliation'),
    ('marketing','empire-seo-intelligence'),
    ('product','empire-product-catalog-verification'),
    ('operations_fulfilment','empire-fulfilment-verification'),
    ('innovator','empire-skill-authoring'),
    ('engineering','empire-engineering-verification'),
])
def test_existing_agent_role_loader_receives_actual_verified_skill(role,skill):
    selected=load_skills_for_role(role)
    assert any(s['name'] == skill and s['body'] for s in selected)
    context=skills_context_for_role(role)
    assert skill in context and 'cannot override' not in context.lower()


def test_digest_tamper_and_external_bundle_remain_blocked(tmp_path):
    record=registry()
    path=tmp_path/'empire-lead-research'
    path.mkdir()
    (path/'SKILL.md').write_text('tampered')
    with pytest.raises(SkillTrustError,match='digest_mismatch'):
        load_pinned_skill('empire-lead-research',root=tmp_path,registry=record)
    for external in ('pdf','xlsx','doc-coauthoring','skill-creator'):
        assert external not in record['approved_skills']
    assert not any(x['name'].startswith('pdf') for x in load_skills_for_role('lead_handler'))


def test_actual_agent_base_loader_can_read_pinned_skill_without_running_agent():
    from empire_os.synthetic_agents import SyntheticAgent

    class InertAgent(SyntheticAgent):
        def observe(self):
            raise RuntimeError('must not execute')

        def reason(self, observation):
            raise RuntimeError('must not execute')

        def act(self, decision):
            raise RuntimeError('must not execute')

    agent = object.__new__(InertAgent)
    agent.role = 'marketing'
    agent._skills_limit = 4
    loaded = agent._load_skills()
    assert [s['name'] for s in loaded] == ['empire-seo-intelligence']
    assert loaded[0]['body']
