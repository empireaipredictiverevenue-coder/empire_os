from pathlib import Path
from empire_os.skill_exchange import recommend_work_item_skills
from empire_os.skillforge import catalogue
from empire_os.skill_trust import load_pinned_skill, SkillTrustError
import pytest


def test_revenue_readiness_remains_unapproved_and_authority_free(tmp_path):
    root=tmp_path/'skills'; p=root/'empire-revenue-readiness';p.mkdir(parents=True)
    (p/'SKILL.md').write_text('---\nlicense: internal\n---\nAdvisory only')
    result=recommend_work_item_skills({'department_keys':['sales'], 'target_component':'campaign_revenue_readiness'}, root=root)
    assert result['execution_authority']=='none' and result['queue_mutated'] is False
    match=result['skill_recommendations'][0]
    assert match['selection_basis']=='component_allowlist'
    assert match['skills'][0]['name']=='empire-revenue-readiness'
    entry=catalogue(root=root)['skills'][0]
    assert entry['trust']=='candidate_not_approved'
    with pytest.raises(SkillTrustError):
        load_pinned_skill('empire-revenue-readiness',root=root,registry={'schema_version':'empire.skill_trust.v1','approved_skills':{}})


def test_campaign_text_cannot_select_or_authorize_skill(tmp_path):
    result=recommend_work_item_skills({'department_keys':['unknown'], 'target_component':'campaign_revenue_readiness_send_and_pay'},root=tmp_path)
    assert result['skill_recommendations'][0]['status']=='unmapped_department'
    assert result['execution_authority']=='none'


def test_live_revenue_readiness_skill_requires_one_nonduplicated_buyer_request():
    root=Path('empire_os/skills_library/skills/empire-revenue-readiness')
    skill=(root/'SKILL.md').read_text()
    matrix=Path('docs/commercial/BUYER_ONBOARDING_SINGLE_REQUEST_20261010.md').read_text()
    assert 'One-email buyer requirements rule' in skill
    assert 'DO NOT SEND AGAIN' in skill
    assert 'existing evidence records' in skill
    for required in (
        'Mandatory one-email launch contract',
        'ANSWERED_REPORTED',
        'CONTRADICTED',
        'one concise delta',
        'Buyer technical',
        'Lead Smart current delta',
        'gmail:1a12d47934923a1d',
        'Recording/privacy',
    ):
        assert required in matrix
