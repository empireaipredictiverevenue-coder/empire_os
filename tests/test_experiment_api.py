from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.experiment_api import create_experiment_router


def client():
    app = FastAPI()
    app.include_router(create_experiment_router())
    return TestClient(app)


def payload():
    return {
        "experiment_key": "exp-1",
        "metric": "revenue_per_subject",
        "control_values": [10, 10, 10, 10, 10],
        "treatment_values": [12, 12, 12, 12, 12],
        "evidence_refs": ["assignment:a", "exposure:b", "outcome:c"],
        "assignment_integrity_verified": True,
        "exposure_integrity_verified": True,
        "outcome_window_closed": True,
        "minimum_per_arm": 5,
    }


def test_health_has_no_mutation_authority():
    response = client().get("/v1/experiments/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["traffic_mutation"] is False
    assert body["rollout_enabled"] is False
    assert body["pricing_mutation"] is False


def test_verified_analysis_is_review_eligible_only():
    response = client().post(
        "/v1/experiments/analysis/preview",
        json=payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_authority"] == "none"
    analysis = body["analysis"]
    assert analysis["causal_claim_eligible"] is True
    assert analysis["interpretation"] == "causal_estimate_eligible_for_review"
    assert analysis["estimate"]["relative_lift"] == 0.2


def test_missing_integrity_downgrades_to_observed_lift_only():
    body = payload()
    body["exposure_integrity_verified"] = False
    response = client().post(
        "/v1/experiments/analysis/preview",
        json=body,
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["causal_claim_eligible"] is False
    assert analysis["interpretation"] == (
        "observed_lift_only_integrity_not_verified"
    )


def test_insufficient_samples_are_explicit():
    body = payload()
    body["control_values"] = [10, 10]
    body["treatment_values"] = [12, 12]
    response = client().post(
        "/v1/experiments/analysis/preview",
        json=body,
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["causal_claim_eligible"] is False
    assert analysis["interpretation"] == "insufficient_observed_samples"


def test_negative_outcome_is_rejected():
    body = payload()
    body["control_values"] = [10, 10, 10, 10, -1]
    response = client().post(
        "/v1/experiments/analysis/preview",
        json=body,
    )
    assert response.status_code == 422
    assert "nonnegative" in response.json()["detail"]
