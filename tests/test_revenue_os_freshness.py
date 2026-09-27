from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_os_api import create_revenue_os_router
from empire_os.revenue_os_freshness import assess_revenue_os_freshness


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def fresh_map():
    return {
        "astra": "2026-09-20T11:30:00+00:00",
        "predictive": "2026-09-20T11:20:00+00:00",
        "capital": "2026-09-20T11:10:00+00:00",
        "demand": "2026-09-20T11:00:00+00:00",
        "enterprise": "2026-09-20T10:50:00+00:00",
    }


def test_all_fresh_components_are_review_ready():
    result = assess_revenue_os_freshness(
        fresh_map(),
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.fresh_for_review is True
    assert result.blockers == ()
    assert result.execution_authority == "none"
    assert result.side_effects == "none"


def test_missing_component_timestamp_blocks_review():
    values = fresh_map()
    values["capital"] = None
    result = assess_revenue_os_freshness(
        values,
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.fresh_for_review is False
    assert "capital_evidence_timestamp_missing" in result.blockers


def test_stale_component_blocks_review():
    values = fresh_map()
    values["demand"] = "2026-09-20T08:00:00+00:00"
    result = assess_revenue_os_freshness(
        values,
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.fresh_for_review is False
    assert "demand_evidence_stale" in result.blockers


def test_future_dated_component_blocks_review():
    values = fresh_map()
    values["enterprise"] = "2026-09-20T12:05:00+00:00"
    result = assess_revenue_os_freshness(
        values,
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.fresh_for_review is False
    assert "enterprise_evidence_from_future" in result.blockers


def test_api_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_revenue_os_router())
    client = TestClient(app)
    response = client.post(
        "/v1/revenue-os/freshness/preview",
        json={
            "now_utc": "2026-09-20T12:00:00+00:00",
            "max_age_seconds": 7200,
            "astra_observed_at": "2026-09-20T11:30:00+00:00",
            "predictive_observed_at": "2026-09-20T11:20:00+00:00",
            "capital_observed_at": "2026-09-20T11:10:00+00:00",
            "demand_observed_at": "2026-09-20T11:00:00+00:00",
            "enterprise_observed_at": "2026-09-20T10:50:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["spend_execution"] is False
    assert body["payment_execution"] is False
    assert body["deployment_execution"] is False
    assert body["freshness"]["fresh_for_review"] is True
