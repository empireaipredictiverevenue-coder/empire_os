"""Revenue recognizer must not conflate matching payment with earned revenue.

No live DB, no payment, no actual revenue writes. Role RPC is mocked.
"""
from uuid import uuid4
import json
import pytest

from empire_os.outcome_role_transport import (
    OutcomeTransportError, PostgresOutcomeRpc,
)
from scripts import revenue_recognition_worker as worker

OID=str(uuid4())
OTHER=str(uuid4())


def work(*, matches=True, price=19900, direct=True):
    return {
        "fulfilment_order_id":OID,
        "price_cents":price,
        "direct_evidence":direct,
        "escrow_release":False,
        "amount_matches":matches,
    }


def verified_costs(*, order=OID, acq=2000, fulfil=3000):
    return {
        "fulfilment_order_id":order,
        "actual_cost_ready":True,
        "acquisition_cost":{
            "evidence_id":str(uuid4()),"source_type":"internal_actual",
            "source_reference":"cost-recorded:acq","amount_cents":acq,
        },
        "fulfilment_cost":{
            "evidence_id":str(uuid4()),"source_type":"provider_invoice",
            "source_reference":"cost-recorded:fulfil",
            "amount_cents":fulfil,
        },
    }


UNSET=object()


class Transport:
    def __init__(self, item=None, costs=UNSET, *, fail_cost=False):
        self.item=work() if item is None else item
        self.costs=verified_costs() if costs is UNSET else costs
        self.calls=[]
        self.fail_cost=fail_cost

    def __call__(self,name,params):
        self.calls.append(name)
        if name=="list_revenue_recognition_work":
            return [self.item]
        if name=="get_verified_actual_cost_evidence":
            if self.fail_cost:
                raise OutcomeTransportError("db unavailable")
            return self.costs
        if name=="recognize_bsc_revenue":
            return {"decision":"revenue_recognized"}
        raise AssertionError(name)


@pytest.mark.parametrize("bad",[
    None, {}, {"fulfilment_order_id":OID,"actual_cost_ready":False},
    verified_costs(order=OTHER),
    verified_costs(acq=19900,fulfil=0),
    verified_costs(acq=True),
    verified_costs(acq=-1),
    {**verified_costs(), "acquisition_cost":{
        **verified_costs()["acquisition_cost"],"source_type":"observed_contract"}},
    {**verified_costs(), "fulfilment_cost":{
        **verified_costs()["fulfilment_cost"],"source_reference":""}},
])
def test_missing_mismatched_or_unverified_cost_never_ready(bad):
    rpc=Transport(costs=bad)
    result=worker._classify_work(work(),rpc)
    assert result["decision"]=="HOLD_ACTUAL_COST_EVIDENCE"
    assert result["actual_cost_evidence_ready"] is False
    assert rpc.calls==["get_verified_actual_cost_evidence"]


def test_verified_actual_cost_and_positive_margin_required():
    rpc=Transport()
    result=worker._classify_work(work(),rpc)
    assert result["decision"]=="READY"
    assert result["actual_cost_evidence_ready"] is True
    assert rpc.calls==["get_verified_actual_cost_evidence"]


def test_no_money_evidence_or_bad_amount_never_queries_cost():
    for item in [work(matches=False),work(direct=False)]:
        rpc=Transport()
        result=worker._classify_work(item,rpc)
        assert result["decision"]=="HOLD_AMOUNT_MISMATCH"
        assert rpc.calls==[]


def test_cost_rpc_unavailable_fail_closed():
    rpc=Transport(fail_cost=True)
    result=worker._classify_work(work(),rpc)
    assert result["decision"]=="HOLD_ACTUAL_COST_LOOKUP_UNAVAILABLE"


def test_invalid_order_work_identity_is_not_approved():
    for item in ({"fulfilment_order_id":"invalid"},None):
        with pytest.raises(OutcomeTransportError):
            worker._classify_work(item,Transport())


def test_actor_execution_flags_cannot_override_missing_actual_cost(monkeypatch,capsys):
    transport=Transport(costs={"actual_cost_ready":False})
    monkeypatch.setattr(worker,"PostgresOutcomeRpc",lambda *a,**kw:transport)
    monkeypatch.setenv("EMPIRE_REVENUE_RECOGNIZER_DSN","redacted-test-dsn")
    assert worker.main(["--mode","GUARDED_EXECUTE","--execute"])==0
    report=json.loads(capsys.readouterr().out)
    assert report["results"][0]["decision"]=="HOLD_ACTUAL_COST_EVIDENCE"
    assert "recognize_bsc_revenue" not in transport.calls


def test_guarded_execute_requires_both_independent_proofs(monkeypatch,capsys):
    transport=Transport()
    monkeypatch.setattr(worker,"PostgresOutcomeRpc",lambda *a,**kw:transport)
    monkeypatch.setenv("EMPIRE_REVENUE_RECOGNIZER_DSN","redacted-test-dsn")
    assert worker.main(["--mode","GUARDED_EXECUTE","--execute"])==0
    report=json.loads(capsys.readouterr().out)
    assert report["results"][0]["execution"]["decision"]=="revenue_recognized"
    assert transport.calls==[
        "list_revenue_recognition_work",
        "get_verified_actual_cost_evidence",
        "recognize_bsc_revenue",
    ]


def test_observe_reports_evidence_without_recognising(monkeypatch,capsys):
    transport=Transport()
    monkeypatch.setattr(worker,"PostgresOutcomeRpc",lambda *a,**kw:transport)
    monkeypatch.setenv("EMPIRE_REVENUE_RECOGNIZER_DSN","redacted-test-dsn")
    assert worker.main(["--mode","OBSERVE"])==0
    report=json.loads(capsys.readouterr().out)
    assert report["results"][0]["decision"]=="READY"
    assert "recognize_bsc_revenue" not in transport.calls


def test_exact_existing_revenue_role_can_read_existing_cost_evidence():
    from empire_os.outcome_role_transport import ROLE_FUNCTIONS
    assert "get_verified_actual_cost_evidence" in ROLE_FUNCTIONS["empire_revenue_recognizer"]
    assert not any(
        "get_verified_actual_cost_evidence" in spec
        for name,spec in ROLE_FUNCTIONS.items()
        if name!="empire_revenue_recognizer"
    )
    sql,fields=ROLE_FUNCTIONS["empire_revenue_recognizer"]["get_verified_actual_cost_evidence"]
    assert sql=="select public.get_verified_actual_cost_evidence(%s)"
    assert fields==("p_fulfilment_order_id",)
