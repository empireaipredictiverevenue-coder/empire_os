from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.conversation_api import create_conversation_router
from empire_os.conversation_qualification import (
    review_conversation_qualification,
)


def event(
    *,
    direction="inbound",
    text="Interested",
    evidence=None,
    event_id="event-1",
):
    return {
        "conversation_id": "conversation-1",
        "event_type": "transcript_segment",
        "direction": direction,
        "occurred_at": "2026-09-20T10:00:00+00:00",
        "actor": "buyer",
        "body_text": text,
        "provider_event_id": event_id,
        "evidence": dict(evidence or {}),
    }


def explicit_evidence(signals):
    return {
        "transcript_ref": "transcript:conv-1:segment-1",
        "evidence_ref": "provider:event-1",
        "qualification_signals": list(signals),
    }


def test_plain_inbound_text_does_not_infer_qualification():
    result = review_conversation_qualification(
        [event(text="Interested, send me pricing")],
        conversation_id="conversation-1",
    )
    assert result.inbound_event_count == 1
    assert result.observed_signals == ()
    assert result.evidence_available_for_operator_review is False
    assert result.review_state == (
        "inbound_observed_without_transcript_evidence"
    )
    assert result.blockers == ("transcript_evidence_missing",)


def test_transcript_without_explicit_signals_stays_unqualified():
    result = review_conversation_qualification(
        [event(evidence=explicit_evidence([]))],
        conversation_id="conversation-1",
    )
    assert result.transcript_backed_inbound_count == 1
    assert result.observed_signals == ()
    assert result.review_state == (
        "inbound_observed_no_explicit_qualification_signals"
    )
    assert result.blockers == (
        "explicit_qualification_signals_missing",
    )


def test_explicit_inbound_signals_are_preserved_as_evidence():
    result = review_conversation_qualification(
        [event(evidence=explicit_evidence([
            "interest",
            "decision_authority",
            "commercial_need",
        ]))],
        conversation_id="conversation-1",
    )
    assert result.evidence_available_for_operator_review is True
    assert result.observed_signals == (
        "commercial_need",
        "decision_authority",
        "interest",
    )
    assert result.review_state == (
        "explicit_qualification_evidence_observed"
    )
    assert result.blockers == ()
    assert len(result.signal_evidence) == 3
    assert result.execution_authority == "none"
    assert result.send_execution is False
    assert result.call_execution is False


def test_outbound_explicit_signals_do_not_count():
    result = review_conversation_qualification(
        [event(
            direction="outbound",
            evidence=explicit_evidence(["interest"]),
        )],
        conversation_id="conversation-1",
    )
    assert result.inbound_event_count == 0
    assert result.observed_signals == ()
    assert result.review_state == "no_observed_inbound_response"


def test_unknown_signal_is_ignored_not_invented():
    result = review_conversation_qualification(
        [event(evidence=explicit_evidence([
            "interest",
            "sentiment_positive",
        ]))],
        conversation_id="conversation-1",
    )
    assert result.observed_signals == ("interest",)


class FakeReadRepository:
    def __init__(self, rows):
        self.rows = rows

    def conversation(self, *, conversation_id):
        if conversation_id != "conversation-1":
            return None
        return {
            "id": conversation_id,
            "channel": "voice",
            "state": "engaged",
            "buyer_id": "buyer-1",
        }

    def timeline(self, *, conversation_id, limit):
        return list(self.rows)[:limit]


def test_api_qualification_is_read_only_and_non_executing():
    repo = FakeReadRepository([
        event(evidence=explicit_evidence([
            "interest",
            "timing",
        ]))
    ])
    app = FastAPI()
    app.include_router(
        create_conversation_router(read_repository=repo)
    )
    response = TestClient(app).get(
        "/v1/conversations/conversation-1/qualification"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"
    assert body["outbound_calls"] is False
    assert body["voice_streaming"] is False
    assert body["email_sends"] is False
    assert body["booking_execution"] is False
    assert body["qualification"][
        "evidence_available_for_operator_review"
    ] is True
    assert body["qualification"]["observed_signals"] == [
        "interest",
        "timing",
    ]


def test_unbound_qualification_reader_fails_closed():
    app = FastAPI()
    app.include_router(create_conversation_router())
    response = TestClient(app).get(
        "/v1/conversations/conversation-1/qualification"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "conversation_reader_not_activated"
    )
