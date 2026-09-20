import json

import pytest

from empire_os.closer_role_transport import (
    CloserTransportError,
    PostgresCloserRpc,
    SupabaseCloserRpc,
)


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return (self.result,)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


class Factory:
    def __init__(self, result):
        self.cursor = FakeCursor(result)

    def __call__(self, dsn):
        return FakeConnection(self.cursor)


def test_observer_can_only_list_work():
    factory = Factory([{"reply_id": "r1", "classification": "positive"}])
    rpc = PostgresCloserRpc(
        "postgresql://secret",
        "empire_closer_observer",
        connect_factory=factory,
    )
    result = rpc("list_closer_work", {"p_limit": 25})
    assert result[0]["reply_id"] == "r1"
    assert factory.cursor.calls[0] == (
        "SET LOCAL ROLE empire_closer_observer",
        None,
    )
    with pytest.raises(CloserTransportError, match="not allowed"):
        rpc("open_closer_case", {"p_reply_id": "r1"})


def test_planner_can_open_and_record_but_not_approve():
    factory = Factory({"decision": "recorded"})
    rpc = PostgresCloserRpc(
        "postgresql://secret",
        "empire_closer_planner",
        connect_factory=factory,
    )
    rpc("open_closer_case", {"p_reply_id": "00000000-0000-0000-0000-000000000001"})
    rpc("provision_buyer_from_closer_case", {
        "p_case_id": "00000000-0000-0000-0000-000000000002",
        "p_actor": "empire_closer_planner",
    })
    rpc("get_closer_reply_context", {
        "p_case_id": "00000000-0000-0000-0000-000000000002",
        "p_reply_id": "00000000-0000-0000-0000-000000000001",
    })
    rpc("propose_closer_reply_intent", {
        "p_case_id": "00000000-0000-0000-0000-000000000002",
        "p_reply_id": "00000000-0000-0000-0000-000000000001",
        "p_subject": "Re: hello",
        "p_body_text": "Thanks",
        "p_idempotency_key": "closer:test:1",
        "p_proposed_by": "empire_closer_planner",
        "p_expires_at": "2026-09-21T12:00:00+00:00",
    })
    rpc("record_buyer_capacity_intake", {
        "p_case_id": "00000000-0000-0000-0000-000000000002",
        "p_reply_id": "00000000-0000-0000-0000-000000000001",
        "p_territory": "Austin",
        "p_daily_cap": 10,
        "p_delivery_route": "webhook",
        "p_delivery_reference": "https://acme.test/leads",
        "p_evidence": {"parser": "buyer_capacity_intake_v1"},
        "p_actor": "empire_closer_planner",
    })
    rpc("prepare_fulfilment_order_from_capacity", {
        "p_case_id": "00000000-0000-0000-0000-000000000002",
        "p_actor": "empire_closer_planner",
    })
    rpc("record_closer_recommendation", {
        "p_case_id": "00000000-0000-0000-0000-000000000002",
        "p_type": "qualify",
        "p_confidence": 0.9,
        "p_rationale": {"classification": "positive"},
        "p_message": None,
        "p_model_key": "rules:v1",
    })
    assert json.loads(factory.cursor.calls[-1][1][3]) == {
        "classification": "positive"
    }
    with pytest.raises(CloserTransportError, match="not allowed"):
        rpc("advance_closer_case", {})


def test_approver_can_only_advance_and_shapes_are_strict():
    factory = Factory({"decision": "advanced"})
    rpc = PostgresCloserRpc(
        "postgresql://secret",
        "empire_closer_approver",
        connect_factory=factory,
    )
    rpc("advance_closer_case", {
        "p_case_id": "00000000-0000-0000-0000-000000000002",
        "p_next_state": "qualified",
        "p_actor": "human.operator",
        "p_fulfilment_order_id": None,
        "p_note": "reviewed",
    })
    with pytest.raises(CloserTransportError, match="not allowed"):
        rpc("record_closer_recommendation", {})
    with pytest.raises(CloserTransportError, match="unexpected"):
        rpc("advance_closer_case", {"wrong": "shape"})
    with pytest.raises(CloserTransportError, match="unsupported"):
        PostgresCloserRpc(
            "postgresql://secret",
            "service_role",
            connect_factory=factory,
        )
    with pytest.raises(CloserTransportError, match="DSN"):
        PostgresCloserRpc(
            "",
            "empire_closer_observer",
            connect_factory=factory,
        )


def test_supabase_planner_bridge_keeps_role_allowlist():
    calls = []

    def request(method, path, *, payload=None, **_kwargs):
        calls.append((method, path, payload))
        return {"decision": "opened", "case_id": "c1"}

    rpc = SupabaseCloserRpc(
        "empire_closer_planner",
        request_factory=request,
    )
    result = rpc(
        "open_closer_case",
        {"p_reply_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert result["case_id"] == "c1"
    assert calls == [(
        "POST",
        "/rest/v1/rpc/open_closer_case",
        {"p_reply_id": "00000000-0000-0000-0000-000000000001"},
    )]
    with pytest.raises(CloserTransportError, match="not allowed"):
        rpc("advance_closer_case", {})


def test_supabase_bridge_never_exposes_closer_approver():
    with pytest.raises(CloserTransportError, match="dedicated governed"):
        SupabaseCloserRpc(
            "empire_closer_approver",
            request_factory=lambda *_args, **_kwargs: None,
        )
