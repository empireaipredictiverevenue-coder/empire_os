import json
import pytest

from empire_os.outbound_provider import OutboundProviderError
from empire_os.outbound_role_transport import (
    PostgresOutboundRpc,
    SupabaseOutboundRpc,
)


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params=None): self.calls.append((sql, params))
    def fetchone(self): return (self.result,)


class FakeConnection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return self._cursor


class Factory:
    def __init__(self, result):
        self.cursor = FakeCursor(result)
    def __call__(self, dsn):
        return FakeConnection(self.cursor)


def test_sender_role_can_review_context_claim_and_record_but_not_approve():
    factory = Factory({"decision":"authorized_send","actual_revenue":False})
    rpc = PostgresOutboundRpc("postgresql://secret", "empire_outbound_sender", connect_factory=factory)
    result = rpc("claim_outbound_send", {"p_intent_id":"00000000-0000-0000-0000-000000000001","p_actor":"sender"})
    assert result["decision"] == "authorized_send"
    assert factory.cursor.calls[0] == ("SET LOCAL ROLE empire_outbound_sender", None)
    rpc("get_outbound_governor_context", {
        "p_intent_id":"00000000-0000-0000-0000-000000000001"
    })
    assert "get_outbound_governor_context" in factory.cursor.calls[-1][0]
    rpc("list_outbound_governor_work", {"p_limit":25})
    assert "list_outbound_governor_work" in factory.cursor.calls[-1][0]
    with pytest.raises(OutboundProviderError, match="not allowed"):
        rpc("approve_outbound_intent", {})


def test_reply_ingest_serializes_metadata_and_cannot_send():
    factory = Factory({"decision":"recorded","actual_revenue":False})
    rpc = PostgresOutboundRpc("postgresql://secret", "empire_reply_ingest", connect_factory=factory)
    rpc("ingest_outbound_reply", {
        "p_intent_id":"00000000-0000-0000-0000-000000000001",
        "p_provider_message_id":"em_1", "p_from_contact":"buyer@example.com",
        "p_subject":"Re: hello", "p_body_text":"Interested",
        "p_received_at":"2026-09-17T18:00:00Z", "p_metadata":{"provider":"resend"},
    })
    values = factory.cursor.calls[1][1]
    assert json.loads(values[-1]) == {"provider":"resend"}
    rpc("record_outbound_provider_event", {
        "p_intent_id":"00000000-0000-0000-0000-000000000001",
        "p_event_type":"delivered",
        "p_provider_message_id":"em_1",
        "p_recipient":"buyer@example.com",
        "p_suppress":False,
        "p_payload":{"provider":"resend"},
    })
    values = factory.cursor.calls[-1][1]
    assert json.loads(values[-1]) == {"provider":"resend"}
    with pytest.raises(OutboundProviderError, match="not allowed"):
        rpc("claim_outbound_send", {})


def test_approver_role_is_separate_and_parameter_shape_is_strict():
    factory = Factory({"decision":"approved","actual_revenue":False})
    rpc = PostgresOutboundRpc("postgresql://secret", "empire_outbound_approver", connect_factory=factory)
    rpc("approve_outbound_intent", {
        "p_intent_id":"00000000-0000-0000-0000-000000000001",
        "p_approved_by":"human.operator", "p_note":"reviewed",
    })
    rpc("cancel_outbound_intent", {
        "p_intent_id":"00000000-0000-0000-0000-000000000001",
        "p_cancelled_by":"human.operator", "p_reason":"replace stale draft",
    })
    with pytest.raises(OutboundProviderError, match="unexpected"):
        rpc("approve_outbound_intent", {"wrong":"shape"})
    with pytest.raises(OutboundProviderError, match="unsupported"):
        PostgresOutboundRpc("postgresql://secret", "service_role", connect_factory=factory)
    with pytest.raises(OutboundProviderError, match="DSN"):
        PostgresOutboundRpc("", "empire_outbound_sender", connect_factory=factory)


def test_supabase_sender_transport_keeps_same_rpc_allowlist():
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload, kwargs))
        return {"decision": "authorized_send", "actual_revenue": False}

    rpc = SupabaseOutboundRpc(
        "empire_outbound_sender",
        request_factory=request,
    )
    result = rpc(
        "claim_outbound_send",
        {
            "p_intent_id": "00000000-0000-0000-0000-000000000001",
            "p_actor": "empire_gtm_agent_v1",
        },
    )

    assert result["decision"] == "authorized_send"
    assert calls == [
        (
            "POST",
            "/rest/v1/rpc/claim_outbound_send",
            {
                "p_intent_id": "00000000-0000-0000-0000-000000000001",
                "p_actor": "empire_gtm_agent_v1",
            },
            {},
        )
    ]
    with pytest.raises(OutboundProviderError, match="not allowed"):
        rpc("approve_outbound_intent", {})


def test_supabase_reply_transport_is_not_a_sender():
    rpc = SupabaseOutboundRpc(
        "empire_reply_ingest",
        request_factory=lambda *args, **kwargs: {"ok": True},
    )

    with pytest.raises(OutboundProviderError, match="not allowed"):
        rpc(
            "claim_outbound_send",
            {
                "p_intent_id": "00000000-0000-0000-0000-000000000001",
                "p_actor": "reply",
            },
        )
