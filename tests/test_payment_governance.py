from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from empire_os.payment_governance import (
    PaymentGovernanceError,
    approve_payment_request,
    build_escrow_proposal,
    build_payment_proposal,
    cancel_payment_request,
    record_payment_preview,
    review_payment_request,
    submit_payment_proposal,
    validate_review_block_anchor,
)

PAYER = "0x" + "33" * 20
TREASURY = "0x" + "22" * 20
NOW = datetime(2026, 9, 17, 16, 0, tzinfo=timezone.utc)


class FakeDb:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return self.result


def proposal(**overrides):
    values = {
        "fulfilment_order_id": uuid4(),
        "amount_usdt": "100.000000000000000001",
        "payer_address": PAYER.upper().replace("0X", "0x"),
        "treasury_address": TREASURY,
        "min_block_number": 123,
        "expires_at": NOW + timedelta(hours=1),
        "idempotency_key": "order:test:001",
        "actor": "operator.test",
        "now": NOW,
    }
    values.update(overrides)
    return build_payment_proposal(**values)

def test_build_proposal_is_observe_only_and_normalized():
    plan = proposal()
    assert plan["mode"] == "OBSERVE"
    assert plan["write_authorized"] is False
    assert plan["actual_revenue"] is False
    assert plan["rpc"] == "propose_bsc_payment_request"
    assert plan["params"]["p_payer_address"] == PAYER
    assert plan["params"]["p_amount_usdt"] == "100.000000000000000001"


def test_build_proposal_rejects_unsafe_terms():
    with pytest.raises(PaymentGovernanceError, match="18 decimal"):
        proposal(amount_usdt="1.0000000000000000001")
    with pytest.raises(PaymentGovernanceError, match="must differ"):
        proposal(treasury_address=PAYER)
    with pytest.raises(PaymentGovernanceError, match="10 minutes to 7 days"):
        proposal(expires_at=NOW + timedelta(days=8))
    with pytest.raises(PaymentGovernanceError, match="positive min_block"):
        proposal(min_block_number=True)


def test_submit_proposal_requires_explicit_operator_authorization():
    plan = proposal()
    db = FakeDb({"decision": "proposed", "request_id": str(uuid4()),
                 "status": "pending", "actual_revenue": False})
    with pytest.raises(PaymentGovernanceError, match="operator authorization"):
        submit_payment_proposal(plan, db=db)
    result = submit_payment_proposal(plan, operator_authorized=True, db=db)
    assert result["decision"] == "proposed"
    assert db.calls == [("propose_bsc_payment_request", plan["params"])]

def test_cancel_requires_explicit_operator_authorization():
    request_id = uuid4()
    db = FakeDb({"decision": "cancelled", "request_id": str(request_id),
                 "status": "cancelled", "actual_revenue": False})
    with pytest.raises(PaymentGovernanceError, match="operator authorization"):
        cancel_payment_request(request_id, actor="operator", reason="buyer withdrew", db=db)
    result = cancel_payment_request(
        request_id, actor="operator", reason="buyer withdrew",
        operator_authorized=True, db=db,
    )
    assert result["decision"] == "cancelled"
    assert db.calls[0][0] == "cancel_bsc_payment_request"


def test_approval_has_no_service_role_fallback():
    request_id = uuid4()
    with pytest.raises(PaymentGovernanceError, match="operator authorization"):
        approve_payment_request(
            request_id, approved_by="human", approval_note="reviewed terms",
            approver_rpc=lambda *_: None,
        )
    with pytest.raises(PaymentGovernanceError, match="dedicated approver transport"):
        approve_payment_request(
            request_id, approved_by="human", approval_note="reviewed terms",
            operator_authorized=True,
        )


def test_approval_uses_only_injected_approver_transport():
    calls = []
    request_id = uuid4()
    def rpc(name, params):
        calls.append((name, params))
        return {"decision": "approved", "request_id": str(request_id),
                "status": "approved", "actual_revenue": False}
    result = approve_payment_request(
        request_id, approved_by="human.operator", approval_note="buyer and treasury reviewed",
        operator_authorized=True, approver_rpc=rpc,
    )
    assert result["decision"] == "approved"
    assert calls[0][0] == "approve_bsc_payment_request"

def test_review_requires_dedicated_role_transport():
    request_id = uuid4()
    with pytest.raises(PaymentGovernanceError, match="dedicated approver/verifier transport"):
        review_payment_request(request_id)
    result = review_payment_request(
        request_id,
        role_rpc=lambda name, params: {
            "request_id": params["p_request_id"], "status": "pending",
            "actual_revenue": False,
        },
    )
    assert result["status"] == "pending"


def test_record_preview_requires_verifier_authorization_and_transport():
    request_id = uuid4()
    preview = {
        "mode": "OBSERVE", "recorded": False, "actual_revenue": False,
        "request_id": str(request_id),
        "evidence": {"verified": True, "token_decimals": 18},
    }
    with pytest.raises(PaymentGovernanceError, match="verifier authorization"):
        record_payment_preview(preview, verifier_rpc=lambda *_: None)
    with pytest.raises(PaymentGovernanceError, match="dedicated verifier transport"):
        record_payment_preview(preview, verifier_authorized=True)

    calls = []
    def rpc(name, params):
        calls.append((name, params))
        return {"decision": "recorded", "evidence_id": str(uuid4()),
                "request_id": str(request_id), "actual_revenue": False}
    result = record_payment_preview(
        preview, verifier_authorized=True, verifier_rpc=rpc,
    )
    assert result["decision"] == "recorded"
    assert calls[0][0] == "record_bsc_payment_evidence"
    assert calls[0][1]["p_evidence"]["verified"] is True


def test_governance_never_accepts_revenue_recognition_response():
    plan = proposal()
    db = FakeDb({"decision": "proposed", "actual_revenue": True})
    with pytest.raises(PaymentGovernanceError, match="revenue recognition"):
        submit_payment_proposal(plan, operator_authorized=True, db=db)


def test_cancel_can_use_dedicated_approver_transport_without_service_db():
    request_id = uuid4()
    calls = []
    def rpc(name, params):
        calls.append((name, params))
        return {"decision": "cancelled", "request_id": str(request_id),
                "status": "cancelled", "actual_revenue": False}
    result = cancel_payment_request(
        request_id, actor="human.operator", reason="buyer cancelled terms",
        operator_authorized=True, cancel_rpc=rpc,
    )
    assert result["decision"] == "cancelled"
    assert calls[0][0] == "cancel_bsc_payment_request"
    with pytest.raises(PaymentGovernanceError, match="choose dedicated"):
        cancel_payment_request(
            request_id, actor="human.operator", reason="buyer cancelled terms",
            operator_authorized=True, cancel_rpc=rpc, db=FakeDb({}),
        )


def test_build_escrow_proposal_is_explicit_and_uses_beneficiary():
    plan = build_escrow_proposal(
        fulfilment_order_id=uuid4(), amount_usdt="100",
        payer_address=PAYER, beneficiary_address=TREASURY,
        min_block_number=123, expires_at=NOW + timedelta(hours=1),
        idempotency_key="escrow:test:001", actor="operator.test", now=NOW,
    )
    assert plan["mode"] == "OBSERVE"
    assert plan["settlement_mode"] == "escrow"
    assert plan["rpc"] == "propose_bsc_escrow_request"
    assert plan["params"]["p_beneficiary_address"] == TREASURY
    assert plan["actual_revenue"] is False


def test_submit_accepts_escrow_proposal_but_still_requires_operator_authorization():
    plan = build_escrow_proposal(
        fulfilment_order_id=uuid4(), amount_usdt="50",
        payer_address=PAYER, beneficiary_address=TREASURY,
        min_block_number=321, expires_at=NOW + timedelta(hours=1),
        idempotency_key="escrow:test:002", actor="operator.test", now=NOW,
    )
    db = FakeDb({"decision":"proposed","status":"pending","actual_revenue":False})
    with pytest.raises(PaymentGovernanceError, match="operator authorization"):
        submit_payment_proposal(plan, db=db)
    result = submit_payment_proposal(plan, operator_authorized=True, db=db)
    assert result["decision"] == "proposed"
    assert db.calls[0][0] == "propose_bsc_escrow_request"


def test_block_anchor_validation_supports_escrow_beneficiary():
    class EscrowCfg:
        rpc_url = "https://example.invalid"
        beneficiary = TREASURY
        chain_id = 56
    review = {
        "actual_revenue": False, "settlement_mode": "escrow",
        "treasury_address": TREASURY, "min_block_number": 123,
        "created_at": NOW.isoformat(),
    }
    responses = {
        "eth_chainId": hex(56),
        "eth_getBlockByNumber": {
            "number": hex(123), "hash": "0x" + "77" * 32,
            "timestamp": hex(int(NOW.timestamp())),
        },
    }
    result = validate_review_block_anchor(
        review, config=EscrowCfg(), rpc_call=lambda method, params: responses[method]
    )
    assert result["verified"] is True
    assert result["actual_revenue"] is False


def test_block_anchor_validation_rejects_wrong_escrow_beneficiary():
    class EscrowCfg:
        rpc_url = "https://example.invalid"
        beneficiary = "0x" + "44" * 20
        chain_id = 56
    review = {
        "actual_revenue": False, "settlement_mode": "escrow",
        "treasury_address": TREASURY, "min_block_number": 123,
        "created_at": NOW.isoformat(),
    }
    with pytest.raises(PaymentGovernanceError, match="escrow beneficiary"):
        validate_review_block_anchor(review, config=EscrowCfg(), rpc_call=lambda *_: None)
