"""Safety and integration tests for automatic draft capture."""
import json
import subprocess
from pathlib import Path

import empire_os.department_worker as worker_module
from empire_os.astra_department_dispatch import dispatch_executive_plan
from empire_os.skillforge_learning import capture_completed_work


def done_work(tmp_path: Path, *, status='DONE', refs=None, result=None):
    work_id='dept_work_'+'a'*24
    path=tmp_path/'runtime/departments/work/done'/f'{work_id}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({
        'id':work_id, 'status':status, 'authority':'observe', 'error':None,
        'target_component':'reply_triage',
        'result': {'adapter':'verified_reply_adapter', 'execution_authority':'none'} if result is None else result,
        'result_evidence_refs': ['canonical:outbound_replies:example'] if refs is None else refs,
    }))
    return work_id


def test_completed_work_captures_redacted_candidate(tmp_path):
    work_id=done_work(tmp_path)
    outcome=capture_completed_work(tmp_path, work_id)
    assert outcome['status']=='candidate_saved'
    record=json.loads(next((tmp_path/'runtime/skillforge/observations').glob('*.json')).read_text())
    assert record['approved'] is False
    assert record['skill_available_to_agents'] is False
    assert record['status']=='DRAFT_REVIEW_REQUIRED'
    assert record['adapter']=='verified_reply_adapter'
    assert 'canonical:outbound_replies:example' not in json.dumps(record)
    assert work_id not in json.dumps(record)
    assert len(record['source_evidence_sha256'])==1


def test_dedupes_same_completed_work(tmp_path):
    work_id=done_work(tmp_path)
    first=capture_completed_work(tmp_path,work_id)
    second=capture_completed_work(tmp_path,work_id)
    assert first['candidate_id']==second['candidate_id']
    assert second['status']=='existing_candidate'
    assert len(list((tmp_path/'runtime/skillforge/observations').glob('*.json')))==1


def test_rejects_blocked_or_unproven_completion(tmp_path):
    work_id=done_work(tmp_path,status='BLOCKED')
    assert capture_completed_work(tmp_path,work_id)['status']=='skipped'
    done_work(tmp_path,status='DONE',refs=[])
    assert capture_completed_work(tmp_path,work_id)['reason']=='missing_completion_evidence'
    done_work(tmp_path,status='DONE',result={'adapter':'verified_reply_adapter','simulated':True})
    assert capture_completed_work(tmp_path,work_id)['reason']=='unsupported_result_authority'
    assert not (tmp_path/'runtime/skillforge/observations').exists()


def test_invalid_id_fails_without_file_reads(tmp_path):
    result=capture_completed_work(tmp_path,'../../root/secret')
    assert result['reason']=='invalid_work_id'
    assert not (tmp_path/'runtime/skillforge').exists()


def test_department_worker_saves_candidate_without_approving(tmp_path,monkeypatch):
    source=tmp_path/'runtime/astra/executive_latest.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'plan_id':'skillforge-test','plan':[{
        'step_id':'work-1','goal_key':'test','department_keys':['product'],
        'target_component':'commercial_product_catalog','action':'refresh',
        'authority':'observe','auto_dispatch_eligible':True,
        'founder_gate_required':False,
    }]}))
    dispatch_executive_plan(tmp_path)
    monkeypatch.setattr(worker_module.subprocess,'run',lambda *a,**k: subprocess.CompletedProcess(a,0,stdout='ok',stderr=''))
    outcome=worker_module.run_one_department_work(tmp_path)
    assert outcome['state']=='DONE'
    assert outcome['skillforge_observation']['status']=='candidate_saved'
    assert outcome['skillforge_observation']['approved'] is False
    assert len(list((tmp_path/'runtime/skillforge/observations').glob('*.json')))==1


def test_worker_capture_error_does_not_invalidate_done(tmp_path,monkeypatch):
    source=tmp_path/'runtime/astra/executive_latest.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'plan_id':'skillforge-test','plan':[{
        'step_id':'work-2','goal_key':'test','department_keys':['product'],
        'target_component':'commercial_product_catalog','action':'refresh',
        'authority':'observe','auto_dispatch_eligible':True,
        'founder_gate_required':False,
    }]}))
    dispatch_executive_plan(tmp_path)
    monkeypatch.setattr(worker_module.subprocess,'run',lambda *a,**k: subprocess.CompletedProcess(a,0,stdout='ok',stderr=''))
    import empire_os.skillforge_learning as learning
    monkeypatch.setattr(learning,'capture_completed_work',lambda *a,**k: (_ for _ in ()).throw(OSError('sensitive failure')))
    outcome=worker_module.run_one_department_work(tmp_path)
    assert outcome['state']=='DONE'
    assert outcome['skillforge_observation']=={'status':'capture_error','approved':False}

from empire_os.skillforge_learning import learning_index
from empire_os.skillforge import catalogue


def test_learning_index_groups_same_verified_technique(tmp_path):
    first=done_work(tmp_path)
    assert capture_completed_work(tmp_path, first)['status']=='candidate_saved'
    new_id='dept_work_'+'b'*24
    old=tmp_path/'runtime/departments/work/done'/f'{first}.json'
    record=json.loads(old.read_text());record['id']=new_id
    (old.parent/f'{new_id}.json').write_text(json.dumps(record))
    assert capture_completed_work(tmp_path,new_id)['status']=='candidate_saved'
    index=learning_index(tmp_path)
    assert index['observation_count']==2
    assert index['techniques'][0]['observation_count']==2
    assert index['techniques'][0]['review_required'] is True
    assert index['techniques'][0]['learned_skill_approved'] is False
    summary=catalogue(root=tmp_path/'nonexisting_skill_library',repo_root=tmp_path)
    assert summary['learning']['observation_count']==2


def test_learning_index_skips_corrupt_or_unapproved_observations(tmp_path):
    directory=tmp_path/'runtime/skillforge/observations';directory.mkdir(parents=True)
    (directory/'skill_observation_bad.json').write_text('{not-json')
    (directory/'skill_observation_fake.json').write_text(json.dumps({'approved':True,'status':'DRAFT_REVIEW_REQUIRED'}))
    assert learning_index(tmp_path)['observation_count']==0


def test_observation_references_result_version_without_exposing_output(tmp_path):
    work_id=done_work(tmp_path,result={
        'adapter':'verified_reply_adapter',
        'execution_authority':'none',
        'secret_example':'private@example.com',
    })
    assert capture_completed_work(tmp_path,work_id)['status']=='candidate_saved'
    record=json.loads(next((tmp_path/'runtime/skillforge/observations').glob('*.json')).read_text())
    assert len(record['source_result_sha256'])==64
    assert record['repeatability_verified'] is False
    assert record['success_claim']=='canonical_work_marked_DONE_only'
    assert 'private@example.com' not in json.dumps(record)


def test_observation_directory_symlink_fails_safely(tmp_path):
    work_id=done_work(tmp_path)
    other=tmp_path/'other';other.mkdir()
    expected=tmp_path/'runtime/skillforge/observations'
    expected.parent.mkdir(parents=True,exist_ok=True)
    expected.symlink_to(other,target_is_directory=True)
    import pytest
    with pytest.raises(ValueError,match='unsafe_skillforge_directory'):
        capture_completed_work(tmp_path,work_id)
    assert not list(other.iterdir())
