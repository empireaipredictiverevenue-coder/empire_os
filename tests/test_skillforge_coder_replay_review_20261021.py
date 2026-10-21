"""Pinned review evidence cannot grant reusable-skill or execution authority."""
from pathlib import Path
import json
import shutil
from empire_os.skillforge_coder_replay_review import (
    PINNED_REPLAY,read_pinned_coder_replay,
)
from empire_os.skillforge import catalogue

ROOT=Path(__file__).resolve().parents[1]


def test_original_pinned_replay_matches_exact_committed_test_source():
    r=read_pinned_coder_replay(ROOT)
    assert r['status']=='PINNED_CURRENT_REVISION_TEST_REPLAY_REVIEW_ONLY'
    assert r['recorded_current_revision_tests_passed'] is True
    assert r['recorded_test_files']==3
    assert r['distinct_historical_coder_plans']==2
    assert len(r['source_receipt_sha256'])==64
    assert r['recorded_replay_attested_by_independent_owner'] is False
    assert r['historical_source_revision_reproduced'] is False
    assert r['skillforge_promotion_authorized'] is False
    assert r['automatic_dispatch_authorized'] is False
    assert r['independently_verified_code_implementations']==0


def test_skillforge_catalogue_includes_replay_without_approval():
    c=catalogue(root=ROOT/'empire_os/skills_library/skills',repo_root=ROOT)
    data=c['coder_current_revision_replay']
    assert data['status']=='PINNED_CURRENT_REVISION_TEST_REPLAY_REVIEW_ONLY'
    assert c['execution_authority']=='none'
    assert data['execution_authority']=='none'
    assert data['skillforge_promotion_authorized'] is False


def _copy_receipt(root):
    out=root/PINNED_REPLAY
    out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/PINNED_REPLAY,out)
    return out


def test_missing_current_replay_does_not_create_success(tmp_path):
    report=read_pinned_coder_replay(tmp_path)
    assert report['status']=='REPLAY_NOT_INSTALLED'
    assert report['recorded_current_revision_tests_passed'] is False
    assert report['skillforge_promotion_authorized'] is False


def test_symlinked_current_replay_is_rejected(tmp_path):
    dest=tmp_path/PINNED_REPLAY
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.symlink_to(ROOT/PINNED_REPLAY)
    assert read_pinned_coder_replay(tmp_path)['status']=='REPLAY_TAMPER_OR_UNSAFE_ARTIFACT'


def test_altered_verdict_cannot_promote_when_evidence_changed(tmp_path):
    path=_copy_receipt(tmp_path)
    info=json.loads(path.read_text())
    info['skillforge_promotion_authorized']=True
    info['historical_source_revision_reproduced']=True
    path.write_text(json.dumps(info))
    result=read_pinned_coder_replay(tmp_path)
    assert result['status']=='REPLAY_TAMPER_OR_UNSAFE_ARTIFACT'
    assert result['recorded_current_revision_tests_passed'] is False
    assert result['skillforge_promotion_authorized'] is False


def test_forged_test_sha256_is_rejected(tmp_path):
    path=_copy_receipt(tmp_path)
    obj=json.loads(path.read_text())
    first=obj['fixed_test_files'][0]
    obj['current_test_file_sha256'][first]='f'*64
    path.write_text(json.dumps(obj))
    assert read_pinned_coder_replay(tmp_path)['status']=='REPLAY_TAMPER_OR_UNSAFE_ARTIFACT'


def _synthetic_coder_review_family():
    """A bridge fixture, explicitly not real owner evidence."""
    return {
        'component':'empire_coder','adapter':'empire_coder_plan_bridge',
        'canonical_done_observation_count':2,
        'distinct_evidence_reference_string_count':4,
        'independently_verified_successful_agent_outcomes':0,
        'original_referenced_artifacts_independently_authenticated':False,
        'skill_approval_authorized':False,'review_only':True,
        'original_coder_plan_scheduler_pairs_correlated':2,
        'original_coder_plan_scheduler_pairs_uncorrelated':0,
        'original_coder_plan_jobs_failed':0,
        'original_coder_plan_failure_reason_counts':{},
        'independently_verified_code_implementations':0,
        'downstream_coder_verify_jobs':{
            'completed_verify_job_receipts':0,
            'completed_verify_report_pass':0,
            'completed_verify_report_fail':0,
            'completed_verify_pass_with_internal_test_receipt':0,
            'completed_verify_pass_without_sufficient_test_receipt':0,
            'internal_test_receipts_all_named_test_paths_present':0,
            'internal_test_receipts_one_or_more_test_paths_missing':0,
            'failed_verify_job_receipts':0,
            'untrusted_or_inconsistent_verify_job_receipts':0,
        },
        'verify_report_pass_is_not_independent_outcome_proof':True,
        'test_path_availability_is_not_test_reexecution':True,
    }


def test_existing_provenance_owner_queue_can_reference_pinned_replay():
    from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    evidence=review_independent_skill_evidence(ROOT)
    evidence['families']=[_synthetic_coder_review_family()]
    evidence['family_count']=1
    evidence['coder_current_revision_replay']=read_pinned_coder_replay(ROOT)
    old={'schema':'empire.system_improvement_review_plan.v1',
         'automatic_execution_authority':'none',
         'review_packets':[],'task_count':0}
    result=merge_skillforge_evidence_into_review_plan(old,evidence)
    coder=[x for x in result['review_packets'] if
           x.get('component')=='empire_coder']
    assert len(coder)==1
    row=coder[0]
    assert row['current_revision_replay_status']=='PINNED_CURRENT_REVISION_TEST_REPLAY_REVIEW_ONLY'
    assert row['current_revision_replay_fixed_test_file_count']==3
    assert row['current_revision_replay_is_not_historical_implementation_proof'] is True
    assert row['auto_dispatch_eligible'] is False
    assert row['approved_for_implementation'] is False
    assert result['department_work_queue_mutated'] is False


def test_spoofed_replay_approval_is_rejected_by_existing_queue():
    from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    evidence=review_independent_skill_evidence(ROOT)
    evidence['coder_current_revision_replay']={
        **read_pinned_coder_replay(ROOT),
        'skillforge_promotion_authorized':True,
    }
    old={'schema':'empire.system_improvement_review_plan.v1',
         'automatic_execution_authority':'none',
         'review_packets':[],'task_count':0}
    import pytest
    with pytest.raises(ValueError):
        merge_skillforge_evidence_into_review_plan(old,evidence)


def test_original_patch_provenance_audit_pinned_and_not_a_skill_approval():
    from empire_os.skillforge_coder_replay_review import read_pinned_coder_patch_provenance
    result=read_pinned_coder_patch_provenance(ROOT)
    assert result['status']=='PINNED_ORIGINAL_PATCH_PROVENANCE_HOLD'
    assert result['original_jobs_missing_implementation_commit']==2
    assert result['original_git_commit_path_matches']==0
    assert result['independent_implementation_verified'] is False
    assert result['auto_skill_approval_authorized'] is False
    assert result['historical_source_revision_reproduced'] is False
    assert result['execution_authority']=='none'
    assert 'commit SHA' in result['missing_owner_evidence_requirement']


def test_catalogue_exposes_original_git_gap_with_zero_promotion():
    from empire_os.skillforge_coder_replay_review import read_pinned_coder_patch_provenance
    r=read_pinned_coder_patch_provenance(ROOT)
    c=catalogue(root=ROOT/'empire_os/skills_library/skills',repo_root=ROOT)
    assert c['coder_original_patch_provenance']==r
    assert c['approved_count']==0


def test_modified_original_provenance_receipt_holds(tmp_path):
    from empire_os.skillforge_coder_replay_review import (
        PINNED_PATCH_PROVENANCE,read_pinned_coder_patch_provenance,
    )
    path=tmp_path/PINNED_PATCH_PROVENANCE
    path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/PINNED_PATCH_PROVENANCE,path)
    data=json.loads(path.read_text())
    data['independent_code_implementations_verified']=2
    data['skillforge_auto_approval']=True
    path.write_text(json.dumps(data))
    report=read_pinned_coder_patch_provenance(tmp_path)
    assert report['status']=='PINNED_ORIGINAL_PATCH_PROVENANCE_TAMPER_HOLD'
    assert report['auto_skill_approval_authorized'] is False
    assert report['independent_implementation_verified'] is False


def test_symlink_patch_receipt_cannot_be_trusted(tmp_path):
    from empire_os.skillforge_coder_replay_review import (
        PINNED_PATCH_PROVENANCE,read_pinned_coder_patch_provenance,
    )
    link=tmp_path/PINNED_PATCH_PROVENANCE
    link.parent.mkdir(parents=True,exist_ok=True)
    link.symlink_to(ROOT/PINNED_PATCH_PROVENANCE)
    r=read_pinned_coder_patch_provenance(tmp_path)
    assert r['status']=='PINNED_ORIGINAL_PATCH_PROVENANCE_TAMPER_HOLD'
    assert r['original_git_commit_path_matches']==0


def test_existing_engineering_review_carries_missing_commit_requirement():
    from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
    from empire_os.skillforge_coder_replay_review import (
        read_pinned_coder_patch_provenance,
    )
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    evidence=review_independent_skill_evidence(ROOT)
    evidence['families']=[_synthetic_coder_review_family()]
    evidence['family_count']=1
    evidence['coder_current_revision_replay']=read_pinned_coder_replay(ROOT)
    evidence['coder_original_patch_provenance']=read_pinned_coder_patch_provenance(ROOT)
    base={'schema':'empire.system_improvement_review_plan.v1',
          'automatic_execution_authority':'none',
          'review_packets':[],'task_count':0}
    merged=merge_skillforge_evidence_into_review_plan(base,evidence)
    coder=[x for x in merged['review_packets']
           if x.get('component')=='empire_coder']
    assert len(coder)==1
    packet=coder[0]
    assert packet['original_coder_patch_provenance_status']=='PINNED_ORIGINAL_PATCH_PROVENANCE_HOLD'
    assert packet['historical_verify_receipts_missing_implementation_commits']==2
    assert packet['independently_verified_code_implementations']==0
    assert packet['auto_dispatch_eligible'] is False
    assert packet['approved_for_implementation'] is False


def test_review_cannot_accept_forged_patch_provenance_approval():
    import pytest
    from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
    from empire_os.skillforge_coder_replay_review import read_pinned_coder_patch_provenance
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    evidence=review_independent_skill_evidence(ROOT)
    evidence['families']=[_synthetic_coder_review_family()]
    evidence['family_count']=1
    evidence['coder_original_patch_provenance']={
        **read_pinned_coder_patch_provenance(ROOT),
        'independent_implementation_verified':True,
    }
    base={'schema':'empire.system_improvement_review_plan.v1',
          'automatic_execution_authority':'none',
          'review_packets':[],'task_count':0}
    with pytest.raises(ValueError):
        merge_skillforge_evidence_into_review_plan(base,evidence)
