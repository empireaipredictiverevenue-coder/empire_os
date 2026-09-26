import json
import pytest

from empire_os.outcome_role_transport import (
    OutcomeTransportError,
    PostgresOutcomeRpc,
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
    def __init__(self, result): self.cursor = FakeCursor(result)
    def __call__(self, _dsn): return FakeConnection(self.cursor)


def test_revenue_role_lists_and_recognizes_only():
    factory = Factory([])
    rpc = PostgresOutcomeRpc(
        "postgresql://secret", "empire_revenue_recognizer",
        connect_factory=factory,
    )
    rpc("list_revenue_recognition_work", {"p_limit": 25})
    assert "list_revenue_recognition_work" in factory.cursor.calls[-1][0]
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("record_commercial_outcome", {})


def test_outcome_role_serializes_evidence_and_cannot_recognize_revenue():
    factory = Factory({"decision": "recorded_outcome"})
    rpc = PostgresOutcomeRpc(
        "postgresql://secret", "empire_outcome_recorder",
        connect_factory=factory,
    )
    rpc("record_commercial_outcome", {
        "p_fulfilment_order_id": "00000000-0000-0000-0000-000000000001",
        "p_delivery_outcome": "confirmed",
        "p_conversion_outcome": "won",
        "p_buyer_satisfaction": 4.5,
        "p_evidence_kind": "buyer_feedback",
        "p_evidence_reference": "reply-1",
        "p_evidence": {"source": "test"},
        "p_idempotency_key": "phase3f:test:001",
        "p_actor": "worker",
    })
    values = factory.cursor.calls[-1][1]
    assert json.loads(values[6]) == {"source": "test"}
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("recognize_bsc_revenue", {})


def test_transport_rejects_bad_role_and_shape():
    with pytest.raises(OutcomeTransportError, match="unsupported"):
        PostgresOutcomeRpc("postgresql://secret", "service_role", connect_factory=Factory({}))
    with pytest.raises(OutcomeTransportError, match="DSN"):
        PostgresOutcomeRpc("", "empire_revenue_recognizer", connect_factory=Factory({}))


def test_astra_observer_can_read_feedback_only():
    factory = Factory([
        {
            "conversion_outcome": "won",
            "actual_revenue_cents": 10000,
        }
    ])
    rpc = PostgresOutcomeRpc(
        "postgresql://secret",
        "empire_astra_observer",
        connect_factory=factory,
    )

    result = rpc(
        "get_commercial_outcome_feedback",
        {"p_limit": 100},
    )

    assert result[0]["actual_revenue_cents"] == 10000
    assert factory.cursor.calls[0][0] == "SET LOCAL ROLE empire_astra_observer"
    assert "get_commercial_outcome_feedback" in factory.cursor.calls[-1][0]

    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("record_commercial_outcome", {})
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("recognize_bsc_revenue", {})


def test_reader_role_can_read_figures_but_cannot_write():
    factory = Factory({
        "actual_revenue_cents": 10000,
        "gross_profit_cents": 7000,
    })
    rpc = PostgresOutcomeRpc(
        "postgresql://secret", "empire_outcome_reader",
        connect_factory=factory,
    )
    result = rpc(
        "get_phase3f_commercial_scorecard",
        {"p_days": 30},
    )
    assert result["actual_revenue_cents"] == 10000
    assert "get_phase3f_commercial_scorecard" in factory.cursor.calls[-1][0]
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("recognize_bsc_revenue", {})
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("record_commercial_outcome", {})


def test_astra_observer_can_read_operational_evidence_rpc():
    factory = Factory({
        "replies_waiting": 2,
        "failed_jobs": 1,
        "owned_inventory_count": 8,
        "qualified_unallocated_count": 2,
        "active_buyer_capacity": 3,
        "buyer_candidates_due": 4,
    })
    rpc = PostgresOutcomeRpc(
        "postgresql://secret",
        "empire_astra_observer",
        connect_factory=factory,
    )
    result = rpc("get_astra_operational_evidence", {})
    assert result["replies_waiting"] == 2
    assert result["active_buyer_capacity"] == 3
    assert "get_astra_operational_evidence" in factory.cursor.calls[-1][0]
