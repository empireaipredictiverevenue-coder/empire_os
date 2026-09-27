from empire_os.autonomous_revenue_os import RevenueDecisionPacket
from empire_os.revenue_os_readiness import assess_revenue_os_readiness


def packet(**overrides):
    values = {
        "packet_key": "packet-1",
        "recommended_workstream": "buyer_allocation",
        "recommended_job_type": "plan_controlled_allocation",
        "forecast_direction": "up",
        "capital_candidate_id": "candidate-1",
        "demand_plan_ref": "demand-plan-1",
        "enterprise_blockers": (),
        "evidence_refs": ("astra:1", "forecast:1", "capital:1"),
    }
    values.update(overrides)
    return RevenueDecisionPacket(**values)


def test_complete_packet_is_ready_for_operator_review_only():
    result = assess_revenue_os_readiness(packet())
    assert result.ready_for_operator_review is True
    assert result.blockers == ()
    assert result.mode == "OBSERVE"
    assert result.side_effects == "none"
    assert result.execution_authority == "none"


def test_enterprise_blockers_survive_into_readiness_gate():
    result = assess_revenue_os_readiness(
        packet(enterprise_blockers=("backup_unknown",))
    )
    assert result.ready_for_operator_review is False
    assert result.blockers == ("backup_unknown",)


def test_missing_forecast_blocks_review():
    result = assess_revenue_os_readiness(
        packet(forecast_direction=None)
    )
    assert result.ready_for_operator_review is False
    assert "forecast_direction_missing" in result.blockers


def test_missing_capital_and_demand_evidence_are_explicit():
    result = assess_revenue_os_readiness(
        packet(
            capital_candidate_id=None,
            demand_plan_ref=None,
        )
    )
    assert result.ready_for_operator_review is False
    assert result.blockers == (
        "capital_candidate_missing",
        "demand_plan_missing",
    )


def test_missing_astra_decision_blocks_review():
    result = assess_revenue_os_readiness(
        packet(
            recommended_workstream=None,
            recommended_job_type=None,
        )
    )
    assert result.ready_for_operator_review is False
    assert result.blockers == (
        "astra_job_type_missing",
        "astra_workstream_missing",
    )
