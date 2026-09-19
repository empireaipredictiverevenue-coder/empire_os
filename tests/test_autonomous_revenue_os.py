import pytest

from empire_os.autonomous_revenue_os import (
    RevenueDecisionPacket,
    compose_revenue_decision_packet,
)


def test_packet_composes_observed_recommendations_without_execution():
    packet = compose_revenue_decision_packet(
        packet_key="packet-1",
        astra_decision={
            "workstream": "buyer_allocation",
            "recommended_job_type": "plan_controlled_allocation",
        },
        predictive_forecast={"direction": "up"},
        capital_recommendation={"candidate_id": "market-london-roofing"},
        demand_plan_ref="demand-plan-1",
        enterprise_blockers=("backup_restore_unknown",),
        evidence_refs=("astra:1", "forecast:1", "capital:1"),
    )
    assert packet.recommended_workstream == "buyer_allocation"
    assert packet.forecast_direction == "up"
    assert packet.capital_candidate_id == "market-london-roofing"
    assert packet.mode == "OBSERVE"
    assert packet.side_effects == "none"
    assert packet.execution_authority == "none"


def test_missing_optional_signals_remain_unknown():
    packet = compose_revenue_decision_packet(
        packet_key="packet-2",
        astra_decision=None,
        predictive_forecast=None,
        capital_recommendation=None,
        demand_plan_ref=None,
        evidence_refs=("evidence:baseline",),
    )
    assert packet.recommended_workstream is None
    assert packet.recommended_job_type is None
    assert packet.forecast_direction is None
    assert packet.capital_candidate_id is None
    assert packet.demand_plan_ref is None


def test_enterprise_blockers_are_preserved_deterministically():
    packet = compose_revenue_decision_packet(
        packet_key="packet-3",
        astra_decision={},
        predictive_forecast={},
        capital_recommendation={},
        demand_plan_ref=None,
        enterprise_blockers=("slo_unknown", "backup_unknown", "slo_unknown"),
        evidence_refs=("evidence:1",),
    )
    assert packet.enterprise_blockers == ("backup_unknown", "slo_unknown")


def test_packet_requires_evidence():
    with pytest.raises(ValueError, match="requires evidence"):
        compose_revenue_decision_packet(
            packet_key="packet-4",
            astra_decision={},
            predictive_forecast={},
            capital_recommendation={},
            demand_plan_ref=None,
            evidence_refs=(),
        )


def test_execution_authority_cannot_be_enabled():
    packet = RevenueDecisionPacket(
        packet_key="packet-5",
        recommended_workstream=None,
        recommended_job_type=None,
        forecast_direction=None,
        capital_candidate_id=None,
        demand_plan_ref=None,
        enterprise_blockers=(),
        evidence_refs=("evidence:1",),
        execution_authority="commercial",
    )
    with pytest.raises(ValueError, match="cannot grant execution authority"):
        packet.validate()
