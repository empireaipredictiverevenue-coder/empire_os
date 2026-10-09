from hashlib import sha256
import pytest
from empire_os.skill_trust import load_pinned_skill, SkillTrustError

def setup_skill(tmp_path, body=b'# Verified instructions'):
    p=tmp_path/'safe-skill';p.mkdir();(p/'SKILL.md').write_bytes(body)
    return {'schema_version':'empire.skill_trust.v1','approved_skills':{'safe-skill':{'status':'approved','sha256':sha256(body).hexdigest()}}}

def test_approved_digest_can_load_instructions(tmp_path):
    registry=setup_skill(tmp_path)
    result=load_pinned_skill('safe-skill', root=tmp_path, registry=registry)
    assert result['body']=='# Verified instructions'
    assert result['scripts_executed'] is False

def test_modified_skill_fails_closed(tmp_path):
    registry=setup_skill(tmp_path)
    (tmp_path/'safe-skill'/'SKILL.md').write_text('tampered')
    with pytest.raises(SkillTrustError, match='digest_mismatch'):
        load_pinned_skill('safe-skill', root=tmp_path, registry=registry)

def test_missing_approval_fails_closed(tmp_path):
    setup_skill(tmp_path)
    with pytest.raises(SkillTrustError, match='missing_trust_registry'):
        load_pinned_skill('safe-skill', root=tmp_path)

def test_symlink_skill_fails_closed(tmp_path):
    registry=setup_skill(tmp_path)
    target=tmp_path/'safe-skill'/'SKILL.md';target.unlink()
    other=tmp_path/'other';other.write_text('hello');target.symlink_to(other)
    with pytest.raises(SkillTrustError, match='unsafe_skill_path'):
        load_pinned_skill('safe-skill', root=tmp_path, registry=registry)

def test_unapproved_skill_fails_closed(tmp_path):
    registry=setup_skill(tmp_path);registry['approved_skills']['safe-skill']['status']='candidate'
    with pytest.raises(SkillTrustError, match='skill_not_approved'):
        load_pinned_skill('safe-skill', root=tmp_path, registry=registry)

from empire_os.skill_trust import load_work_item_skill_context

def test_work_item_consumes_only_approved_skill(tmp_path):
    p=tmp_path/'empire-reply-triage';p.mkdir();body=b'# Sales instructions';(p/'SKILL.md').write_bytes(body)
    registry={'schema_version':'empire.skill_trust.v1','approved_skills':{'empire-reply-triage':{'status':'approved','sha256':sha256(body).hexdigest()}}}
    result=load_work_item_skill_context({'id':'task-1','department_keys':['sales']}, root=tmp_path, registry=registry)
    assert [s['name'] for s in result['skills']] == ['empire-reply-triage']
    assert result['scripts_executed'] is False

def test_unapproved_work_item_cannot_load_skill(tmp_path):
    p=tmp_path/'empire-reply-triage';p.mkdir();(p/'SKILL.md').write_text('not approved')
    result=load_work_item_skill_context({'id':'task-1','department_keys':['sales']}, root=tmp_path)
    assert result['skills'] == []
    assert result['rejected'][0]['reason'] == 'missing_trust_registry'


def test_approved_oversized_skill_does_not_enter_agent_context(tmp_path):
    p=tmp_path/'empire-reply-triage';p.mkdir()
    body=(b'X' * 13000)
    (p/'SKILL.md').write_bytes(body)
    registry={'schema_version':'empire.skill_trust.v1','approved_skills':{
        'empire-reply-triage':{'status':'approved','sha256':sha256(body).hexdigest()}}}
    result=load_work_item_skill_context({'department_keys':['sales']},root=tmp_path,registry=registry)
    assert result['skills']==[]
    assert result['rejected'][0]['reason']=='skill_context_too_large'
    assert result['context_bytes']==0
