import json
from datetime import datetime, timezone

import pytest

from empire_os.astra_observer import (
    AstraObserverError,
    bounded_feedback_limit,
    parse_operational_snapshot,
    run_observer_cycle,
)


class FakeRpc:
    def __init__(self, dsn, role, rows, calls, operational=None):
        self.dsn = dsn
        self.role = role
        self.rows = rows
        self.calls = calls
        self.operational = operational

    def __call__(self, name, params):
        self.calls.append((self.role, name, params))
        if name == "get_astra_operational_evidence":
            return self.operational
        return self.rows


def _factory(rows, calls, operational=None):
    def build(dsn, role):
        return FakeRpc(dsn, role, rows, calls, operational)
    return build


def _complete_snapshot():
    return {
        "execution_mode": "observe",
        "actual_revenue_cents": 0,
        "premium_ai_budget_cents": 0,
        "replies_waiting": 0,
        "failed_jobs": 0,
        "owned_inventory_count": 3,
        "qualified_unallocated_count": 0,
        "active_buyer_capacity": 1,
        "buyer_candidates_due": 0,
        "outbound_domain_verified": True,
        "source_health_ok": True,
    }


def test_cycle_reads_feedback_and_writes_local_snapshot_without_decision(tmp_path):
    rows = [{
        "conversion_outcome": "won",
        "actual_revenue_cents": 10000,
        "actual_cost_cents": 3000,
        "gross_profit_cents": 7000,
        "buyer_satisfaction": 4.5,
        "previous_purchase": True,
    }]
    calls = []
    output = tmp_path / "latest.json"

    result = run_observer_cycle(
        dsn="postgresql://observer",
        feedback_limit=5000,
        min_samples=20,
        min_conversions=5,
        output_path=output,
        rpc_factory=_factory(rows, calls),
    )

    assert calls == [
        (
            "empire_astra_observer",
            "get_commercial_outcome_feedback",
            {"p_limit": 1000},
        ),
        (
            "empire_astra_observer",
            "get_astra_operational_evidence",
            {},
        ),
    ]
    assert result["mode"] == "OBSERVE"
    assert result["side_effects"] == "none"
    assert result["decision"]["available"] is False
    assert result["decision"]["reason"] == "operational_evidence_incomplete"
    assert "active_buyer_capacity" in result["decision"]["missing"]
    assert result["operating_board"]["available"] is False
    assert result["operating_board"]["reason"] == "operational_evidence_incomplete"
    assert result["calibration"]["actual_revenue_cents"] == 10000
    assert result["calibration"]["calibration_ready"] is False
    assert json.loads(output.read_text()) == result


def test_complete_observed_snapshot_can_produce_plan_only_decision(tmp_path):
    calls = []
    result = run_observer_cycle(
        dsn="postgresql://observer",
        operational_snapshot_json=json.dumps(_complete_snapshot()),
        output_path=tmp_path / "latest.json",
        rpc_factory=_factory([], calls),
    )

    assert result["decision"]["available"] is True
    assert result["decision"]["source"] == "explicit_operational_snapshot"
    decision = result["decision"]["result"]
    assert decision["recommended_job_type"] == "qualify_owned_inventory"
    assert decision["side_effect_approval_required"] is False
    board = result["operating_board"]["result"]
    assert board["primary"] == decision
    assert board["items"][0] == decision
    assert board["side_effects"] == "none"


def test_partial_operational_snapshot_is_rejected():
    with pytest.raises(AstraObserverError, match="exactly AstraSnapshot fields"):
        parse_operational_snapshot(json.dumps({
            "execution_mode": "observe",
            "owned_inventory_count": 3,
        }))


def test_non_observe_mode_is_rejected(tmp_path):
    with pytest.raises(AstraObserverError, match="supports OBSERVE only"):
        run_observer_cycle(
            dsn="postgresql://observer",
            mode="LIVE",
            output_path=tmp_path / "latest.json",
            rpc_factory=_factory([], []),
        )


def test_feedback_limit_is_bounded():
    assert bounded_feedback_limit(0) == 1
    assert bounded_feedback_limit(10) == 10
    assert bounded_feedback_limit(50000) == 1000
    assert bounded_feedback_limit("bad") == 100
def test_canonical_operational_evidence_can_build_board(tmp_path):
    calls = []
    operational = {
        "replies_waiting": 0,
        "failed_jobs": 0,
        "owned_inventory_count": 8,
        "qualified_unallocated_count": 2,
        "active_buyer_capacity": 3,
        "buyer_candidates_due": 0,
        "observed_at": "2026-09-19T16:30:00+00:00",
    }
    bindings = {
        "premium_ai_budget_cents": 0,
        "outbound_domain_verified": True,
        "source_health_ok": True,
    }
    result = run_observer_cycle(
        dsn="postgresql://observer",
        operational_bindings=bindings,
        now_utc=datetime(2026, 9, 19, 17, 0, tzinfo=timezone.utc),
        output_path=tmp_path / "latest.json",
        rpc_factory=_factory([], calls, operational),
    )
    assert result["operational_evidence"]["available"] is True
    assert result["decision"]["available"] is True
    assert result["decision"]["source"] == "canonical_operational_evidence"
    assert result["decision"]["result"]["recommended_job_type"] == "plan_controlled_allocation"
    assert result["operating_board"]["result"]["side_effects"] == "none"


def test_canonical_evidence_missing_policy_binding_stays_unavailable(tmp_path):
    operational = {
        "replies_waiting": 0,
        "failed_jobs": 0,
        "owned_inventory_count": 0,
        "qualified_unallocated_count": 0,
        "active_buyer_capacity": 0,
        "buyer_candidates_due": 0,
        "observed_at": "2026-09-19T16:30:00+00:00",
    }
    result = run_observer_cycle(
        dsn="postgresql://observer",
        operational_bindings={},
        now_utc=datetime(2026, 9, 19, 17, 0, tzinfo=timezone.utc),
        output_path=tmp_path / "latest.json",
        rpc_factory=_factory([], [], operational),
    )
    assert result["decision"]["available"] is False
    assert "premium_ai_budget_cents" in result["decision"]["missing"]
    assert "outbound_domain_verified" in result["decision"]["missing"]
    assert "source_health_ok" in result["decision"]["missing"]


def test_stale_canonical_operational_evidence_blocks_board(tmp_path):
    operational = {
        "replies_waiting": 0,
        "failed_jobs": 0,
        "owned_inventory_count": 8,
        "qualified_unallocated_count": 2,
        "active_buyer_capacity": 3,
        "buyer_candidates_due": 0,
        "observed_at": "2026-09-19T10:00:00+00:00",
    }
    bindings = {
        "premium_ai_budget_cents": 0,
        "outbound_domain_verified": True,
        "source_health_ok": True,
    }
    result = run_observer_cycle(
        dsn="postgresql://observer",
        operational_bindings=bindings,
        operational_evidence_max_age_seconds=3600,
        now_utc=datetime(2026, 9, 19, 17, 0, tzinfo=timezone.utc),
        output_path=tmp_path / "latest.json",
        rpc_factory=_factory([], [], operational),
    )
    assert result["decision"]["available"] is False
    assert result["decision"]["reason"] == "operational_evidence_stale"
    assert result["operating_board"]["available"] is False
    assert result["operational_evidence"]["freshness"]["fresh"] is False
