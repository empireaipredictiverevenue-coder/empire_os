from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.a2a_commerce_api import create_a2a_commerce_router
from empire_os.a2a_handoff import A2AManualHandoffEvidence
from empire_os.a2a_handoff_readiness import (
    A2AHandoffTimingEvidence,
    review_manual_handoff_readiness,
)


NOW = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)


def evidence():
    return A2AManualHandoffEvidence(
        negotiation_id="negotiation-1",
        agent_id="agent-buyer-1",
        negotiation_state="approved_for_manual_execution",
        signed_identity_evidence_ref="identity:signed:1",
        negotiation_evidence_ref="negotiation:1",
        human_approval_present=True,
        human_approval_evidence_ref="approval:human:1",
        counterparty_acknowledged=True,
        counterparty_evidence_ref="counterparty:ack:1",
        manual_handoff_ref="handoff:operator:1",
    )


def timing(**overrides):
    values = {
        "negotiation_observed_at": "2026-09-20T14:00:00+00:00",
        "human_approval_observed_at": "2026-09-20T15:00:00+00:00",
        "counterparty_observed_at": "2026-09-20T15:30:00+00:00",
        "handoff_observed_at": "2026-09-20T16:00:00+00:00",
    }
    values.update(overrides)
    return A2AHandoffTimingEvidence(**values)


def test_fresh_chronological_handoff_is_operator_ready_only():
    result = review_manual_handoff_readiness(
        evidence=evidence(),
        timing=timing(),
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.ready_for_operator_handoff is True
    assert result.blockers == ()
    assert result.handoff_age_seconds == 7200.0
    assert result.execution_authority == "none"
    assert result.payment_authority is False
    assert result.allocation_authority is False
    assert result.task_execution is False


def test_counterparty_before_human_approval_is_blocked():
    result = review_manual_handoff_readiness(
        evidence=evidence(),
        timing=timing(
            counterparty_observed_at="2026-09-20T14:30:00+00:00",
        ),
        now=NOW,
    )
    assert result.ready_for_operator_handoff is False
    assert (
        "counterparty_acknowledgement_before_human_approval"
        in result.blockers
    )


def test_stale_handoff_evidence_is_blocked():
    result = review_manual_handoff_readiness(
        evidence=evidence(),
        timing=timing(
            negotiation_observed_at="2026-09-20T08:00:00+00:00",
            human_approval_observed_at="2026-09-20T09:00:00+00:00",
            counterparty_observed_at="2026-09-20T09:30:00+00:00",
            handoff_observed_at="2026-09-20T10:00:00+00:00",
        ),
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.ready_for_operator_handoff is False
    assert "handoff_evidence_stale" in result.blockers


def test_missing_timing_evidence_is_explicit():
    result = review_manual_handoff_readiness(
        evidence=evidence(),
        timing=timing(handoff_observed_at=None),
        now=NOW,
    )
    assert result.ready_for_operator_handoff is False
    assert "handoff_timestamp_missing" in result.blockers


def test_api_preview_never_grants_execution():
    app = FastAPI()
    app.include_router(create_a2a_commerce_router())
    response = TestClient(app).post(
        "/v1/a2a-commerce/negotiation/handoff/readiness/preview",
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
            "negotiation_observed_at": "2026-09-20T14:00:00+00:00",
            "human_approval_observed_at": "2026-09-20T15:00:00+00:00",
            "counterparty_observed_at": "2026-09-20T15:30:00+00:00",
            "handoff_observed_at": "2026-09-20T16:00:00+00:00",
            "now_utc": "2026-09-20T18:00:00+00:00",
            "max_age_seconds": 21600,
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
    assert body["readiness"]["ready_for_operator_handoff"] is True
