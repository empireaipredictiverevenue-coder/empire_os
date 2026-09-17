import json
import pytest

from empire_os.outbound_provider import OutboundProviderError
from empire_os.outbound_role_transport import PostgresOutboundRpc


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


def test_sender_role_can_claim_and_record_delivery_only():
    factory = Factory({"decision":"authorized_send","actual_revenue":False})
    rpc = PostgresOutboundRpc("postgresql://secret", "empire_outbound_sender", connect_factory=factory)
    result = rpc("claim_outbound_send", {"p_intent_id":"00000000-0000-0000-0000-000000000001","p_actor":"sender"})
    assert result["decision"] == "authorized_send"
    assert factory.cursor.calls[0] == ("SET LOCAL ROLE empire_outbound_sender", None)
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
    with pytest.raises(OutboundProviderError, match="not allowed"):
        rpc("claim_outbound_send", {})


def test_approver_role_is_separate_and_parameter_shape_is_strict():
    factory = Factory({"decision":"approved","actual_revenue":False})
    rpc = PostgresOutboundRpc("postgresql://secret", "empire_outbound_approver", connect_factory=factory)
    rpc("approve_outbound_intent", {
        "p_intent_id":"00000000-0000-0000-0000-000000000001",
        "p_approved_by":"human.operator", "p_note":"reviewed",
    })
    with pytest.raises(OutboundProviderError, match="unexpected"):
        rpc("approve_outbound_intent", {"wrong":"shape"})
    with pytest.raises(OutboundProviderError, match="unsupported"):
        PostgresOutboundRpc("postgresql://secret", "service_role", connect_factory=factory)
    with pytest.raises(OutboundProviderError, match="DSN"):
        PostgresOutboundRpc("", "empire_outbound_sender", connect_factory=factory)
