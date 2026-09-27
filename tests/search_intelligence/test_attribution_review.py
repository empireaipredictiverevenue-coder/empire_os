from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.attribution_review import (
    review_search_attribution,
)


def event(**overrides):
    row = {
        "id": "event-1",
        "event_type": "revenue_recognized",
        "actual_revenue": True,
        "fulfilment_order_id": "order-1",
        "amount_cents": 25000,
        "occurred_at": "2026-09-20T15:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_search_touch_before_revenue_is_revenue_attribution_ready():
    review = review_search_attribution(
        site_id="site-1",
        page_id="page-1",
        query="predictive revenue",
        commercial_event=event(),
        search_touch_observed_at="2026-09-18T10:00:00+00:00",
        touch_evidence_ref="search-session:1",
    )
    assert review.revenue_attribution_ready is True
    assert review.profit_attribution_ready is False
    assert review.realized_gross_profit_cents is None
    assert "observed_cost_evidence_missing" in review.blockers
    assert review.write_authority == "none"
    assert review.revenue_mutation is False
    assert review.accounting_mutation is False


def test_profit_attribution_requires_observed_cost_evidence():
    review = review_search_attribution(
        site_id="site-1",
        external_session_id="session-1",
        commercial_event=event(),
        search_touch_observed_at="2026-09-18T10:00:00+00:00",
        touch_evidence_ref="search-session:1",
        observed_cost_cents=10000,
        cost_evidence_ref="cost:order-1",
    )
    assert review.revenue_attribution_ready is True
    assert review.profit_attribution_ready is True
    assert review.realized_gross_profit_cents == 15000


def test_revenue_before_search_touch_is_not_attributable():
    review = review_search_attribution(
        site_id="site-1",
        page_id="page-1",
        commercial_event=event(),
        search_touch_observed_at="2026-09-21T10:00:00+00:00",
        touch_evidence_ref="search-page-view:1",
        observed_cost_cents=10000,
        cost_evidence_ref="cost:order-1",
    )
    assert review.revenue_attribution_ready is False
    assert review.profit_attribution_ready is False
    assert review.realized_gross_profit_cents is None
    assert "revenue_precedes_search_touch" in review.blockers


def test_outside_attribution_window_is_explicitly_blocked():
    review = review_search_attribution(
        site_id="site-1",
        query="predictive revenue",
        commercial_event=event(),
        search_touch_observed_at="2026-07-01T10:00:00+00:00",
        touch_evidence_ref="search-query:1",
        max_attribution_lag_seconds=86400,
    )
    assert review.revenue_attribution_ready is False
    assert "search_touch_outside_attribution_window" in review.blockers


def test_api_review_never_publishes_indexes_or_mutates_accounting():
    app = FastAPI()
    app.include_router(create_search_router())
    response = TestClient(app).post(
        "/v1/search/revenue/review/preview",
        json={
            "site_id": "site-1",
            "page_id": "page-1",
            "query": "predictive revenue",
            "external_session_id": "session-1",
            "commercial_event": event(),
            "search_touch_observed_at": "2026-09-18T10:00:00+00:00",
            "touch_evidence_ref": "search-session:1",
            "observed_cost_cents": 10000,
            "cost_evidence_ref": "cost:order-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["publishing_execution"] is False
    assert body["indexation_execution"] is False
    assert body["revenue_mutation"] is False
    assert body["accounting_mutation"] is False
    assert body["review"]["revenue_attribution_ready"] is True
    assert body["review"]["profit_attribution_ready"] is True
    assert body["review"]["realized_gross_profit_cents"] == 15000
