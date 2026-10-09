"""Adversarial and happy-path tests for dormant independent governor."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace, ModuleType
import sys
import importlib.util
import pytest
from test_factory_hybrid_review_v1 import fixture
from empire_os.factory_hybrid_review_finalizer_v1 import (
    assess_finalisation, load_root_attested_receipt, finalize_review_locked,
    FinalisationDenied, TRUST_ROOT, SCHEMA,
)


def assembled():
    d=fixture()
    item=deepcopy(d['work_item'])
    item['status']='REVIEW';item['error']=None
    raw=(json.dumps(item,sort_keys=True,separators=(',',':'))+'\n').encode()
    proof={
        'schema_version':SCHEMA,'work_id':'work-42',
        'review_record_sha256':hashlib.sha256(raw).hexdigest(),
        'issuer':'empire_root_review_governor',
        'decision':'APPROVED_WITH_RUNTIME_PROOF',
        'production_deploy':False,'production_merge':False,
        'external_send':False,'payment_action':False,
        'revenue_recognition':False,'execution_authority':'none',
        'quality_request':deepcopy(d['quality_request']),
        'self_review':deepcopy(d['self_review']),
        'independent_review':deepcopy(d['independent_review']),
        'candidate_commit':'a'*40,
        'runtime_proof':{
            'status':'PASS','work_id':'work-42','proposal_branch':'agent/work-42',
            'production_verified':True,'read_only_probe':True,
            'environment':'production','tests_passed':True,
            'simulated':False,'shadow_only':False,
            'verifier_id':'runtime-audit-c',
            'production_commit':'a'*40,
            'evidence_ref':'verified-runtime-42',
            'verified_at':datetime.now(timezone.utc).isoformat(),
        }
    }
    return item,raw,proof


def status(patch=None, *, item_patch=None, raw_patch=None):
    item, raw, receipt=assembled()
    if patch: patch(receipt)
    if item_patch: item_patch(item)
    if raw_patch: raw=raw_patch(raw)
    d=assess_finalisation(work_record=item,record_bytes=raw,receipt=receipt)
    for action in ('production_deploy','production_merge','external_send','payment_action','revenue_recognition'):
        assert d.as_dict()[action] is False
    assert d.as_dict()['execution_authority']=='none'
    return d


def test_full_root_receipt_semantically_eligible_not_a_deploy():
    result=status()
    assert result.allowed is True
    assert 'verified-runtime-42' in result.evidence_refs

@pytest.mark.parametrize('field,value',[
    ('schema_version','x'),('work_id','other'),
    ('review_record_sha256','0'*64),('issuer','agent'),
    ('decision','PASS'),('decision','RECOMMEND_APPROVE'),
    ('execution_authority','internal_write'),
    ('production_deploy',True),('production_merge',True),
    ('external_send',True),('payment_action',True),
    ('revenue_recognition',True),
])
def test_bad_receipt_blocks(field,value):
    result=status(lambda p:p.__setitem__(field,value))
    assert not result.allowed

@pytest.mark.parametrize('field,value',[
    ('status','DONE'),('status','BLOCKED'),('lease_id','lease'),
    ('worker_id','builder'),('id','../escape'),
])
def test_bad_review_state_blocks(field,value):
    result=status(item_patch=lambda item:item.__setitem__(field,value))
    assert not result.allowed

@pytest.mark.parametrize('field,value',[
    ('production_verified',False),('read_only_probe',False),
    ('status','QUEUED'),('environment','staging'),
    ('tests_passed',False),('simulated',True),
    ('shadow_only',True),('work_id','other'),
    ('proposal_branch','wrong'),('evidence_ref',''),
    ('production_commit','b'*40),('verifier_id','builder-a'),
    ('verifier_id','different-b'),
    ('verified_at','2020-01-01T00:00:00Z'),
])
def test_runtime_proof_invalid_blocks(field,value):
    result=status(lambda p:p['runtime_proof'].__setitem__(field,value))
    assert not result.allowed


def test_future_proof_blocks():
    result=status(lambda p:p['runtime_proof'].__setitem__('verified_at',
        (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()))
    assert not result.allowed


def test_decision_identity_never_bypasses_native_binding():
    result=status(item_patch=lambda item:item.__setitem__("decision_identity", {"shadow_only":False}))
    assert not result.allowed


def test_review_self_certification_blocks():
    result=status(lambda p:p['independent_review'].__setitem__('reviewer_id','builder-a'))
    assert not result.allowed


def test_founder_gate_prevents_completion():
    result=status(lambda p:p['quality_request'].__setitem__('founder_gate_required', True))
    assert not result.allowed


def test_council_required_for_high_risk():
    result=status(lambda p:p['quality_request'].__setitem__('risk_class','high'))
    assert not result.allowed


def test_high_risk_council_authenticated_data_remains_nonexecuting():
    def change(p):
        p['quality_request']['risk_class']='high'
        p['council_result']={'status':'RECOMMEND_APPROVE','proposal_branch':'agent/work-42',
                             'voter_ids':['architecture','security'],'evidence_ref':'council-42'}
    result=status(change)
    assert result.allowed


def test_missing_receipt_rejected():
    with pytest.raises(FinalisationDenied): load_root_attested_receipt('missing-work-42')


def test_path_traversal_rejected():
    with pytest.raises(FinalisationDenied): load_root_attested_receipt('../../etc/passwd')


def test_dormant_by_default():
    with pytest.raises(FinalisationDenied, match='not_enabled'):
        finalize_review_locked(SimpleNamespace(), 'work-42')


def test_unprivileged_cannot_finalize(monkeypatch):
    monkeypatch.setenv('EMPIRE_HYBRID_FACTORY_FINALISE_V1','1')
    monkeypatch.setattr(os,'geteuid',lambda:1000)
    with pytest.raises(FinalisationDenied,match='privileged'):
        finalize_review_locked(SimpleNamespace(),'work-42')


class MockQueue:
    def __init__(self, root, raw):
        self.ready=root/'ready';self.running=root/'running';self.review=root/'review'
        self.done=root/'done';self.blocked=root/'blocked';self.failed=root/'failed'
        for d in (self.ready,self.running,self.review,self.done,self.blocked,self.failed):d.mkdir()
        (self.review/'work-42.json').write_bytes(raw)
    def _locked(self):return nullcontext()
    def _safe(self, value):return value
    def _load(self, path):
        d=json.loads(path.read_bytes())
        return SimpleNamespace(**d)
    def _write(self, path, item):
        # Simplified repo serializer exercising update/move binding.
        path.write_text(json.dumps(item.__dict__,default=lambda o:o.value if isinstance(o,Enum) else o))


def test_root_only_flow_moves_review_to_done_without_execution(monkeypatch,tmp_path):
    item,raw,proof=assembled()
    mock=MockQueue(tmp_path,raw)
    monkeypatch.setenv('EMPIRE_HYBRID_FACTORY_FINALISE_V1','1')
    monkeypatch.setattr(os,'geteuid',lambda:0)
    mod=ModuleType('empire_os.department_work_queue')
    class DepartmentWorkStatus(Enum): DONE='DONE'
    mod.DepartmentWorkStatus=DepartmentWorkStatus
    monkeypatch.setitem(sys.modules,'empire_os.department_work_queue',mod)
    import empire_os.factory_hybrid_review_finalizer_v1 as f
    monkeypatch.setattr(f,'load_root_attested_receipt',lambda _:proof)
    changed=finalize_review_locked(mock,'work-42')
    assert changed.status==DepartmentWorkStatus.DONE
    assert not (mock.review/'work-42.json').exists()
    assert (mock.done/'work-42.json').exists()
    assert changed.result['production_deploy'] is False
    assert changed.result['execution_authority']=='none'
    assert changed.result['factory_finalisation']['allowed'] is True


def test_modified_review_record_refuses_move(monkeypatch,tmp_path):
    item,raw,proof=assembled()
    mock=MockQueue(tmp_path,raw)
    item['result']['extra']='tampered'
    (mock.review/'work-42.json').write_text(json.dumps(item))
    monkeypatch.setenv('EMPIRE_HYBRID_FACTORY_FINALISE_V1','1')
    monkeypatch.setattr(os,'geteuid',lambda:0)
    import empire_os.factory_hybrid_review_finalizer_v1 as f
    monkeypatch.setattr(f,'load_root_attested_receipt',lambda _:proof)
    with pytest.raises(FinalisationDenied,match='stale_or_modified'):
        finalize_review_locked(mock,'work-42')
    assert (mock.review/'work-42.json').is_file()
    assert not (mock.done/'work-42.json').exists()


def test_done_collision_refuses_move(monkeypatch,tmp_path):
    item,raw,proof=assembled()
    mock=MockQueue(tmp_path,raw)
    (mock.done/'work-42.json').write_text('already there')
    monkeypatch.setenv('EMPIRE_HYBRID_FACTORY_FINALISE_V1','1')
    monkeypatch.setattr(os,'geteuid',lambda:0)
    import empire_os.factory_hybrid_review_finalizer_v1 as f
    monkeypatch.setattr(f,'load_root_attested_receipt',lambda _:proof)
    with pytest.raises(FinalisationDenied,match='conflicting_done'):
        finalize_review_locked(mock,'work-42')
    assert (mock.review/'work-42.json').exists()
