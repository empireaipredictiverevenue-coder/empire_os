from hashlib import sha256
import json
from scripts.inspect_department_skill_context import inspect

def test_preflight_reports_approved_skill_without_instructions(tmp_path):
    skills=tmp_path/'skills';p=skills/'empire-reply-triage';p.mkdir(parents=True)
    content=b'# Private skill instructions';(p/'SKILL.md').write_bytes(content)
    registry=tmp_path/'trust.json'
    registry.write_text(json.dumps({'schema_version':'empire.skill_trust.v1','approved_skills':{
        'empire-reply-triage':{'status':'approved','sha256':sha256(content).hexdigest()}}}))
    report=inspect(departments=['sales'], trust_registry=registry, skills_root=skills)
    assert report['loaded_skill_count']==1
    assert 'Private skill instructions' not in str(report)
    assert report['execution_authority']=='none'

def test_preflight_default_deny(tmp_path):
    skills=tmp_path/'skills';p=skills/'empire-reply-triage';p.mkdir(parents=True)
    (p/'SKILL.md').write_text('unreviewed')
    report=inspect(departments=['sales'],trust_registry=tmp_path/'missing.json',skills_root=skills)
    assert report['loaded_skill_count']==0
    assert report['rejected'][0]['reason']=='missing_trust_registry'


def test_real_component_selection_is_audited_by_preflight(tmp_path):
    skills=tmp_path/'skills';p=skills/'empire-forecast-validation';p.mkdir(parents=True)
    body=b'forecast evidence review';(p/'SKILL.md').write_bytes(body)
    reg=tmp_path/'trust.json'
    reg.write_text(json.dumps({'schema_version':'empire.skill_trust.v1','approved_skills':{
        'empire-forecast-validation':{'status':'approved','sha256':sha256(body).hexdigest()}}}))
    result=inspect(departments=['market_intelligence'],
                   target_component='predictive_cloud_opportunity_loop',
                   trust_registry=reg,skills_root=skills)
    assert result['loaded_skills'][0]['name']=='empire-forecast-validation'
    assert result['context_bytes']==len(body)
