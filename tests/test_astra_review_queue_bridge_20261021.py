import pytest
from empire_os.astra_review_queue_bridge import build_review_packets,merge_into_review_plan

def sample():
 return {'schema_version':'empire.astra.unified_intelligence_review.v1','mode':'OBSERVE','execution_authority':'none', 'campaign_activation_authorized':False,'outbound_authorized':False,'owner_actions':[{'owner':'data_quant','status':'HOLD','action':'Review forecast lineage'},{'owner':'sales_revenue','status':'REVIEW_REQUIRED','action':'Check replies'},{'owner':'data_quant','status':'HOLD','action':'Review forecast lineage'}]}
def test_repeat_dedup_and_queue_authority():
 p={'schema':'empire.system_improvement_review_plan.v1','automatic_execution_authority':'none','review_packets':[]}
 once=merge_into_review_plan(p,sample());twice=merge_into_review_plan(once,sample())
 assert once['task_count']==twice['task_count']==2
 assert all(not x['auto_dispatch_eligible'] for x in twice['review_packets'])
 assert not twice['department_work_queue_mutated']
def test_unsafe_report_rejected():
 r=sample();r['outbound_authorized']=True
 with pytest.raises(ValueError): build_review_packets(r)
def test_existing_task_preserved():
 p={'schema':'empire.system_improvement_review_plan.v1','automatic_execution_authority':'none','review_packets':[{'task_id':'existing'}]}
 assert merge_into_review_plan(p,sample())['task_count']==3

def test_harness_comparison_becomes_non_executable_review():
    r=sample()
    r['synthetic_campaign_benchmark']={
        'source':'SYNTHETIC_FIXTURES_ONLY',
        'harness_comparison':{
            'schema_version':'empire.astra.harness2_evaluation.v1',
            'mode':'OBSERVE','automated_adoption':False,
            'model_generated_code_executed':False,
        },
    }
    packets=build_review_packets(r)
    matched=[x for x in packets if x['task_type']=='ASTRA_HARNESS2_CANDIDATE_REVIEW']
    assert len(matched)==1
    assert matched[0]['google_harness2_runtime_executed'] is False
    assert matched[0]['auto_dispatch_eligible'] is False
    assert len(build_review_packets(r))==len(packets)

def test_harness2_skillforge_candidate_reuses_existing_nonexecuting_review_queue():
    r=sample()
    r['harness2_skillforge_candidate']={
        'schema_version':'empire.skillforge.harness2_candidate_review.v1',
        'candidate_id':'empire-harness2-evidence-guard-v1',
        'status':'REVIEW_REQUIRED_REPLAY_EVIDENCE_VERIFIED',
        'source_replay_present_and_consistent':True,
        'independent_real_agent_completions':0,
        'independent_holdout_verified':False,
        'approved':False,'skill_available_to_agents':False,
        'release_allowed':False,'execution_authority':'none',
        'original_evidence_tasks':2,
    }
    old={'schema':'empire.system_improvement_review_plan.v1',
         'automatic_execution_authority':'none','review_packets':[]}
    output=merge_into_review_plan(old,r)
    repeat=merge_into_review_plan(output,r)
    matched=[p for p in repeat['review_packets']
             if p['task_type']=='ASTRA_HARNESS2_SKILL_REVIEW']
    assert len(matched)==1
    assert matched[0]['original_evidence_task_count']==2
    assert matched[0]['auto_dispatch_eligible'] is False
    assert matched[0]['approved_for_implementation'] is False
    assert repeat['task_count']==output['task_count']
    assert repeat['department_work_queue_mutated'] is False

def test_harness2_skillforge_approval_spoof_cannot_enter_review():
    r=sample()
    r['harness2_skillforge_candidate']={
        'schema_version':'empire.skillforge.harness2_candidate_review.v1',
        'candidate_id':'empire-harness2-evidence-guard-v1',
        'status':'REVIEW_REQUIRED_REPLAY_EVIDENCE_VERIFIED',
        'source_replay_present_and_consistent':True,
        'independent_real_agent_completions':0,
        'independent_holdout_verified':False,
        'approved':True,'skill_available_to_agents':True,
        'release_allowed':True,'execution_authority':'none',
    }
    assert not any(p['task_type']=='ASTRA_HARNESS2_SKILL_REVIEW'
                   for p in build_review_packets(r))
