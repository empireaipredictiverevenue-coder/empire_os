"""Fail-closed independent review coordinator tests."""
from __future__ import annotations

from copy import deepcopy
import pytest
from empire_os.factory_hybrid_review_v1 import (
    assess_held_review, BLOCK, CANDIDATE, NOT_READY, REVIEWED,
    REPAIR, ESCALATE, FOUNDER,
)


def fixture():
    gate = dict(schema_version='empire.execution-plane-candidate-gate.v1',
                proposal_branch='agent/work-42', candidate_gate_passed=True,
                awaiting_promptfoo=False, promptfoo_required=False,
                candidate_verification={'passed': True, 'candidate_patch_path': 'patch'},
                production_promotion_allowed=False, execution_authority='none')
    hold = dict(schema_version='empire.hybrid_factory_worker_guard.v1',
                enforced=True, disposition='READY_FOR_INDEPENDENT_REVIEW',
                department_work_done=False, request_id='work-42')
    bridge = dict(adapter='agent_tool_execution_plane', hybrid_factory=hold,
                  implementation_performed=False, external_execution_performed=False,
                  execution_authority='none',
                  dispatch=dict(request_id='work-42', status='CANDIDATE_GATE_PASSED',
                                proposal_gate=gate, production_deploy=False,
                                external_send=False, payment_action=False,
                                revenue_recognition=False, execution_authority='none'))
    item = dict(id='work-42', target_component='agent_tool_execution_plane',
                status='BLOCKED', authority='internal_write', error='hybrid_factory_ready_for_independent_review',
                lease_id=None, worker_id=None, result=bridge)
    request = dict(request_id='work-42', proposal_branch='agent/work-42', authority='internal_write',
                   risk_class='low', founder_gate_required=False, builder_id='builder-a',
                   persona_id='backend', soul_id='soul:backend:v1')
    self_review = dict(builder_id='builder-a', proposal_branch='agent/work-42',
                       passed=True, evidence_ref='self-ref')
    independent_review = dict(reviewer_id='different-b', proposal_branch='agent/work-42',
                              advisory_only=True, verdict='PASS', evidence_ref='review-ref')
    return dict(work_item=item, quality_request=request,
                self_review=self_review, independent_review=independent_review)


def verdict(d):
    result=assess_held_review(**d).as_dict()
    for key in ('queue_mutated', 'department_work_done', 'execution_completed',
                'production_merge','production_deploy','external_send','payment_action','revenue_recognition'):
        assert result[key] is False
    assert result['execution_authority']=='none'
    return result['status']


def test_complete_model_review_never_finalizes():
    assert verdict(fixture()) == REVIEWED


def test_missing_review_evidence_waits():
    d=fixture(); d.pop('quality_request')
    assert verdict(d) == CANDIDATE


def test_no_independent_review_waits():
    d=fixture(); d.pop('independent_review')
    assert verdict(d)==CANDIDATE


def test_self_review_failure_needs_repair():
    d=fixture(); d['self_review']['passed']=False
    assert verdict(d)==REPAIR


def test_self_certification_blocks():
    d=fixture(); d['independent_review']['reviewer_id']='builder-a'
    assert verdict(d)==BLOCK


def test_wrong_attestation_branch_blocks():
    d=fixture(); d['independent_review']['proposal_branch']='other'
    assert verdict(d)==BLOCK


def test_quality_request_bound_to_record():
    d=fixture(); d['quality_request']['request_id']='other'
    assert verdict(d)==BLOCK


def test_quality_authority_bound_to_record():
    d=fixture(); d['quality_request']['authority']='observe'
    assert verdict(d)==BLOCK


def test_council_escalated_on_high_risk():
    d=fixture(); d['quality_request']['risk_class']='high'
    assert verdict(d)==ESCALATE


def test_high_risk_council_recommendation_never_deploys():
    d=fixture(); d['quality_request']['risk_class']='high'
    d['council_result'] = dict(status='RECOMMEND_APPROVE', proposal_branch='agent/work-42',
                               voter_ids=['architect','security'], evidence_ref='council-ref')
    assert verdict(d)==REVIEWED


def test_founder_gate_holds():
    d=fixture(); d['quality_request']['founder_gate_required']=True
    assert verdict(d)==FOUNDER


@pytest.mark.parametrize('field,value', [
    ('id','not-this-work'), ('target_component','identity_enrichment'),
    ('status','DONE'), ('status','RUNNING'), ('lease_id','active-lease'),
    ('worker_id','active-worker'), ('error','mismatched_reason'),
])
def test_record_integrity_checks(field,value):
    d=fixture(); d['work_item'][field]=value
    assert verdict(d) != REVIEWED


@pytest.mark.parametrize('field,value', [
    ('schema_version','incorrect'), ('enforced',False),
    ('department_work_done',True), ('request_id','wrong'),
    ('disposition','WAITING_FOR_EVIDENCE'),
])
def test_hold_integrity(field,value):
    d=fixture(); d['work_item']['result']['hybrid_factory'][field]=value
    assert verdict(d) != REVIEWED


@pytest.mark.parametrize('field,value', [
    ('request_id','wrong'), ('status','QUEUED'),
    ('execution_authority','internal_write'),
])
def test_dispatch_integrity(field,value):
    d=fixture(); d['work_item']['result']['dispatch'][field]=value
    assert verdict(d) != REVIEWED


def test_review_state_supported_but_not_done():
    d=fixture(); d['work_item']['status']='REVIEW'; d['work_item']['error']=None
    assert verdict(d)==REVIEWED


def test_promptfoo_required_requires_finished_workflow():
    d=fixture(); d['work_item']['result']['dispatch']['proposal_gate']['promptfoo_required']=True
    assert verdict(d)==NOT_READY


def test_unknown_work_id_fails_closed():
    d=fixture(); d['work_item']['id']='../escape'
    assert verdict(d)==BLOCK
