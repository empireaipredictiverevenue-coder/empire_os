"""Pin original historical source replay, without invented owner attestations."""
from pathlib import Path
import json
import shutil
import pytest
from empire_os.skillforge_coder_historical_review import (
    RECEIPT, read_pinned_original_revision_replay,
)
from empire_os.skillforge import catalogue
ROOT=Path(__file__).resolve().parents[1]


def _copy_replay(root):
    path=root/RECEIPT
    path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/RECEIPT,path)
    return path


def test_original_replay_is_pinned_review_only():
    row=read_pinned_original_revision_replay(ROOT)
    assert row['status']=='PINNED_TWO_ORIGINAL_REVISION_TEST_REPLAYS_REVIEW_ONLY'
    assert row['historical_source_chains_verified']==2
    assert row['original_git_revisions_with_replayed_tests']==2
    assert row['historical_commits_on_current_branch']==0
    assert row['production_deployment_verified'] is False
    assert row['independent_department_completion_attributed'] is False
    assert row['independent_implementation_outcome_verified'] is False
    assert row['automatic_skill_approval'] is False


def test_catalogue_exposes_original_replay_but_no_promotion():
    data=catalogue(root=ROOT/'empire_os/skills_library/skills',repo_root=ROOT)
    assert data['coder_historical_release_test_replay']['status']=='PINNED_TWO_ORIGINAL_REVISION_TEST_REPLAYS_REVIEW_ONLY'
    assert data['coder_original_patch_provenance']['status']=='PINNED_ORIGINAL_PATCH_PROVENANCE_HOLD'
    assert data['approved_count']==0
    assert data['execution_authority']=='none'


def test_original_replay_not_installed_is_hold(tmp_path):
    row=read_pinned_original_revision_replay(tmp_path)
    assert row['status']=='ORIGINAL_REVISION_REPLAY_NOT_INSTALLED'
    assert row['automatic_skill_approval'] is False


@pytest.mark.parametrize('field,forged',[
    ('production_deployment_verified',True),
    ('historical_department_work_completion_link_verified',True),
    ('independent_agent_code_outcomes_verified',2),
    ('skillforge_auto_approval',True),
])
def test_tampered_replay_authority_fails_closed(tmp_path,field,forged):
    path=_copy_replay(tmp_path)
    data=json.loads(path.read_text())
    data[field]=forged
    path.write_text(json.dumps(data))
    assert read_pinned_original_revision_replay(tmp_path)['status']=='ORIGINAL_REVISION_REPLAY_TAMPER_OR_INTEGRITY_HOLD'


def test_symlinked_original_replay_cannot_be_trusted(tmp_path):
    path=tmp_path/RECEIPT
    path.parent.mkdir(parents=True,exist_ok=True)
    path.symlink_to(ROOT/RECEIPT)
    assert read_pinned_original_revision_replay(tmp_path)['status']=='ORIGINAL_REVISION_REPLAY_TAMPER_OR_INTEGRITY_HOLD'


def test_historical_evidence_flows_into_existing_review_only_queue():
    from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    from test_skillforge_coder_replay_review_20261021 import _synthetic_coder_review_family
    source=review_independent_skill_evidence(ROOT)
    source['families']=[_synthetic_coder_review_family()]
    source['family_count']=1
    source['coder_historical_release_test_replay']=read_pinned_original_revision_replay(ROOT)
    base={'schema':'empire.system_improvement_review_plan.v1',
          'automatic_execution_authority':'none',
          'review_packets':[],'task_count':0}
    out=merge_skillforge_evidence_into_review_plan(base,source)
    assert out['task_count']==1
    packet=out['review_packets'][0]
    assert packet['original_revision_replay_status']=='PINNED_TWO_ORIGINAL_REVISION_TEST_REPLAYS_REVIEW_ONLY'
    assert packet['historical_original_git_revisions_with_tests_replayed']==2
    assert packet['historical_release_replay_is_not_attributed_department_work'] is True
    assert packet['auto_dispatch_eligible'] is False
    assert packet['approved_for_implementation'] is False
    assert out['department_work_queue_mutated'] is False


def test_forged_historical_replay_skill_approval_rejected_by_queue():
    from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    from test_skillforge_coder_replay_review_20261021 import _synthetic_coder_review_family
    source=review_independent_skill_evidence(ROOT)
    source['families']=[_synthetic_coder_review_family()]
    source['family_count']=1
    source['coder_historical_release_test_replay']={
        **read_pinned_original_revision_replay(ROOT),
        'automatic_skill_approval':True,
    }
    base={'schema':'empire.system_improvement_review_plan.v1',
          'automatic_execution_authority':'none','review_packets':[],'task_count':0}
    with pytest.raises(ValueError):
        merge_skillforge_evidence_into_review_plan(base,source)
