"""Existing department -> Empire Coder PLAN uses pinned skill instructions."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import empire_os.department_worker as worker
from empire_os.skill_trust import build_advisory_work_item_skill_text


def _setup(tmp_path, *, digest_tampered=False, include_external=False):
    names = ['empire-lead-research', 'empire-identity-resolution']
    if include_external:
        names.append('pdf')
    approved = {}
    for name in names:
        f = tmp_path / 'empire_os/skills_library/skills' / name / 'SKILL.md'
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f'# {name}\nOnly research. Do not send, spend, publish or write to production.\n')
        digest = sha256(f.read_bytes()).hexdigest()
        approved[name] = {'status':'approved', 'sha256': '0'*64 if digest_tampered else digest,
                          'trust_scope':'advisory_instruction_only',
                          'external_execution_authority':'none'}
    path=tmp_path/'config/skill_trust_registry.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'schema_version':'empire.skill_trust.v1','approved_skills':approved}))
    return approved


def _item(*,component='buyer_relationship_research',departments=('sales_revenue',)):
    return SimpleNamespace(
        id='dept_work_0123456789abcdef01234567', goal_key='verify_existing_buyer',
        department_keys=departments, target_component=component,
        action='review_existing_buyer_source', rationale='existing buyer evidence check',
        success_condition='return provenance and unknowns', evidence_refs=('source:verified',),
        plan_id='existing_astra_plan', step_id='existing_step', priority=75,
        intelligence_request={},
    )


def _capture(monkeypatch):
    sink={}
    class FakeCoder:
        def __init__(self, repo_root, *, runtime_root):
            sink['root']=repo_root
        def create_task(self, objective):
            sink['objective']=objective
            return SimpleNamespace(id='original-coder-task-id')
    class FakeQueue:
        def __init__(self, repo_root, *, runtime_root): pass
        def enqueue(self, *, task_id, kind, priority, payload):
            sink['payload']=payload
            sink['job_kind']=kind
            return SimpleNamespace(id='original-coder-job-id')
    monkeypatch.setattr(worker, 'EmpireCoder', FakeCoder)
    monkeypatch.setattr(worker, 'LocalJobQueue', FakeQueue)
    return sink


def test_real_existing_coder_bridge_includes_verified_skill_content(tmp_path, monkeypatch):
    _setup(tmp_path)
    sink=_capture(monkeypatch)
    result=worker._coder_bridge(tmp_path,_item())
    assert result['adapter']=='empire_coder_plan_bridge'
    assert result['skill_instruction_context_loaded'] is True
    assert result['skill_instruction_names']==['empire-lead-research','empire-identity-resolution']
    assert len(result['skill_instruction_sha256'])==2
    assert '## VERIFIED EMPIRE SKILLFORGE ADVISORY CONTEXT' in sink['objective']
    assert 'Only research. Do not send, spend' in sink['objective']
    assert 'PLAN ONLY' in sink['objective']
    assert sink['payload']['execution_authority']=='none'
    assert sink['payload']['skill_instruction_names']==result['skill_instruction_names']
    assert sink['payload']['skill_instruction_sha256']==result['skill_instruction_sha256']
    assert sink['payload']['department_work_id']==_item().id
    assert result['external_execution_performed'] is False
    assert result['implementation_performed'] is False


def test_external_skills_excluded_even_if_pinned(tmp_path,monkeypatch):
    _setup(tmp_path,include_external=True)
    sink=_capture(monkeypatch)
    result=worker._coder_bridge(tmp_path,_item(component='knowledge_factory_document_review',departments=('market_intelligence',)))
    assert result['skill_instruction_names']==[]
    assert 'pdf' not in sink['objective'].lower()
    assert 'ADVISORY CONTEXT' not in sink['objective']


def test_tampered_hash_is_silently_rejected_without_changing_coder_work(tmp_path,monkeypatch):
    _setup(tmp_path,digest_tampered=True)
    sink=_capture(monkeypatch)
    result=worker._coder_bridge(tmp_path,_item())
    assert result['skill_instruction_context_loaded'] is False
    assert result['skill_instruction_names']==[]
    assert 'ADVISORY CONTEXT' not in sink['objective']
    assert 'PLAN ONLY' in sink['objective']


def test_registry_missing_never_breaks_existing_coder_plan(tmp_path,monkeypatch):
    sink=_capture(monkeypatch)
    result=worker._coder_bridge(tmp_path,_item())
    assert result['skill_instruction_context_loaded'] is False
    assert result['coder_task_id']=='original-coder-task-id'


def test_skill_prompt_budget_rejects_partial_or_oversized_content(tmp_path):
    approved=_setup(tmp_path)
    huge=tmp_path/'empire_os/skills_library/skills/empire-lead-research/SKILL.md'
    huge.write_text('Do not send, spend or publish.\n'*450)
    approved['empire-lead-research']['sha256']=sha256(huge.read_bytes()).hexdigest()
    result=build_advisory_work_item_skill_text(
        {'id':'t','department_keys':['sales_revenue'], 'target_component':'buyer_relationship_research'},
        root=tmp_path/'empire_os/skills_library/skills',
        registry={'schema_version':'empire.skill_trust.v1','approved_skills':approved},
        max_chars=9000,
    )
    assert result['skill_names']==['empire-identity-resolution']
    assert 'empire-lead-research' not in result['text']
    assert 'Do not send, spend or publish.' not in result['text']
    assert result['execution_authority']=='none' and result['scripts_executed'] is False


def test_exact_ui_specialists_are_selected_by_review_action_without_scripts(tmp_path):
    root=tmp_path/'empire_os/skills_library/skills'
    pins={}
    for name in ('empire-engineering-verification','frontend-design','webapp-testing'):
        path=root/name/'SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text('# '+name+'\nThis is advisory only. No tools are permitted.\n')
        pin={'status':'approved','sha256':sha256(path.read_bytes()).hexdigest(),
             'trust_scope':'advisory_instruction_only','external_execution_authority':'none'}
        if not name.startswith('empire-'):
            pin['licence']='Apache-2.0'
            (path.parent/'LICENSE.txt').write_text('Apache License\nVersion 2.0, January 2004\n')
        pins[name]=pin
    registry={'schema_version':'empire.skill_trust.v1','approved_skills':pins}
    task={'id':'review','department_keys':['engineering'],
          'target_component':'empire_product_ui_review', 'action':'design_review'}
    from empire_os.skill_trust import build_advisory_work_item_skill_text
    design=build_advisory_work_item_skill_text(task,root=root,registry=registry,max_chars=9000)
    assert design['skill_names'][0]=='frontend-design'
    task['action']='browser_regression_review'
    browser=build_advisory_work_item_skill_text(task,root=root,registry=registry,max_chars=9000)
    assert browser['skill_names'][0]=='webapp-testing'
    assert design['scripts_executed'] is False and browser['scripts_executed'] is False
    (root/'webapp-testing/LICENSE.txt').unlink()
    held=build_advisory_work_item_skill_text(task,root=root,registry=registry,max_chars=9000)
    assert 'webapp-testing' not in held['skill_names']
