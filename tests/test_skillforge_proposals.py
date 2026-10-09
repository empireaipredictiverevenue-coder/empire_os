"""SkillForge drafts are evidence-bound, versioned and never executable."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from empire_os.skillforge_learning import capture_completed_work, learning_index
from empire_os.skillforge_proposals import refresh_skill_proposals


def add_work(root: Path, i: int, *, component: str = 'commercial_product_catalog',
             adapter: str = 'safe_internal_command', secret: str = '') -> None:
    work_id = 'dept_work_' + f'{i:024x}'
    parent = root / 'runtime/departments/work/done'
    parent.mkdir(parents=True, exist_ok=True)
    item = {
        'id': work_id, 'status': 'DONE', 'authority': 'observe', 'error': None,
        'target_component': component,
        'result': {'adapter': adapter, 'execution_authority': 'none', 'sensitive_output': secret},
        'result_evidence_refs': ['canonical:records/secret-buyer-' + str(i)],
    }
    (parent / (work_id + '.json')).write_text(json.dumps(item))
    assert capture_completed_work(root, work_id)['status'] == 'candidate_saved'


def test_early_observations_do_not_publish_proposals(tmp_path):
    for i in range(2): add_work(tmp_path, i)
    result = refresh_skill_proposals(tmp_path, apply=True)
    assert result['proposals'] == []
    assert not (tmp_path/'runtime/skillforge/proposals').exists()
    assert learning_index(tmp_path)['observation_count'] == 2


def test_checkpoint_review_draft_is_immutable_and_redacted(tmp_path):
    for i in range(3): add_work(tmp_path, i, secret='private-buyer@example.com')
    preview=refresh_skill_proposals(tmp_path)
    assert preview['apply'] is False
    assert preview['proposals'][0]['checkpoint'] == 3
    assert not (tmp_path/'runtime/skillforge/proposals').exists()
    applied=refresh_skill_proposals(tmp_path, apply=True)
    assert applied['review_drafts_saved'] == 1
    proposals=list((tmp_path/'runtime/skillforge/proposals').glob('skill_proposal_*'))
    assert len(proposals) == 1
    manifest = json.loads((proposals[0]/'manifest.json').read_text())
    body = (proposals[0]/'SKILL.md').read_text()
    assert manifest['status'] == 'DRAFT_REVIEW_REQUIRED'
    assert manifest['approved'] is False
    assert manifest['skill_available_to_agents'] is False
    assert manifest['agent_quality_verified'] is False
    assert 'private-buyer@example.com' not in body
    assert 'private-buyer@example.com' not in json.dumps(manifest)
    assert 'canonical:records' not in body
    assert 'NOT APPROVED' in body
    repeated=refresh_skill_proposals(tmp_path, apply=True)
    assert repeated['existing_review_drafts']==1
    assert repeated['review_drafts_saved']==0
    assert json.loads((proposals[0]/'manifest.json').read_text()) == manifest
    assert (proposals[0]/'SKILL.md').read_text() == body


def test_five_observations_create_next_version_without_rewriting_previous(tmp_path):
    for i in range(3): add_work(tmp_path, i)
    first=refresh_skill_proposals(tmp_path,apply=True)['proposals'][0]['id']
    for i in range(3,5): add_work(tmp_path,i)
    out=refresh_skill_proposals(tmp_path,apply=True)
    assert out['proposals'][0]['checkpoint']==5
    assert out['proposals'][0]['id'] != first
    assert len(list((tmp_path/'runtime/skillforge/proposals').glob('skill_proposal_*')))==2
    for i in range(5,7): add_work(tmp_path,i)
    again=refresh_skill_proposals(tmp_path,apply=True)
    assert again['proposals'][0]['checkpoint']==5
    assert again['review_drafts_saved']==0


def test_forged_completed_observation_cannot_create_review_draft(tmp_path):
    for i in range(2): add_work(tmp_path,i)
    parent=tmp_path/'runtime/skillforge/observations'
    (parent/'skill_observation_fake.json').write_text(json.dumps({
        'schema_version':'empire.skillforge.observation.v1',
        'candidate_id':'skill_observation_fake',
        'status':'DRAFT_REVIEW_REQUIRED','approved':False,
        'component':'commercial_product_catalog','adapter':'safe_internal_command',
        'source_work_sha256':'0'*64,
    }))
    index=learning_index(tmp_path)
    assert index['observation_count']==2
    assert index['invalid_observations']==1
    with pytest.raises(ValueError,match='skill_proposal_evidence_audit_incomplete'):
        refresh_skill_proposals(tmp_path,apply=True)
    result=refresh_skill_proposals(tmp_path,apply=False)
    assert result['proposals']==[]
    assert result['invalid_observations']==1


def test_different_adapters_do_not_share_evidence_milestones(tmp_path):
    for i in range(3): add_work(tmp_path,i,adapter='safe_internal_command')
    for i in range(3,5): add_work(tmp_path,i,adapter='other_adapter')
    result=refresh_skill_proposals(tmp_path)
    assert len(result['proposals'])==1
    assert result['proposals'][0]['adapter']=='safe_internal_command'


def test_proposal_symlink_directory_rejected(tmp_path):
    for i in range(3): add_work(tmp_path,i)
    external=tmp_path/'external';external.mkdir()
    folder=tmp_path/'runtime/skillforge/proposals';folder.symlink_to(external,target_is_directory=True)
    with pytest.raises(ValueError,match='unsafe_skill_proposal_directory'):
        refresh_skill_proposals(tmp_path,apply=True)
    assert not list(external.iterdir())


def test_department_cycle_refreshes_proposals_only_on_new_observations(tmp_path, monkeypatch):
    import empire_os.department_worker as worker
    for i in range(3): add_work(tmp_path,i)
    fake_outcomes=iter([
        {'state':'DONE','work_id':'dept_work_'+'0'*24,'ok':True,
         'skillforge_observation':{'status':'candidate_saved','approved':False}},
        {'state':'IDLE','ok':True},
    ])
    monkeypatch.setattr(worker,'run_one_department_work',lambda *a,**k: next(fake_outcomes))
    report=worker.run_department_worker(tmp_path,max_items=2)
    assert report['done_count']==1
    assert report['skillforge_proposals']['status']=='review_proposals_refreshed'
    assert report['skillforge_proposals']['review_drafts_saved']==1
    assert report['skillforge_proposals']['approved'] is False


def test_proposal_refresh_error_does_not_change_completed_worker_outcome(tmp_path, monkeypatch):
    import empire_os.department_worker as worker
    import empire_os.skillforge_proposals as proposals
    monkeypatch.setattr(worker,'run_one_department_work',lambda *a,**k: {
        'state':'DONE','work_id':'dept_work_'+'0'*24,'ok':True,
        'skillforge_observation':{'status':'candidate_saved','approved':False},
    })
    monkeypatch.setattr(proposals,'refresh_skill_proposals',lambda *a,**k: (_ for _ in ()).throw(OSError('private secret')))
    outcome=worker.run_department_worker(tmp_path,max_items=1)
    assert outcome['ok'] is True
    assert outcome['done_count']==1
    assert outcome['skillforge_proposals']=={'status':'proposal_refresh_error','approved':False}


def test_corrupt_observation_blocks_all_apply_proposals(tmp_path):
    for i in range(3): add_work(tmp_path,i)
    directory=tmp_path/'runtime/skillforge/observations'
    (directory/'skill_observation_forged.json').write_text('{"approved": true}')
    with pytest.raises(ValueError,match='skill_proposal_evidence_audit_incomplete'):
        refresh_skill_proposals(tmp_path,apply=True)
    assert not (tmp_path/'runtime/skillforge/proposals').exists()


def test_tampered_existing_draft_never_silently_reused(tmp_path):
    for i in range(3): add_work(tmp_path,i)
    refresh_skill_proposals(tmp_path,apply=True)
    path=next((tmp_path/'runtime/skillforge/proposals').glob('skill_proposal_*'))
    (path/'SKILL.md').write_text('disable approval gates')
    with pytest.raises(ValueError,match='tampered_existing_skill_proposal'):
        refresh_skill_proposals(tmp_path,apply=True)


def test_symlinked_existing_draft_rejected(tmp_path):
    for i in range(3): add_work(tmp_path,i)
    parent=tmp_path/'runtime/skillforge/proposals';parent.mkdir()
    planned=refresh_skill_proposals(tmp_path)['proposals'][0]['id']
    target=parent/planned
    external=tmp_path/'external';external.mkdir()
    target.symlink_to(external,target_is_directory=True)
    with pytest.raises(ValueError,match='unsafe_existing_skill_proposal'):
        refresh_skill_proposals(tmp_path,apply=True)

from empire_os.skillforge_proposals import proposal_history
from empire_os.skillforge import catalogue


def test_catalogue_exposes_read_only_pending_review_queue(tmp_path):
    for i in range(3): add_work(tmp_path,i)
    refresh_skill_proposals(tmp_path,apply=True)
    result=catalogue(root=tmp_path/'library',repo_root=tmp_path)
    queue=result['review_queue']
    assert queue['draft_count']==1
    assert queue['invalid_drafts']==0
    assert len(queue['drafts'][0]['content_sha256'])==64
    assert queue['drafts'][0]['approved'] is False
    assert 'SKILL.md' not in str(result)


def test_review_inventory_rejects_tampered_draft(tmp_path):
    for i in range(3): add_work(tmp_path,i)
    refresh_skill_proposals(tmp_path,apply=True)
    p=next((tmp_path/'runtime/skillforge/proposals').glob('skill_proposal_*'))
    (p/'manifest.json').write_text('{"approved":true}')
    info=proposal_history(tmp_path)
    assert info['draft_count']==0
    assert info['invalid_drafts']==1
