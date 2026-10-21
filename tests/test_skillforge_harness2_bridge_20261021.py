from pathlib import Path
import json
import shutil

from empire_os.skillforge_harness2_bridge import skillforge_harness2_candidate
from empire_os.skillforge import catalogue

REPO=Path(__file__).resolve().parents[1]
MANIFEST=Path('config/harness2_evidence_guard_candidate_20261021.json')
GUARD=Path('empire_os/astra_harness_evidence_guard.py')
REPLAY=Path('config/harness2_evidence_guard_replay_receipt_20261021.json')
FRESH_TRIAL=Path('config/harness2_original_source_shadow_receipt_20261021.json')

def prepare(tmp_path, *, replay=True):
    for path in (MANIFEST,GUARD,FRESH_TRIAL,*([REPLAY] if replay else [])):
        to=tmp_path/path
        to.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(REPO/path,to)
    return tmp_path

def test_original_evaluated_guard_is_draft_not_trusted():
    answer=skillforge_harness2_candidate(REPO)
    assert answer['status']=='REVIEW_REQUIRED_REPLAY_EVIDENCE_VERIFIED'
    assert answer['source_replay_present_and_consistent'] is True
    assert answer['original_evidence_tasks']==2
    assert answer['independent_real_agent_completions']==0
    assert answer['independent_holdout_verified'] is False
    assert answer['approved'] is False
    assert answer['skill_available_to_agents'] is False
    assert answer['release_allowed'] is False

def test_real_skillforge_catalogue_keeps_approved_count_unchanged(tmp_path):
    root=prepare(tmp_path)
    got=catalogue(root=tmp_path/'none',repo_root=root)
    assert got['harness2_guard_candidate']['status']=='REVIEW_REQUIRED_REPLAY_EVIDENCE_VERIFIED'
    assert got['approved_count']==0
    assert got['skill_count']==0
    assert got['execution_authority']=='none'

def test_replay_artifact_unavailable_is_a_review_hold(tmp_path):
    root=prepare(tmp_path,replay=False)
    got=skillforge_harness2_candidate(root)
    assert got['status']=='PINNED_REPLAY_NOT_AVAILABLE_ON_THIS_WORKSPACE'
    assert got['skill_available_to_agents'] is False

def test_altered_guard_source_is_detected(tmp_path):
    root=prepare(tmp_path)
    with (root/GUARD).open('a') as file:
        file.write('\n# altered guard')
    assert skillforge_harness2_candidate(root)['status']=='INVALID_OR_TAMPERED_HARNESS2_REVIEW_EVIDENCE'

def test_altered_replay_receipt_is_detected(tmp_path):
    root=prepare(tmp_path)
    p=root/REPLAY
    data=json.loads(p.read_text())
    data['measured']['guarded_passed']=99
    p.write_text(json.dumps(data))
    assert skillforge_harness2_candidate(root)['status']=='INVALID_OR_TAMPERED_HARNESS2_REVIEW_EVIDENCE'

def test_manifest_cannot_grant_approval(tmp_path):
    root=prepare(tmp_path)
    p=root/MANIFEST
    data=json.loads(p.read_text())
    data['approved']=True
    data['skill_available_to_agents']=True
    data['independent_real_agent_completions']=20
    p.write_text(json.dumps(data))
    result=skillforge_harness2_candidate(root)
    assert result['status']=='INVALID_OR_TAMPERED_HARNESS2_REVIEW_EVIDENCE'
    assert result['approved'] is False

def test_missing_or_symlinked_manifest_rejected(tmp_path):
    root=prepare(tmp_path)
    (root/MANIFEST).unlink()
    (root/MANIFEST).symlink_to(REPO/MANIFEST)
    assert skillforge_harness2_candidate(root)['status']=='INVALID_OR_TAMPERED_HARNESS2_REVIEW_EVIDENCE'

def test_uninstalled_skillforge_candidate_is_not_a_tamper_claim(tmp_path):
    result=skillforge_harness2_candidate(tmp_path)
    assert result['status']=='CANDIDATE_NOT_INSTALLED_ON_THIS_WORKSPACE'
    assert result['approved'] is False
