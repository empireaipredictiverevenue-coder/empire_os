from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.a2a_commerce_api import create_a2a_commerce_router
from empire_os.a2a_handoff import (
    A2AManualHandoffEvidence,
    review_manual_handoff,
)


def evidence(**overrides):
    values = {
        "negotiation_id": "negotiation-1",
        "agent_id": "agent-buyer-1",
        "negotiation_state": "approved_for_manual_execution",
        "signed_identity_evidence_ref": "identity:signed:1",
        "negotiation_evidence_ref": "negotiation:1",
        "human_approval_present": True,
        "human_approval_evidence_ref": "approval:human:1",
        "counterparty_acknowledged": True,
        "counterparty_evidence_ref": "counterparty:ack:1",
        "manual_handoff_ref": "handoff:operator:1",
    }
    values.update(overrides)
    return A2AManualHandoffEvidence(**values)


def test_complete_evidence_is_ready_for_operator_handoff_only():
    result = review_manual_handoff(evidence())
    assert result.handoff_ready_for_operator_review is True
    assert result.blockers == ()
    assert result.human_approval_required is True
    assert result.execution_authority == "none"
    assert result.payment_authority is False
    assert result.allocation_authority is False
    assert result.task_execution is False
    assert result.autonomous_handoff_execution is False


def test_approved_state_without_human_approval_evidence_is_blocked():
    result = review_manual_handoff(
        evidence(
            human_approval_present=False,
            human_approval_evidence_ref=None,
        )
    )
    assert result.handoff_ready_for_operator_review is False
    assert "human_approval_evidence_missing" in result.blockers


def test_nonapproved_negotiation_state_is_blocked():
    result = review_manual_handoff(
        evidence(negotiation_state="reviewed")
    )
    assert result.handoff_ready_for_operator_review is False
    assert (
        "negotiation_not_approved_for_manual_execution"
        in result.blockers
    )


def test_missing_signed_identity_and_counterparty_evidence_are_explicit():
    result = review_manual_handoff(
        evidence(
            signed_identity_evidence_ref=None,
            counterparty_acknowledged=False,
            counterparty_evidence_ref=None,
        )
    )
    assert result.handoff_ready_for_operator_review is False
    assert "signed_agent_identity_evidence_missing" in result.blockers
    assert (
        "counterparty_acknowledgement_evidence_missing"
        in result.blockers
    )


def test_missing_handoff_reference_blocks_operator_review():
    result = review_manual_handoff(
        evidence(manual_handoff_ref=None)
    )
    assert result.handoff_ready_for_operator_review is False
    assert "manual_handoff_reference_missing" in result.blockers


def test_api_preview_never_grants_commercial_execution():
    app = FastAPI()
    app.include_router(create_a2a_commerce_router())
    response = TestClient(app).post(
        "/v1/a2a-commerce/negotiation/handoff/preview",
        json={
            "negotiation_id": "negotiation-1",
            "agent_id": "agent-buyer-1",
            "negotiation_state": "approved_for_manual_execution",
            "signed_identity_evidence_ref": "identity:signed:1",
            "negotiation_evidence_ref": "negotiation:1",
            "human_approval_present": True,
            "human_approval_evidence_ref": "approval:human:1",
            "counterparty_acknowledged": True,
            "counterparty_evidence_ref": "counterparty:ack:1",
            "manual_handoff_ref": "handoff:operator:1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["human_approval_required"] is True
    assert body["execution_authority"] == "none"
    assert body["payment_authority"] is False
    assert body["allocation_authority"] is False
    assert body["task_execution"] is False
    assert body["autonomous_handoff_execution"] is False
    assert body["handoff"]["handoff_ready_for_operator_review"] is True


def test_empty_identity_is_rejected():
    app = FastAPI()
    app.include_router(create_a2a_commerce_router())
    response = TestClient(app).post(
        "/v1/a2a-commerce/negotiation/handoff/preview",
        json={
            "negotiation_id": "negotiation-1",
            "agent_id": "",
            "negotiation_state": "approved_for_manual_execution",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "agent_id required"
