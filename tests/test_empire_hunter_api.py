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


def test_prioritize_preview_never_uses_actual_revenue():
    response = client().post(
        "/v1/hunter/prioritize/preview",
        json={
            "entity_id": "entity-1",
            "evidence_confidence": 0.9,
            "omega_score": 88,
            "omega_confidence": 0.8,
            "buyer_demand_strength": 0.9,
            "buyer_demand_confidence": 0.9,
            "contact_ready": False,
            "modeled_expected_gp_cents": 250000,
            "enrichment_cost_cents": 3000,
            "evidence_refs": ["omega:1", "buyer-demand:1"],
        },
    )

    assert response.status_code == 200
    priority = response.json()["priority"]
    assert priority["depth"] == "deep"
    assert priority["economics_is_forecast"] is True
    assert priority["actual_revenue_used"] is False


def test_signals_preview_requires_real_change():
    response = client().post(
        "/v1/hunter/signals/preview",
        json={
            "entity_id": "entity-1",
            "observed_at": "2026-09-20T14:30:00Z",
            "previous": {
                "people": [{"name": "Old Owner", "title": "Owner"}],
                "emails": ["old@example.com"],
            },
            "current": {
                "people": [{"name": "New Owner", "title": "President"}],
                "emails": ["new@example.com"],
            },
            "evidence_refs": ["site:before", "site:after"],
        },
    )

    assert response.status_code == 200
    types = {
        item["signal_type"]
        for item in response.json()["signals"]
    }
    assert "leadership_change" in types
    assert "contact_surface_change" in types
