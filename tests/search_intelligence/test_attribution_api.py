from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router


def client():
    app = FastAPI()
    app.include_router(create_search_router())
    return TestClient(app)


def recognized_event(**overrides):
    row = {
        "id": "event-1",
        "event_type": "revenue_recognized",
        "actual_revenue": True,
        "fulfilment_order_id": "order-1",
        "amount_cents": 25000,
        "occurred_at": "2026-09-19T23:50:00+00:00",
    }
    row.update(overrides)
    return row


def test_revenue_preview_endpoint_is_observe_only():
    response = client().post(
        "/v1/search/revenue/preview",
        json={
            "site_id": "site-1",
            "page_id": "page-1",
            "query": "predictive revenue platform",
            "external_session_id": "session-1",
            "prospect_id": "prospect-1",
            "opportunity_id": "opportunity-1",
            "commercial_event": recognized_event(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_allowed"] is False
    assert body["preview"]["revenue_cents"] == 25000
    assert body["preview"]["actual_revenue"] is True
    assert body["preview"]["write_authority"] == "none"


def test_non_revenue_payment_event_is_rejected():
    response = client().post(
        "/v1/search/revenue/preview",
        json={
            "site_id": "site-1",
            "page_id": "page-1",
            "commercial_event": recognized_event(
                event_type="payment_verified",
                actual_revenue=False,
            ),
        },
    )
    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "commercial event is not recognized actual revenue"
    )


def test_preview_requires_search_touch_evidence():
    response = client().post(
        "/v1/search/revenue/preview",
        json={
            "site_id": "site-1",
            "commercial_event": recognized_event(),
        },
    )
    assert response.status_code == 422
    assert "observed page, query, or session" in response.json()["detail"]
