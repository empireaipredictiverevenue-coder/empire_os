from __future__ import annotations
from types import SimpleNamespace
from copy import deepcopy
import pytest
from empire_os.factory_hybrid_review_intake_v1 import validate_review_intake, ReviewIntakeError
from test_factory_hybrid_review_v1 import fixture


def example():
    d=fixture(); item = SimpleNamespace(id='work-42', target_component='agent_tool_execution_plane')
    return item, d['work_item']['result']


def test_passed_candidate_can_only_enter_review():
    item, result = example()
    assert validate_review_intake(item, result) is None


@pytest.mark.parametrize('field,value', [
    ('disposition', 'WAITING_FOR_EVIDENCE'),('schema_version','fake'),
    ('department_work_done',True),('enforced',False),('request_id','wrong')
])
def test_invalid_hold_rejected(field,value):
    item,result=example();result['hybrid_factory'][field]=value
    with pytest.raises(ReviewIntakeError): validate_review_intake(item,result)


@pytest.mark.parametrize('field,value', [
    ('status','QUEUED'),('request_id','bad'),('production_deploy',True),
    ('payment_action',True),('execution_authority','internal_write'),
])
def test_bad_dispatch_rejected(field,value):
    item,result=example();result['dispatch'][field]=value
    with pytest.raises(ReviewIntakeError): validate_review_intake(item,result)


@pytest.mark.parametrize('field,value', [
    ('candidate_gate_passed',False),('promptfoo_required',True),('awaiting_promptfoo',True),
    ('production_promotion_allowed',True),('execution_authority','write'),
])
def test_bad_candidate_gate_rejected(field,value):
    item,result=example();result['dispatch']['proposal_gate'][field]=value
    with pytest.raises(ReviewIntakeError): validate_review_intake(item,result)


def test_candidate_verification_failure_rejected():
    item,result=example();result['dispatch']['proposal_gate']['candidate_verification']['passed']=False
    with pytest.raises(ReviewIntakeError): validate_review_intake(item,result)


def test_wrong_target_rejected():
    item,result=example();item.target_component='empire_coder'
    with pytest.raises(ReviewIntakeError): validate_review_intake(item,result)


def test_builder_claiming_implementation_rejected():
    item,result=example();result['implementation_performed']=True
    with pytest.raises(ReviewIntakeError): validate_review_intake(item,result)
