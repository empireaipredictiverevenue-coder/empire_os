from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.advertising_adapters import InjectedAdvertisingReadAdapter
from empire_os.advertising_api import create_advertising_router


def client(adapters=None):
    app = FastAPI()
    app.include_router(create_advertising_router(adapters))
    return TestClient(app)


def google_adapter():
    return InjectedAdvertisingReadAdapter(
        "google",
        "account-1",
        lambda account_id, start_date, end_date: [{
            "campaign_id": "campaign-1",
            "creative_id": "creative-1",
            "spend_cents": 10000,
            "attributed_revenue_cents": 25000,
            "impressions": 1000,
            "clicks": 50,
            "conversions": 4,
            "observed_at": "2026-09-19T18:50:00+00:00",
        }],
    )


def test_health_has_no_ad_mutation_authority():
    response = client().get("/v1/advertising/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["campaign_creation"] is False
    assert body["budget_mutation"] is False
    assert body["pause_mutation"] is False
    assert body["retarget_execution"] is False


def test_provider_status_requires_bound_adapter():
    response = client().get("/v1/advertising/google/status")
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "advertising_read_adapter_not_activated"
    )


def test_google_observations_are_read_only():
    response = client({"google": google_adapter()}).get(
        "/v1/advertising/google/observations"
        "?start_date=2026-09-01&end_date=2026-09-19"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "google"
    assert body["count"] == 1
    assert body["execution_authority"] == "none"
    assert body["budget_mutation"] is False
    assert body["items"][0]["campaign_id"] == "campaign-1"
    assert body["items"][0]["attributed_revenue_cents"] == 25000


def test_provider_status_reports_injected_transport():
    response = client({"google": google_adapter()}).get(
        "/v1/advertising/google/status"
    )
    assert response.status_code == 200
    status = response.json()["status"]
    assert status["provider"] == "google"
    assert status["available"] is True
    assert status["reason"] == "injected_read_transport_ready"


def test_unknown_provider_observations_fail_closed():
    response = client({"google": google_adapter()}).get(
        "/v1/advertising/meta/observations"
        "?start_date=2026-09-01&end_date=2026-09-19"
    )
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "advertising_read_adapter_not_activated"
    )
