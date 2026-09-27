from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.conversation_api import create_conversation_router
from empire_os.conversation_qualification import (
    review_conversation_qualification,
)
from empire_os.conversation_qualification_freshness import (
    review_qualification_freshness,
)


NOW = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)


def event(occurred_at="2026-09-20T16:00:00+00:00"):
    return {
        "conversation_id": "conversation-1",
        "event_type": "transcript_segment",
        "direction": "inbound",
        "occurred_at": occurred_at,
        "actor": "buyer",
        "body_text": "Interested",
        "provider_event_id": "event-1",
        "evidence": {
            "transcript_ref": "transcript:1",
            "evidence_ref": "provider:event-1",
            "qualification_signals": ["interest", "timing"],
        },
    }


def test_fresh_qualification_evidence_is_operator_reviewable():
    base = review_conversation_qualification(
        [event()],
        conversation_id="conversation-1",
    )
    result = review_qualification_freshness(
        base,
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.fresh_for_operator_review is True
    assert result.blockers == ()
    assert result.execution_authority == "none"
    assert result.send_execution is False
    assert result.call_execution is False


def test_stale_signal_evidence_blocks_freshness():
    base = review_conversation_qualification(
        [event("2026-09-20T08:00:00+00:00")],
        conversation_id="conversation-1",
    )
    result = review_qualification_freshness(
        base,
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.fresh_for_operator_review is False
    assert any(
        blocker.endswith(":evidence_stale")
        for blocker in result.blockers
    )


def test_future_signal_evidence_blocks_freshness():
    base = review_conversation_qualification(
        [event("2026-09-20T18:05:00+00:00")],
        conversation_id="conversation-1",
    )
    result = review_qualification_freshness(
        base,
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.fresh_for_operator_review is False
    assert any(
        blocker.endswith(":evidence_from_future")
        for blocker in result.blockers
    )


class FakeReadRepository:
    def conversation(self, *, conversation_id):
        if conversation_id != "conversation-1":
            return None
        return {"id": conversation_id, "state": "engaged"}

    def timeline(self, *, conversation_id, limit):
        return [event()][:limit]


def test_api_freshness_is_read_only_and_non_executing():
    app = FastAPI()
    app.include_router(
        create_conversation_router(
            read_repository=FakeReadRepository()
        )
    )
    response = TestClient(app).get(
        "/v1/conversations/conversation-1/qualification/freshness",
        params={
            "now_utc": "2026-09-20T18:00:00+00:00",
            "max_age_seconds": 21600,
        },
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
    assert body["freshness"]["fresh_for_operator_review"] is True


def test_api_rejects_naive_now():
    app = FastAPI()
    app.include_router(
        create_conversation_router(
            read_repository=FakeReadRepository()
        )
    )
    response = TestClient(app).get(
        "/v1/conversations/conversation-1/qualification/freshness",
        params={"now_utc": "2026-09-20T18:00:00"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "now_utc must include timezone"
