import pytest

from empire_os.demand_readiness import (
    DemandEvidenceSnapshot,
    assess_demand_readiness,
)


def test_complete_observed_evidence_becomes_review_ready():
    result = assess_demand_readiness(
        DemandEvidenceSnapshot(
            plan_id="plan-1",
            observed_demand_signals=10,
            verified_audience_size=2000,
            qualified_inbound_events=8,
            historical_conversion_rate=0.15,
            observed_cost_cents=5000,
            evidence_refs=("search-gap:1", "crm:2", "ads:3"),
        )
    )
    assert result.ready_for_review is True
    assert result.readiness_reason == "evidence_sufficient_for_operator_review"
    assert result.execution_authority == "none"
    assert result.approval_required is True


def test_missing_observed_fields_are_explicit():
    result = assess_demand_readiness(
        DemandEvidenceSnapshot(
            plan_id="plan-2",
            observed_demand_signals=4,
            verified_audience_size=None,
            qualified_inbound_events=2,
            historical_conversion_rate=None,
            observed_cost_cents=None,
            evidence_refs=("search-gap:1",),
        )
    )
    assert result.ready_for_review is False
    assert result.readiness_reason == "required_observed_evidence_missing"
    assert result.missing_evidence == (
        "verified_audience_size",
        "historical_conversion_rate",
        "observed_cost_cents",
    )


def test_zero_demand_signal_is_not_invented():
    result = assess_demand_readiness(
        DemandEvidenceSnapshot(
            plan_id="plan-3",
            observed_demand_signals=0,
            verified_audience_size=1000,
            qualified_inbound_events=0,
            historical_conversion_rate=0.1,
            observed_cost_cents=1000,
            evidence_refs=("audience:1",),
        )
    )
    assert result.ready_for_review is False
    assert "observed_demand_signals" in result.missing_evidence


def test_invalid_conversion_rate_fails_closed():
    with pytest.raises(ValueError, match="between 0 and 1"):
        assess_demand_readiness(
            DemandEvidenceSnapshot(
                plan_id="plan-4",
                observed_demand_signals=1,
                verified_audience_size=100,
                qualified_inbound_events=1,
                historical_conversion_rate=1.1,
                observed_cost_cents=100,
                evidence_refs=("evidence:1",),
            )
        )


def test_readiness_requires_evidence_refs():
    with pytest.raises(ValueError, match="requires evidence"):
        assess_demand_readiness(
            DemandEvidenceSnapshot(
                plan_id="plan-5",
                observed_demand_signals=1,
                verified_audience_size=100,
                qualified_inbound_events=1,
                historical_conversion_rate=0.1,
                observed_cost_cents=100,
                evidence_refs=(),
            )
        )
