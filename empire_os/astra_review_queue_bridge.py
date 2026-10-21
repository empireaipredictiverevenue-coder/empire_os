"""Map ASTRA intelligence findings to the existing non-executable review packet contract."""
from __future__ import annotations
from collections.abc import Mapping
from empire_os.system_improvement_review import _common

OWNERS={'data_quant':'data_quant','sales_revenue':'sales_revenue','commercial_loop_source_owner':'engineering'}

def build_review_packets(report:Mapping)->list[dict]:
    if report.get('schema_version')!='empire.astra.unified_intelligence_review.v1' or report.get('mode')!='OBSERVE' or report.get('execution_authority')!='none':
        raise ValueError('untrusted ASTRA review authority')
    if report.get('campaign_activation_authorized') is not False or report.get('outbound_authorized') is not False:
        raise ValueError('review-only authority required')
    result={}
    for action in report.get('owner_actions') or []:
        if not isinstance(action,Mapping):continue
        raw_owner=action.get('owner')
        if raw_owner not in OWNERS or action.get('status') not in ('HOLD','REVIEW_REQUIRED'):continue
        owner=OWNERS[raw_owner]
        key='astra_unified|'+str(raw_owner)
        item={**_common(key,'ASTRA_EVIDENCE_REVIEW',owner),
              'source_owner':raw_owner,
              'workstream':'astra_unified_intelligence',
              'priority':'P1',
              'finding':'EVIDENCE_RECONCILIATION_REQUIRED',
              'next_review_action':str(action.get('action') or '')[:300],
              'source_schema':report['schema_version'],
              'references':['ASTRA_UNIFIED_INTELLIGENCE_REVIEW'],
              'independent_owner_verification_required':True,
              'founder_gate_required_before_consequential_action':True}
        result[item['task_id']]=item
    # Reuse the existing ASTRA review queue for pinned Harness²/SkillForge
    # evidence. This is not a Department work item and is never approved by
    # passing a numeric benchmark or by merely executing a deterministic replay.
    candidate=report.get('harness2_skillforge_candidate')
    if (isinstance(candidate,Mapping)
            and candidate.get('schema_version') ==
                'empire.skillforge.harness2_candidate_review.v1'
            and candidate.get('candidate_id') == 'empire-harness2-evidence-guard-v1'
            and candidate.get('status') == 'REVIEW_REQUIRED_REPLAY_EVIDENCE_VERIFIED'
            and candidate.get('source_replay_present_and_consistent') is True
            and candidate.get('independent_real_agent_completions') == 0
            and candidate.get('independent_holdout_verified') is False
            and candidate.get('approved') is False
            and candidate.get('skill_available_to_agents') is False
            and candidate.get('release_allowed') is False
            and candidate.get('execution_authority') == 'none'):
        key='astra_unified|harness2|evidence_guard_skillforge'
        item={**_common(key,'ASTRA_HARNESS2_SKILL_REVIEW','engineering'),
              'workstream':'skillforge_harness2_evidence_guard',
              'priority':'P1',
              'finding':'REPLAY_EVIDENCE_CONFIRMED_INDEPENDENT_HOLDOUT_MISSING',
              'source_schema': candidate['schema_version'],
              'next_review_action':
                  'Run two independent authorized agent completions and blinded holdouts before considering a digest-approved SkillForge skill',
              'harness2_candidate_id':candidate['candidate_id'],
              'original_evidence_task_count': candidate.get('original_evidence_tasks'),
              'source_replay_verified':True,
              'independent_owner_verification_required':True,
              'founder_gate_required_before_consequential_action':True,
              'references':['HARNESS2_REAL_EVIDENCE_REPLAY',
                            'SKILLFORGE_REVIEW_ONLY_CANDIDATE']}
        result[item['task_id']]=item
    benchmark=report.get('synthetic_campaign_benchmark')
    if isinstance(benchmark,Mapping):
        harness=benchmark.get('harness_comparison')
        if (isinstance(harness,Mapping)
                and harness.get('schema_version')=='empire.astra.harness2_evaluation.v1'
                and harness.get('mode')=='OBSERVE'
                and harness.get('automated_adoption') is False
                and harness.get('model_generated_code_executed') is False
                and benchmark.get('source')=='SYNTHETIC_FIXTURES_ONLY'):
            key='astra_unified|harness2|campaign_qualification'
            item={**_common(key,'ASTRA_HARNESS2_CANDIDATE_REVIEW','engineering'),
                  'workstream':'astra_unified_intelligence',
                  'priority':'P1',
                  'finding':'SYNTHETIC_BENCHMARK_NOT_LIVE_PERFORMANCE',
                  'next_review_action':'Independently retest guardrail and skill candidates against authorised original campaign evidence',
                  'source_schema':harness['schema_version'],
                  'harness2_inspired_evaluator':True,
                  'google_harness2_runtime_executed':False,
                  'independent_owner_verification_required':True,
                  'founder_gate_required_before_consequential_action':True,
                  'references':['ASTRA_UNIFIED_INTELLIGENCE_REVIEW']}
            result[item['task_id']]=item
    return list(result.values())

def merge_into_review_plan(existing:Mapping, astra:Mapping)->dict:
    if existing.get('schema')!='empire.system_improvement_review_plan.v1' or existing.get('automatic_execution_authority')!='none':
        raise ValueError('invalid existing ASTRA review plan')
    seen={p['task_id']:p for p in existing.get('review_packets',[]) if isinstance(p,Mapping) and isinstance(p.get('task_id'),str)}
    for packet in build_review_packets(astra):
        if packet['task_id'] in seen and seen[packet['task_id']]!=packet:
            raise ValueError('review identity collision; owner review required')
        seen[packet['task_id']]=packet
    return {**existing,'review_packets':list(seen.values()),'task_count':len(seen),
            'department_work_queue_mutated':False,'automatic_execution_authority':'none',
            'auto_dispatch_eligible':False}


def merge_skillforge_evidence_into_review_plan(existing:Mapping, source:Mapping)->dict:
    """Reuse isolated review packets for unproved repeated techniques.

    The counts are source-reference strings and canonical DONE rows, NEVER
    independent successful agent outcomes or permissions to promote skills.
    """
    from empire_os.skillforge_learning import SAFE_COMPONENT
    if (existing.get('schema')!='empire.system_improvement_review_plan.v1'
        or existing.get('automatic_execution_authority')!='none'
        or source.get('schema_version')!='empire.skillforge.independent_evidence_review.v1'
        or source.get('mode')!='OBSERVE'
        or source.get('status')!='SOURCE_DIVERSITY_REVIEW_ONLY'
        or source.get('execution_authority')!='none'
        or source.get('promotion_ready_skill_count')!=0
        or source.get('independently_authenticated_source_events')!=0
        or source.get('independently_verified_skill_outcomes')!=0
        or source.get('raw_identifiers_disclosed') is not False
        or source.get('automatic_promotion') is not False
        or source.get('inventory_truncated') is not False
        or source.get('coder_downstream_job_inventory_incomplete') is not False
        or source.get('original_skillforge_invalid_observations')!=0
        or source.get('second_read_rejected_observations')!=0):
        raise ValueError('unsafe or incomplete SkillForge provenance review')
    families=source.get('families')
    if not isinstance(families,list) or len(families)>16 or source.get('family_count')!=len(families):
        raise ValueError('invalid SkillForge family review set')
    replay=source.get('coder_current_revision_replay')
    replay_status='NOT_AVAILABLE'
    replay_test_files=0
    if replay is not None:
        if (not isinstance(replay,Mapping)
            or replay.get('schema_version')!='empire.skillforge.coder_replay_review.v1'
            or replay.get('skillforge_promotion_authorized') is not False
            or replay.get('automatic_dispatch_authorized') is not False
            or replay.get('independently_verified_code_implementations')!=0
            or replay.get('historical_source_revision_reproduced') is not False
            or replay.get('recorded_replay_attested_by_independent_owner') is not False
            or replay.get('execution_authority')!='none'):
            raise ValueError('invalid current-revision test replay evidence')
        replay_status=replay.get('status')
        if replay_status=='PINNED_CURRENT_REVISION_TEST_REPLAY_REVIEW_ONLY':
            if (replay.get('recorded_current_revision_tests_passed') is not True
                or replay.get('recorded_test_files')!=3
                or replay.get('distinct_historical_coder_plans')!=2):
                raise ValueError('unsafe recorded current-revision replay proof')
            replay_test_files=3
        elif replay.get('recorded_current_revision_tests_passed') is not False:
            raise ValueError('non-pinned replay cannot claim pass')
    source_patch=source.get('coder_original_patch_provenance')
    source_patch_status="NOT_AVAILABLE"
    source_patch_missing=0
    if source_patch is not None:
        if (not isinstance(source_patch,Mapping)
            or source_patch.get('schema_version')!='empire.skillforge.coder_patch_provenance_review.v1'
            or source_patch.get('auto_skill_approval_authorized') is not False
            or source_patch.get('independent_implementation_verified') is not False
            or source_patch.get('historical_source_revision_reproduced') is not False
            or source_patch.get('original_git_commit_path_matches')!=0
            or source_patch.get('execution_authority')!='none'):
            raise ValueError('original patch provenance not owner approved')
        source_patch_status=source_patch.get('status')
        if source_patch_status=="PINNED_ORIGINAL_PATCH_PROVENANCE_HOLD":
            if source_patch.get('original_jobs_missing_implementation_commit')!=2:
                raise ValueError('unexpected historical patch provenance')
            source_patch_missing=2
        elif source_patch.get('original_jobs_missing_implementation_commit')!=0:
            raise ValueError('untrusted missing commit observation')
    packets={row['task_id']:row for row in existing.get('review_packets',[])
             if isinstance(row,Mapping) and isinstance(row.get('task_id'),str)}
    for family in families:
        if not isinstance(family,Mapping):
            raise ValueError('invalid original source family')
        component=family.get('component')
        adapter=family.get('adapter')
        if (not isinstance(component,str) or not SAFE_COMPONENT.fullmatch(component)
            or not isinstance(adapter,str) or not SAFE_COMPONENT.fullmatch(adapter)):
            raise ValueError('invalid technique identity')
        count=family.get('canonical_done_observation_count')
        refs=family.get('distinct_evidence_reference_string_count')
        if (type(count) is not int or count<1 or count>5000
            or type(refs) is not int or refs<1 or refs>count*20
            or family.get('independently_verified_successful_agent_outcomes')!=0
            or family.get('original_referenced_artifacts_independently_authenticated') is not False
            or family.get('skill_approval_authorized') is not False
            or family.get('review_only') is not True):
            raise ValueError('untrusted SkillForge candidate evidence')
        correlated=family.get('original_coder_plan_scheduler_pairs_correlated',0)
        uncorrelated=family.get('original_coder_plan_scheduler_pairs_uncorrelated',0)
        failed=family.get('original_coder_plan_jobs_failed',0)
        failure_reasons=family.get('original_coder_plan_failure_reason_counts',{})
        if (type(correlated) is not int or type(uncorrelated) is not int
            or type(failed) is not int
            or correlated<0 or uncorrelated<0 or failed<0
            or correlated+uncorrelated+failed>(count)
            or family.get('independently_verified_code_implementations',0)!=0):
            raise ValueError('untrusted Coder scheduler evidence count')
        if (component=='empire_coder'
            and correlated+uncorrelated+failed != count):
            raise ValueError('incomplete Coder scheduler observation audit')
        allowed_failure_codes={
            'NO_HEALTHY_ELIGIBLE_MODEL_ROUTE',
            'MODEL_PROVIDER_NOT_CONFIGURED',
            'WORKSPACE_PATH_POLICY_REJECTION',
            'OTHER_FAILED_CODER_PLAN_JOB',
        }
        downstream=family.get('downstream_coder_verify_jobs')
        required_outcome_keys={
            'completed_verify_job_receipts',
            'completed_verify_report_pass',
            'completed_verify_report_fail',
            'completed_verify_pass_with_internal_test_receipt',
            'completed_verify_pass_without_sufficient_test_receipt',
            'internal_test_receipts_all_named_test_paths_present',
            'internal_test_receipts_one_or_more_test_paths_missing',
            'failed_verify_job_receipts',
            'untrusted_or_inconsistent_verify_job_receipts',
        }
        if (not isinstance(downstream,Mapping)
            or set(downstream)!=required_outcome_keys
            or any(type(value) is not int or value<0 or value>15000
                   for value in downstream.values())
            or (downstream['completed_verify_report_pass']+
                downstream['completed_verify_report_fail'] !=
                downstream['completed_verify_job_receipts'])
            or (downstream['completed_verify_pass_with_internal_test_receipt']+
                downstream['completed_verify_pass_without_sufficient_test_receipt'] !=
                downstream['completed_verify_report_pass'])
            or (downstream['internal_test_receipts_all_named_test_paths_present']+
                downstream['internal_test_receipts_one_or_more_test_paths_missing'] !=
                downstream['completed_verify_pass_with_internal_test_receipt'])
            or family.get('verify_report_pass_is_not_independent_outcome_proof') is not True
            or family.get('test_path_availability_is_not_test_reexecution') is not True):
            raise ValueError('untrusted original Coder VERIFY evidence')
        if (component!='empire_coder'
            and (correlated or uncorrelated or failed or any(downstream.values()))):
            raise ValueError('Coder-only evidence on unrelated skill family')
        if (not isinstance(failure_reasons,Mapping)
            or len(failure_reasons)>4
            or any(code not in allowed_failure_codes or type(n) is not int
                   or n<1 for code,n in failure_reasons.items())
            or sum(failure_reasons.values())!=failed):
            raise ValueError('untrusted Coder PLAN job failure diagnosis')
        if count<2:continue
        key='skillforge|provenance|'+component+'|'+adapter
        item={
            **_common(key,'SKILLFORGE_ORIGINAL_PROVENANCE_REVIEW','engineering'),
            'workstream':'skillforge_original_source_independence',
            'priority':'P1' if refs<=1 else 'P2',
            'finding':('REPEATED_WORK_USES_SHARED_EVIDENCE_REFERENCE'
                       if refs<=1 else 'MULTIPLE_SOURCE_REFERENCES_NOT_AUTHENTICATED'),
            'component':component,'adapter':adapter,
            'canonical_done_observation_count':count,
            'distinct_evidence_reference_string_count':refs,
            'original_coder_plan_scheduler_pairs_correlated':correlated,
            'original_coder_plan_scheduler_pairs_uncorrelated':uncorrelated,
            'original_coder_plan_jobs_failed':failed,
            'original_coder_plan_failure_reason_counts':dict(sorted(failure_reasons.items())),
            'department_done_is_not_coder_job_success':True,
            'downstream_coder_verify_jobs':dict(downstream),
            'verify_report_pass_is_not_independent_outcome_proof':True,
            'test_path_availability_is_not_test_reexecution':True,
            'current_revision_replay_status':(
                replay_status if component=='empire_coder' else 'NOT_APPLICABLE'),
            'current_revision_replay_fixed_test_file_count':(
                replay_test_files if component=='empire_coder' else 0),
            'current_revision_replay_is_not_historical_implementation_proof':True,
            'original_coder_patch_provenance_status':(
                source_patch_status if component=='empire_coder' else 'NOT_APPLICABLE'),
            'historical_verify_receipts_missing_implementation_commits':(
                source_patch_missing if component=='empire_coder' else 0),
            'independently_verified_code_implementations':0,
            'source_schema':source['schema_version'],
            'next_review_action':(
                'Independently retrieve original source events for separate work completions; '
                'verify provenance, outcome, blind holdouts and negative cases before skill approval'),
            'independent_owner_verification_required':True,
            'founder_gate_required_before_consequential_action':True,
            'references':['CANONICAL_DEPARTMENT_DONE_OBSERVATIONS',
                          'SKILLFORGE_SOURCE_DIVERSITY_AUDIT'],
        }
        if item['task_id'] in packets and packets[item['task_id']]!=item:
            raise ValueError('review identity collision; manual owner review required')
        packets[item['task_id']]=item
    return {**existing,'review_packets':list(packets.values()),
            'task_count':len(packets),'auto_dispatch_eligible':False,
            'department_work_queue_mutated':False,
            'automatic_execution_authority':'none'}
