from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.demand_api import create_demand_router


def client():
    app = FastAPI()
    app.include_router(create_demand_router())
    return TestClient(app)


def payload():
    return {
        "plan_id": "plan-1",
        "observed_demand_signals": 10,
        "verified_audience_size": 2000,
        "qualified_inbound_events": 8,
        "historical_conversion_rate": 0.15,
        "observed_cost_cents": 5000,
        "evidence_refs": ["search-gap:1", "crm:2", "ads:3"],
    }


def test_health_is_non_executing():
    response = client().get("/v1/demand/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    assert body["publishing_enabled"] is False
    assert body["outbound_enabled"] is False
    assert body["ad_spend_enabled"] is False


def test_complete_evidence_can_be_review_ready_only():
    response = client().post(
        "/v1/demand/readiness/preview",
        json=payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    readiness = body["readiness"]
    assert readiness["ready_for_review"] is True
    assert readiness["approval_required"] is True


def test_missing_optional_evidence_stays_not_ready():
    body = payload()
    body["verified_audience_size"] = None
    body["historical_conversion_rate"] = None
    body["observed_cost_cents"] = None
    response = client().post(
        "/v1/demand/readiness/preview",
        json=body,
    )
    assert response.status_code == 200
    readiness = response.json()["readiness"]
    assert readiness["ready_for_review"] is False
    assert "verified_audience_size" in readiness["missing_evidence"]
    assert "historical_conversion_rate" in readiness["missing_evidence"]


def test_invalid_conversion_rate_is_rejected():
    body = payload()
    body["historical_conversion_rate"] = 1.5
    response = client().post(
        "/v1/demand/readiness/preview",
        json=body,
    )
    assert response.status_code == 422
