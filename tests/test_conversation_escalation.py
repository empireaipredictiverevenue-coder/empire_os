from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.conversation_api import create_conversation_router
from empire_os.conversation_escalation import review_human_escalation_readiness
from empire_os.conversation_qualification import (
    QualificationSignalEvidence,
    ConversationQualificationReview,
)
from empire_os.conversation_qualification_freshness import (
    QualificationFreshnessReview,
)


def qualification(signals=("commercial_need", "decision_authority")):
    evidence = tuple(
        QualificationSignalEvidence(
            signal=signal,
            provider_event_id=f"evt-{index}",
            occurred_at="2026-09-20T16:00:00+00:00",
            transcript_ref=f"transcript:{index}",
            evidence_ref=f"evidence:{index}",
        )
        for index, signal in enumerate(signals, start=1)
    )
    return ConversationQualificationReview(
        conversation_id="conversation-1",
        inbound_event_count=1,
        transcript_backed_inbound_count=1,
        observed_signals=tuple(signals),
        signal_evidence=evidence,
        review_state="explicit_qualification_evidence_observed",
        evidence_available_for_operator_review=bool(signals),
        blockers=(),
    )


def freshness(*, fresh=True, blockers=()):
    return QualificationFreshnessReview(
        conversation_id="conversation-1",
        fresh_for_operator_review=fresh,
        signal_ages_seconds={"evt-1:commercial_need": 60.0},
        blockers=tuple(blockers),
    )


def test_fresh_explicit_signals_and_closer_case_are_review_ready_only():
    result = review_human_escalation_readiness(
        qualification=qualification(),
        freshness=freshness(),
        closer_case_id="closer-case-1",
    )
    assert result.ready_for_human_escalation_review is True
    assert result.blockers == ()
    assert result.execution_authority == "none"
    assert result.human_escalation_execution is False
    assert result.call_execution is False
    assert result.voice_streaming is False
    assert result.booking_execution is False
    assert result.closer_state_mutation is False


def test_missing_closer_case_blocks_escalation_review():
    result = review_human_escalation_readiness(
        qualification=qualification(),
        freshness=freshness(),
        closer_case_id=None,
    )
    assert result.ready_for_human_escalation_review is False
    assert "canonical_closer_case_missing" in result.blockers


def test_stale_qualification_blocks_escalation_review():
    result = review_human_escalation_readiness(
        qualification=qualification(),
        freshness=freshness(
            fresh=False,
            blockers=("evt-1:commercial_need:evidence_stale",),
        ),
        closer_case_id="closer-case-1",
    )
    assert result.ready_for_human_escalation_review is False
    assert "qualification_not_fresh_for_operator_review" in result.blockers


def test_mixed_conversation_identity_is_rejected():
    bad = QualificationFreshnessReview(
        conversation_id="conversation-2",
        fresh_for_operator_review=True,
        signal_ages_seconds={},
        blockers=(),
    )
    try:
        review_human_escalation_readiness(
            qualification=qualification(),
            freshness=bad,
            closer_case_id="closer-case-1",
        )
    except ValueError as exc:
        assert "conversation mismatch" in str(exc)
    else:
        raise AssertionError("expected ValueError")


class Repo:
    def conversation(self, *, conversation_id):
        if conversation_id != "conversation-1":
            return None
        return {
            "id": conversation_id,
            "closer_case_id": "closer-case-1",
        }

    def timeline(self, *, conversation_id, limit):
        return [{
            "conversation_id": conversation_id,
            "direction": "inbound",
            "provider_event_id": "evt-1",
            "occurred_at": "2026-09-20T16:00:00+00:00",
            "evidence": {
                "transcript_ref": "transcript:1",
                "evidence_ref": "evidence:1",
                "qualification_signals": [
                    "commercial_need",
                    "decision_authority",
                ],
            },
        }]


def test_api_escalation_readiness_never_executes():
    app = FastAPI()
    app.include_router(create_conversation_router(read_repository=Repo()))
    response = TestClient(app).get(
        "/v1/conversations/conversation-1/escalation/readiness",
        params={"now_utc": "2026-09-20T16:30:00+00:00"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["human_escalation_execution"] is False
    assert body["outbound_calls"] is False
    assert body["voice_streaming"] is False
    assert body["booking_execution"] is False
    assert body["closer_state_mutation"] is False
    assert body["readiness"]["ready_for_human_escalation_review"] is True
