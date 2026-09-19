from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.conversation_api import create_conversation_router
from empire_os.conversation_timeline import summarise_conversation_timeline


class FakeReadRepository:
    def __init__(self, rows=None):
        self.rows = rows or []

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


def event(direction, occurred_at, event_type, text=None):
    return {
        "conversation_id": "conversation-1",
        "event_type": event_type,
        "direction": direction,
        "actor": "buyer" if direction == "inbound" else "agent",
        "body_text": text,
        "provider_event_id": f"{event_type}-{occurred_at}",
        "evidence": {"source": "provider"},
        "occurred_at": occurred_at,
    }


def client(repo=None):
    app = FastAPI()
    app.include_router(
        create_conversation_router(read_repository=repo)
    )
    return TestClient(app)


def test_inbound_response_is_observed_not_inferred():
    rows = [
        event(
            "outbound",
            "2026-09-20T09:00:00+00:00",
            "message_sent",
        ),
        event(
            "inbound",
            "2026-09-20T09:05:00+00:00",
            "speech_received",
            "Interested",
        ),
    ]
    result = summarise_conversation_timeline(
        rows,
        conversation_id="conversation-1",
    )
    assert result.event_count == 2
    assert result.inbound_events == 1
    assert result.qualification_signal == "observed_inbound_response"
    assert result.latest_text == "Interested"
    assert result.execution_authority == "none"


def test_outbound_only_stays_explicitly_unanswered():
    result = summarise_conversation_timeline(
        [event(
            "outbound",
            "2026-09-20T09:00:00+00:00",
            "message_sent",
        )],
        conversation_id="conversation-1",
    )
    assert result.qualification_signal == (
        "outbound_only_no_observed_response"
    )
    assert result.blockers == ("inbound_response_not_observed",)


def test_empty_timeline_is_unknown_not_zero_interest():
    result = summarise_conversation_timeline(
        [],
        conversation_id="conversation-1",
    )
    assert result.event_count == 0
    assert result.qualification_signal == "no_observed_events"
    assert result.latest_text is None
    assert result.blockers == (
        "conversation_event_evidence_missing",
    )


def test_unbound_reader_fails_closed():
    response = client().get(
        "/v1/conversations/conversation-1/timeline"
    )
    assert response.status_code == 503

def test_timeline_endpoint_is_read_only():
    repo = FakeReadRepository([
        event(
            "inbound",
            "2026-09-20T09:05:00+00:00",
            "speech_received",
            "Interested",
        )
    ])
    response = client(repo).get(
        "/v1/conversations/conversation-1/timeline?limit=10"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"
    assert body["count"] == 1
    assert body["conversation"]["buyer_id"] == "buyer-1"


def test_summary_endpoint_uses_only_observed_events():
    repo = FakeReadRepository([
        event(
            "outbound",
            "2026-09-20T09:00:00+00:00",
            "message_sent",
        ),
        event(
            "inbound",
            "2026-09-20T09:05:00+00:00",
            "speech_received",
            "Interested",
        ),
    ])
    response = client(repo).get(
        "/v1/conversations/conversation-1/summary"
    )
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["qualification_signal"] == "observed_inbound_response"
    assert summary["latest_text"] == "Interested"


def test_unknown_conversation_returns_404():
    response = client(FakeReadRepository()).get(
        "/v1/conversations/missing/summary"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "conversation_not_found"
