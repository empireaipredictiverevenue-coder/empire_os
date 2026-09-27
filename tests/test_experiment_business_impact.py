from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.experiment_api import create_experiment_router
from empire_os.experiment_business_impact import (
    ExperimentBusinessImpactEvidence,
    review_experiment_business_impact,
)
from empire_os.experiment_conclusion import CausalConclusionPacket
from empire_os.experiment_conclusion_freshness import (
    ExperimentConclusionFreshness,
)


def conclusion():
    return CausalConclusionPacket(
        conclusion_key="conclusion-1",
        experiment_key="experiment-1",
        metric="recognized_revenue_cents",
        control_count=5,
        treatment_count=5,
        control_mean=10.0,
        treatment_mean=12.0,
        absolute_lift=2.0,
        relative_lift=0.2,
        effect_direction="positive_observed_lift",
        assignment_integrity_verified=True,
        exposure_integrity_verified=True,
        outcome_window_closed=True,
        evidence_refs=("assignment:1", "outcome-window:1"),
    )


def freshness(*, fresh=True, blockers=()):
    return ExperimentConclusionFreshness(
        conclusion_key="conclusion-1",
        fresh_for_operator_review=fresh,
        evidence_age_seconds=3600.0,
        blockers=tuple(blockers),
    )


def evidence(**overrides):
    values = {
        "conclusion_key": "conclusion-1",
        "commercial_outcome_ref": "commercial-outcome:1",
        "recognized_revenue_ref": "revenue:recognized:1",
        "realized_gp_ref": "gross-profit:1",
        "realized_gp_cents": 4200,
    }
    values.update(overrides)
    return ExperimentBusinessImpactEvidence(**values)


def test_fresh_conclusion_and_real_commercial_evidence_are_review_ready():
    result = review_experiment_business_impact(
        conclusion=conclusion(),
        freshness=freshness(),
        evidence=evidence(),
    )
    assert result.outcome_link_ready is True
    assert result.commercial_impact_ready is True
    assert result.realized_gp_cents == 4200
    assert result.statistical_significance_available is False
    assert result.execution_authority == "none"
    assert result.rollout_enabled is False
    assert result.revenue_mutation is False
    assert result.accounting_mutation is False


def test_outcome_can_link_while_revenue_and_gp_remain_unknown():
    result = review_experiment_business_impact(
        conclusion=conclusion(),
        freshness=freshness(),
        evidence=evidence(
            recognized_revenue_ref=None,
            realized_gp_ref=None,
            realized_gp_cents=None,
        ),
    )
    assert result.outcome_link_ready is True
    assert result.commercial_impact_ready is False
    assert "recognized_revenue_evidence_missing" in result.blockers
    assert "realized_gross_profit_value_unknown" in result.blockers


def test_stale_conclusion_blocks_impact_review():
    result = review_experiment_business_impact(
        conclusion=conclusion(),
        freshness=freshness(
            fresh=False,
            blockers=("outcome_window_evidence_stale",),
        ),
        evidence=evidence(),
    )
    assert result.outcome_link_ready is False
    assert result.commercial_impact_ready is False
    assert "causal_conclusion_not_fresh_for_operator_review" in result.blockers


def test_api_business_impact_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_experiment_router())
    response = TestClient(app).post(
        "/v1/experiments/conclusions/business-impact/preview",
        json={
            "experiment_key": "experiment-1",
            "metric": "recognized_revenue_cents",
            "control_values": [10, 10, 10, 10, 10],
            "treatment_values": [12, 12, 12, 12, 12],
            "evidence_refs": ["assignment:1", "outcome-window:1"],
            "assignment_integrity_verified": True,
            "exposure_integrity_verified": True,
            "outcome_window_closed": True,
            "minimum_per_arm": 5,
            "conclusion_key": "conclusion-1",
            "evidence": {"source": "canonical"},
            "experiment_observed_at": "2026-09-20T12:00:00+00:00",
            "outcome_window_closed_at": "2026-09-20T14:00:00+00:00",
            "now_utc": "2026-09-20T15:00:00+00:00",
            "commercial_outcome_ref": "commercial-outcome:1",
            "recognized_revenue_ref": "revenue:recognized:1",
            "realized_gp_ref": "gross-profit:1",
            "realized_gp_cents": 4200,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["rollout_enabled"] is False
    assert body["pricing_mutation"] is False
    assert body["revenue_mutation"] is False
    assert body["accounting_mutation"] is False
    assert body["impact"]["commercial_impact_ready"] is True
