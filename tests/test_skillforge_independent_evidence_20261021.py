"""Original work reference diversity is evidence for review, NOT skill success."""
from pathlib import Path
import json
import pytest

from empire_os.skillforge_learning import capture_completed_work
from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
from empire_os.skillforge import catalogue


def done(root:Path, number:int, *, ref='runtime:shared:latest',
         plan='plan-a', adapter='original_source_review'):
    work_id='dept_work_'+f'{number:024x}'
    p=root/'runtime/departments/work/done'/f'{work_id}.json'
    p.parent.mkdir(parents=True,exist_ok=True)
    item={
        'id':work_id,'status':'DONE','authority':'observe','error':None,
        'target_component':'source_intelligence_review',
        'result':{'adapter':adapter,'execution_authority':'none','returncode':0},
        'result_evidence_refs':[ref],
        'plan_id':plan,'goal_key':'safe-goal',
    }
    p.write_text(json.dumps(item))
    assert capture_completed_work(root,work_id)['status']=='candidate_saved'
    return p


def family(result):
    assert len(result['families'])==1
    return result['families'][0]


def test_independent_work_count_does_not_infer_independent_source_events(tmp_path):
    done(tmp_path,1,ref='runtime:one:latest',plan='plan-1')
    done(tmp_path,2,ref='runtime:one:latest',plan='plan-2')
    done(tmp_path,3,ref='runtime:one:latest',plan='plan-3')
    result=review_independent_skill_evidence(tmp_path)
    row=family(result)
    assert result['canonical_observations_reviewed']==3
    assert row['distinct_canonical_work_count']==3
    assert row['distinct_plan_context_count']==3
    assert row['distinct_evidence_reference_string_count']==1
    assert row['reference_diversity_status']=='REUSED_SINGLE_REFERENCE_STRING'
    assert row['independently_verified_successful_agent_outcomes']==0
    assert row['skill_approval_authorized'] is False
    assert result['families_with_single_shared_reference']==1
    assert result['promotion_ready_skill_count']==0
    assert 'runtime:one:latest' not in json.dumps(result)


def test_distinct_source_reference_strings_are_not_authenticated_sources(tmp_path):
    done(tmp_path,1,ref='runtime:source:a')
    done(tmp_path,2,ref='runtime:source:b')
    review=review_independent_skill_evidence(tmp_path)
    row=family(review)
    assert row['distinct_evidence_reference_string_count']==2
    assert row['reference_diversity_status']=='MULTIPLE_REFERENCE_STRINGS_CUSTODY_UNVERIFIED'
    assert row['original_referenced_artifacts_independently_authenticated'] is False
    assert review['independently_authenticated_source_events']==0
    assert review['independently_verified_skill_outcomes']==0


def test_tampered_canonical_result_fails_closed(tmp_path):
    p=done(tmp_path,1)
    item=json.loads(p.read_text());item['result']['returncode']=5
    p.write_text(json.dumps(item))
    review=review_independent_skill_evidence(tmp_path)
    assert review['status']=='SOURCE_INTEGRITY_OR_COVERAGE_HOLD'
    assert review['original_skillforge_invalid_observations']==1
    assert review['canonical_observations_reviewed']==0
    assert review['promotion_ready_skill_count']==0


def test_recheck_rejects_changes_between_primary_audit_and_second_read(tmp_path,monkeypatch):
    p=done(tmp_path,1)
    import empire_os.skillforge_independent_evidence as module
    original=module._verified_learning_observations
    def hostile_change(root,*,max_observations):
        valid,invalid,truncated=original(root,max_observations=max_observations)
        item=json.loads(p.read_text());item['result_evidence_refs']=['runtime:fake']
        p.write_text(json.dumps(item))
        return valid,invalid,truncated
    monkeypatch.setattr(module,'_verified_learning_observations',hostile_change)
    review=review_independent_skill_evidence(tmp_path)
    assert review['second_read_rejected_observations']==1
    assert review['status']=='SOURCE_INTEGRITY_OR_COVERAGE_HOLD'


def test_bounded_incomplete_source_inventory_must_hold(tmp_path):
    done(tmp_path,1)
    done(tmp_path,2)
    report=review_independent_skill_evidence(tmp_path,max_observations=1)
    assert report['inventory_truncated'] is True
    assert report['status']=='SOURCE_INTEGRITY_OR_COVERAGE_HOLD'


def test_directory_symlink_is_not_a_source(tmp_path):
    done(tmp_path,1)
    actual=tmp_path/'runtime/departments/work/done'
    replacement=tmp_path/'old-done'
    actual.rename(replacement)
    actual.symlink_to(replacement,target_is_directory=True)
    with pytest.raises(ValueError):
        review_independent_skill_evidence(tmp_path)


@pytest.mark.parametrize('invalid',[0,5001,True,'5000'])
def test_invalid_limits_rejected(tmp_path,invalid):
    with pytest.raises(ValueError):
        review_independent_skill_evidence(tmp_path,max_observations=invalid)


def test_skillforge_catalogue_exposes_review_without_promotion(tmp_path):
    done(tmp_path,1)
    c=catalogue(root=tmp_path/'nothing',repo_root=tmp_path)
    d=c['independent_evidence_review']
    assert d['canonical_observations_reviewed']==1
    assert d['promotion_ready_skill_count']==0
    assert d['automatic_promotion'] is False
    assert c['approved_count']==0
    assert c['execution_authority']=='none'


def test_empty_repo_has_no_invented_skills(tmp_path):
    report=review_independent_skill_evidence(tmp_path)
    assert report['family_count']==0
    assert report['canonical_observations_reviewed']==0
    assert report['status']=='SOURCE_DIVERSITY_REVIEW_ONLY'


def _empty_resolution(root:Path):
    from empire_os.system_improvement_review import RESOLUTION
    file=root/RESOLUTION
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps({
        'schema':'empire.opportunity_evidence_resolution_shadow.v1',
        'execution_authority':'none',
        'normalized_scores_written':0,
        'factory_promotion_authorized':False,'items':[],
    }))


def test_existing_engineering_review_queue_gets_one_idempotent_source_task(tmp_path):
    from empire_os.system_improvement_review import refresh_review_packets
    _empty_resolution(tmp_path)
    done(tmp_path,1)
    done(tmp_path,2)
    a=refresh_review_packets(tmp_path)
    b=refresh_review_packets(tmp_path)
    matched=[x for x in a['packets']
             if x['type']=='SKILLFORGE_ORIGINAL_PROVENANCE_REVIEW']
    assert len(matched)==1
    assert a['task_count']==1
    assert b['task_count']==1
    assert b['new_or_changed_review_packets']==0
    assert b['department_work_queue_mutated'] is False
    packet=json.loads((tmp_path/matched[0]['path']).read_text())
    assert packet['finding']=='REPEATED_WORK_USES_SHARED_EVIDENCE_REFERENCE'
    assert packet['canonical_done_observation_count']==2
    assert packet['distinct_evidence_reference_string_count']==1
    assert packet['auto_dispatch_eligible'] is False
    assert packet['approved_for_implementation'] is False
    assert packet['allow_outbound'] is False
    assert packet['allow_payment'] is False
    assert packet['allow_db_migration'] is False
    assert not (tmp_path/'runtime/departments/work/ready').exists()


def test_missing_source_record_cannot_enter_existing_review(tmp_path):
    from empire_os.system_improvement_review import refresh_review_packets
    _empty_resolution(tmp_path)
    one=done(tmp_path,1)
    done(tmp_path,2)
    one.unlink()
    out=refresh_review_packets(tmp_path)
    assert not any(x['type']=='SKILLFORGE_ORIGINAL_PROVENANCE_REVIEW'
                   for x in out['packets'])
    assert out['department_work_queue_mutated'] is False


def test_untrusted_skillforge_review_report_cannot_spoof_approval():
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    old={'schema':'empire.system_improvement_review_plan.v1',
         'automatic_execution_authority':'none',
         'review_packets':[],'task_count':0}
    fake={
        'schema_version':'empire.skillforge.independent_evidence_review.v1',
        'mode':'OBSERVE','status':'SOURCE_DIVERSITY_REVIEW_ONLY',
        'execution_authority':'none',
        'promotion_ready_skill_count':0,
        'independently_authenticated_source_events':0,
        'independently_verified_skill_outcomes':0,
        'raw_identifiers_disclosed':False,'automatic_promotion':False,
        'inventory_truncated':False,
        'original_skillforge_invalid_observations':0,
        'second_read_rejected_observations':0,'family_count':1,
        'families':[{
          'component':'source_intelligence_review','adapter':'internal_review',
          'canonical_done_observation_count':2,
          'distinct_evidence_reference_string_count':1,
          'independently_verified_successful_agent_outcomes':0,
          'original_referenced_artifacts_independently_authenticated':False,
          'skill_approval_authorized':False,'review_only':True,
        }],
    }
    assert len(merge_skillforge_evidence_into_review_plan(old,fake)['review_packets'])==1
    for key,value in (
        ('promotion_ready_skill_count',1),
        ('independently_authenticated_source_events',3),
        ('automatic_promotion',True),
        ('inventory_truncated',True),
    ):
        fake[key]=value
        with pytest.raises(ValueError):
            merge_skillforge_evidence_into_review_plan(old,fake)
        fake[key]=0 if isinstance(value,int) and not isinstance(value,bool) else False
    fake['families'][0]['skill_approval_authorized']=True
    with pytest.raises(ValueError):
        merge_skillforge_evidence_into_review_plan(old,fake)


def coder_receipts(root, number=123):
    work_id='dept_work_'+f'{number:024x}'
    task_id='coder_'+f'{number:032x}'
    job_id='coder_job_'+f'{number:032x}'
    done_path=root/'runtime/departments/work/done'/f'{work_id}.json'
    done_path.parent.mkdir(parents=True,exist_ok=True)
    result={
        'adapter':'empire_coder_plan_bridge',
        'coder_task_id':task_id,'coder_job_id':job_id,
        'implementation_performed':False,
        'external_execution_performed':False,
        'execution_authority':'none',
    }
    done_path.write_text(json.dumps({
        'id':work_id,'status':'DONE','authority':'observe',
        'error':None,'target_component':'empire_coder',
        'result':result,
        'result_evidence_refs':[
            'coder_task:'+task_id,'coder_job:'+job_id,
        ],
    }))
    task=root/'runtime/coder/tasks'/f'{task_id}.json'
    job=root/'runtime/coder/jobs/completed'/f'{job_id}.json'
    task.parent.mkdir(parents=True,exist_ok=True)
    job.parent.mkdir(parents=True,exist_ok=True)
    task.write_text(json.dumps({'id':task_id,'status':'running'}))
    job.write_text(json.dumps({
        'id':job_id,'task_id':task_id,
        'status':'COMPLETED','kind':'PLAN','error':None,
        'payload':{'department_work_id':work_id,'execution_authority':'none'},
        'result':{
            'execution_authority':'none','external_execution_performed':False,
            'production_mutation':False,'stage':'REFINED',
        },
    }))
    assert capture_completed_work(root,work_id)['status']=='candidate_saved'
    return done_path,task,job


def test_coder_completed_plan_receipt_is_not_an_implementation(tmp_path):
    coder_receipts(tmp_path)
    review=review_independent_skill_evidence(tmp_path)
    data=family(review)
    assert data['original_coder_plan_scheduler_pairs_correlated']==1
    assert data['original_coder_plan_scheduler_pairs_uncorrelated']==0
    assert data['independently_verified_code_implementations']==0
    assert data['coder_plan_scheduler_correlation_is_not_implementation_proof'] is True
    assert review['promotion_ready_skill_count']==0


@pytest.mark.parametrize('tamper',[
    lambda task,job:task.unlink(),
    lambda task,job:job.unlink(),
    lambda task,job:job.write_text(json.dumps({
        **json.loads(job.read_text()),'task_id':'coder_'+'b'*32,
    })),
    lambda task,job:job.write_text(json.dumps({
        **json.loads(job.read_text()),'status':'FAILED',
    })),
    lambda task,job:job.write_text(json.dumps({
        **json.loads(job.read_text()),
        'result':{**json.loads(job.read_text())['result'],'production_mutation':True},
    })),
])
def test_coder_missing_failed_or_wrong_original_job_not_proven(tmp_path,tamper):
    _,task,job=coder_receipts(tmp_path)
    tamper(task,job)
    review=review_independent_skill_evidence(tmp_path)
    row=family(review)
    assert row['original_coder_plan_scheduler_pairs_correlated']==0
    assert row['original_coder_plan_scheduler_pairs_uncorrelated']==1
    assert row['independently_verified_code_implementations']==0
    assert review['status']=='SOURCE_DIVERSITY_REVIEW_ONLY'
    assert review['promotion_ready_skill_count']==0


def test_coder_original_symlink_cannot_be_counted(tmp_path):
    _,task,job=coder_receipts(tmp_path)
    copy=tmp_path/'fake-task'
    task.rename(copy)
    task.symlink_to(copy)
    data=family(review_independent_skill_evidence(tmp_path))
    assert data['original_coder_plan_scheduler_pairs_correlated']==0
    assert data['original_coder_plan_scheduler_pairs_uncorrelated']==1


def test_coder_scheduler_gaps_appear_only_in_nonexecuting_owner_review(tmp_path):
    from empire_os.system_improvement_review import refresh_review_packets
    _empty_resolution(tmp_path)
    coder_receipts(tmp_path,number=1)
    _,task,job=coder_receipts(tmp_path,number=2)
    job.unlink()
    result=refresh_review_packets(tmp_path)
    matched=[p for p in result['packets']
             if p['type']=='SKILLFORGE_ORIGINAL_PROVENANCE_REVIEW']
    assert len(matched)==1
    receipt=json.loads((tmp_path/matched[0]['path']).read_text())
    assert receipt['original_coder_plan_scheduler_pairs_correlated']==1
    assert receipt['original_coder_plan_scheduler_pairs_uncorrelated']==1
    assert receipt['independently_verified_code_implementations']==0
    assert receipt['auto_dispatch_eligible'] is False
    assert receipt['approved_for_implementation'] is False
