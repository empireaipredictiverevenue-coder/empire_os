import pytest

from empire_os.astra_evidence import build_astra_evidence


def operational_row():
    return {
        "replies_waiting": 2,
        "failed_jobs": 1,
        "owned_inventory_count": 12,
        "qualified_unallocated_count": 3,
        "active_buyer_capacity": 5,
        "buyer_candidates_due": 4,
    }


def policy_bindings():
    return {
        "premium_ai_budget_cents": 2500,
        "outbound_domain_verified": True,
        "source_health_ok": True,
    }


def test_complete_evidence_builds_observe_snapshot():
    result = build_astra_evidence(
        actual_revenue_cents=10000,
        operational_row=operational_row(),
        bindings=policy_bindings(),
    )
    assert result.available is True
    assert result.missing == ()
    assert result.snapshot.execution_mode == "observe"
    assert result.snapshot.actual_revenue_cents == 10000
    assert result.snapshot.active_buyer_capacity == 5
def test_missing_signal_keeps_snapshot_unavailable():
    row = operational_row()
    row.pop("active_buyer_capacity")
    result = build_astra_evidence(
        actual_revenue_cents=0,
        operational_row=row,
        bindings=policy_bindings(),
    )
    assert result.available is False
    assert result.snapshot is None
    assert result.missing == ("active_buyer_capacity",)
    assert "active_buyer_capacity" not in result.observed


def test_missing_policy_binding_is_not_coerced_to_false_or_zero():
    bindings = policy_bindings()
    bindings.pop("source_health_ok")
    result = build_astra_evidence(
        actual_revenue_cents=0,
        operational_row=operational_row(),
        bindings=bindings,
    )
    assert result.available is False
    assert "source_health_ok" in result.missing


def test_invalid_boolean_binding_fails_closed():
    bindings = policy_bindings()
    bindings["outbound_domain_verified"] = "unknown"
    with pytest.raises(ValueError, match="explicit boolean"):
        build_astra_evidence(
            actual_revenue_cents=0,
            operational_row=operational_row(),
            bindings=bindings,
        )
