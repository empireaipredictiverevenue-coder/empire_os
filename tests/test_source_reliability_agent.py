import pytest

from empire_os.source_reliability_agent import (
    build_source_reliability_state,
    source_reliability_agent_status,
)


def test_source_id_is_required():
    with pytest.raises(ValueError):
        build_source_reliability_state(
            source_id="",
            runs=1,
            accepted=1,
            errors=0,
        )


def test_unknown_economics_stay_unknown():
    row = build_source_reliability_state(
        source_id="recc_solar",
        runs=1,
        accepted=10,
        errors=0,
    )
    assert row.verified_revenue_cents is None
    assert row.cost_cents is None
    assert row.recommendation == "continue_exploration"


def test_quarantined_source_is_recovery_only_not_retired():
    row = build_source_reliability_state(
        source_id="broken_source",
        runs=3,
        accepted=0,
        errors=3,
    )
    assert row.runtime_health == "QUARANTINED"
    assert row.scheduling_weight == 0.1
    assert row.recommendation == "recovery_only"
    assert row.permanent_retirement_allowed is False
    assert row.canonical_delete_performed is False


def test_downstream_conversation_yield_can_increase_bounded_sampling():
    row = build_source_reliability_state(
        source_id="useful_source",
        runs=5,
        accepted=50,
        errors=0,
        prospects=20,
        qualified=10,
        conversations=3,
        complete_records=40,
        identity_resolved=35,
    )
    assert row.runtime_health == "HEALTHY"
    assert row.qualification_rate == 0.5
    assert row.conversation_rate == 0.3
    assert row.scheduling_weight == 1.15
    assert row.recommendation == "increase_bounded_sampling"


def test_status_has_no_delete_or_execution_authority():
    row = source_reliability_agent_status()
    assert row["canonical_delete_authority"] is False
    assert row["permanent_retirement_allowed"] is False
    assert row["execution_authority"] == "none"
