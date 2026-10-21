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
