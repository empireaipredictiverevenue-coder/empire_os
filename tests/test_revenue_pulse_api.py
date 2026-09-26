from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_pulse_api import create_revenue_pulse_router


def test_revenue_pulse_api_is_read_only_and_truth_separated():
    app = FastAPI()
    app.include_router(create_revenue_pulse_router())
    client = TestClient(app)

    status = client.get("/v1/revenue-pulse/status")
    assert status.status_code == 200
    assert status.json()["execution_allowed"] is False
    assert status.json()["forecast_separate_from_revenue"] is True

    response = client.post(
        "/v1/revenue-pulse/preview",
        json={
            "current": {
                "label": "current_24h",
                "hours": 24,
                "acquisitions": 8,
                "qualified": 4,
                "buyer_reviews": 2,
                "delivered_outreach": 2,
                "commercial_replies": 0,
                "commercial_terms": 0,
                "verified_payments": 0,
                "fulfilments": 0,
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
                "evidence_refs": ["canonical:pulse"],
            },
            "highest_priority_blocker": "buyer_conversation",
            "blocker_state": "blocked",
            "forecasts": [
                {
                    "horizon": "30d",
                    "forecast_revenue_cents": 100000,
                    "confidence": 0.6,
                    "evidence_refs": ["forecast:v1"],
                }
            ],
            "storm": {
                "opportunity_count": 8,
                "max_multiplier": 2.454,
                "priority_boost_max": 36.35,
                "evidence_refs": ["nws:dfw"],
            },
            "spatial_physical": {
                "volumetric_observations": 4,
                "physical_observations": 3,
                "modeled_opportunities": 2,
                "max_combined_priority_boost": 48.2,
                "evidence_refs": ["spatial:dfw", "physical:dfw"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_allowed"] is False
    assert payload["pulse_state"] == "conversation_blocked"
    assert payload["recognized_revenue_truth"]["recognized_revenue_cents"] == 0
    assert payload["forecast"]["items"][0]["forecast_revenue_cents"] == 100000
    assert payload["storm_pulse"]["opportunity_count"] == 8
    assert payload["spatial_physical_pulse"]["modeled_opportunities"] == 2
    assert payload["recognized_revenue_truth"]["recognized_revenue_cents"] == 0
