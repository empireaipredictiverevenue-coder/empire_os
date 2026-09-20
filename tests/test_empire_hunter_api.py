from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.hunter.api import create_hunter_router


def client():
    app = FastAPI()
    app.include_router(create_hunter_router())
    return TestClient(app)


def test_health_is_observe_only_and_native():
    response = client().get("/v1/hunter/health")

    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "Empire Hunter"
    assert body["mode"] == "OBSERVE"
    assert body["third_party_contact_data"] is False
    assert body["outbound_execution"] is False


def test_pattern_preview_learns_first_party_pattern():
    response = client().post(
        "/v1/hunter/pattern/preview",
        json={
            "domain": "acme.com",
            "observations": [
                {
                    "email": "jane.smith@acme.com",
                    "person_name": "Jane Smith",
                    "person_bound": True,
                    "first_party": True,
                },
                {
                    "email": "john.doe@acme.com",
                    "person_name": "John Doe",
                    "person_bound": True,
                    "first_party": True,
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pattern"]["pattern"] == "first.last"
    assert body["execution_allowed"] is False


def test_contact_outcome_preview_rejects_verified_bounce():
    response = client().post(
        "/v1/hunter/outcomes/contact/preview",
        json={
            "contact": {
                "email": "jane.smith@acme.com",
                "state": "probable",
                "confidence": 0.78,
                "source": "empire_pattern_brain",
                "person_name": "Jane Smith",
                "person_bound": True,
                "first_party": False,
                "syntax_ok": True,
                "mx_ok": True,
            },
            "observations": [
                {
                    "email": "jane.smith@acme.com",
                    "event_type": "bounced",
                    "verified": True,
                    "evidence_ref": "provider_event:1",
                }
            ],
        },
    )

    assert response.status_code == 200
    calibration = response.json()["calibration"]
    assert calibration["state"] == "rejected"
    assert calibration["posterior_confidence"] <= 0.10
