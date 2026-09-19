from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.experiment_analysis import analyze_observed_experiment
from empire_os.experiment_api import create_experiment_router
from empire_os.experiment_conclusion import build_causal_conclusion
from empire_os.experiment_conclusion_freshness import (
    assess_conclusion_freshness,
)


NOW = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)


def conclusion():
    analysis = analyze_observed_experiment(
        experiment_key="exp-1",
        metric="revenue_per_subject",
        control_values=[10, 10, 10, 10, 10],
        treatment_values=[12, 12, 12, 12, 12],
        evidence_refs=("assignment:a", "exposure:b", "outcome:c"),
        assignment_integrity_verified=True,
        exposure_integrity_verified=True,
        outcome_window_closed=True,
        minimum_per_arm=5,
    )
    return build_causal_conclusion(
        conclusion_key="exp-1-conclusion-v1",
        analysis=analysis,
    )


def test_fresh_closed_window_is_operator_reviewable():
    result = assess_conclusion_freshness(
        conclusion=conclusion(),
        experiment_observed_at="2026-09-20T12:00:00+00:00",
        outcome_window_closed_at="2026-09-20T16:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.fresh_for_operator_review is True
    assert result.blockers == ()
    assert result.evidence_age_seconds == 7200.0
    assert result.execution_authority == "none"
    assert result.rollout_enabled is False


def test_stale_outcome_window_blocks_current_review():
    result = assess_conclusion_freshness(
        conclusion=conclusion(),
        experiment_observed_at="2026-09-19T08:00:00+00:00",
        outcome_window_closed_at="2026-09-19T10:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.fresh_for_operator_review is False
    assert "outcome_window_evidence_stale" in result.blockers


def test_window_closed_before_experiment_observation_is_blocked():
    result = assess_conclusion_freshness(
        conclusion=conclusion(),
        experiment_observed_at="2026-09-20T16:00:00+00:00",
        outcome_window_closed_at="2026-09-20T15:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.fresh_for_operator_review is False
    assert (
        "outcome_window_closed_before_experiment_observation"
        in result.blockers
    )


def test_api_freshness_preview_never_mutates_experiment():
    app = FastAPI()
    app.include_router(create_experiment_router())
    response = TestClient(app).post(
        "/v1/experiments/conclusions/freshness/preview",
        json={
            "conclusion_key": "exp-1-conclusion-v1",
            "experiment_key": "exp-1",
            "metric": "revenue_per_subject",
            "control_values": [10, 10, 10, 10, 10],
            "treatment_values": [12, 12, 12, 12, 12],
            "evidence_refs": ["assignment:a", "exposure:b", "outcome:c"],
            "assignment_integrity_verified": True,
            "exposure_integrity_verified": True,
            "outcome_window_closed": True,
            "minimum_per_arm": 5,
            "evidence": {"source": "canonical_experiment_outcomes"},
            "experiment_observed_at": "2026-09-20T12:00:00+00:00",
            "outcome_window_closed_at": "2026-09-20T16:00:00+00:00",
            "now_utc": "2026-09-20T18:00:00+00:00",
            "max_age_seconds": 21600,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["traffic_mutation"] is False
    assert body["rollout_enabled"] is False
    assert body["pricing_mutation"] is False
    assert body["freshness"]["fresh_for_operator_review"] is True
