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
