from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.advertising_api import create_advertising_router
from empire_os.advertising_brain import normalise_ad_observation
from empire_os.advertising_drift import review_advertising_drift


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def observation(**overrides):
    values = {
        "platform": "google",
        "campaign_id": "campaign-1",
        "creative_id": "creative-1",
        "spend_cents": 10000,
        "attributed_revenue_cents": 20000,
        "attributed_gross_profit_cents": 10000,
        "conversions": 2,
        "observed_at": "2026-09-20T11:00:00+00:00",
        "source": "google_ads_read_adapter",
    }
    values.update(overrides)
    return normalise_ad_observation(values)


def test_creative_profit_roas_drift_is_observed_only():
    result = review_advertising_drift(
        baseline=(observation(),),
        current=(observation(
            attributed_revenue_cents=30000,
            attributed_gross_profit_cents=15000,
            observed_at="2026-09-20T11:30:00+00:00",
        ),),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.comparison_available is True
    row = result.creative_drift[0]
    assert row.roas_delta == 1.0
    assert row.profit_roas_delta == 0.5
    assert row.direction == "improving"
    assert result.execution_authority == "none"
    assert result.budget_mutation is False


def test_missing_creative_in_current_blocks_comparison():
    result = review_advertising_drift(
        baseline=(observation(),),
        current=(observation(creative_id="creative-2"),),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.comparison_available is False
    assert any(
        "comparison_evidence_missing" in blocker
        for blocker in result.blockers
    )


def test_stale_baseline_blocks_comparison():
    result = review_advertising_drift(
        baseline=(observation(
            observed_at="2026-09-20T08:00:00+00:00",
        ),),
        current=(observation(
            observed_at="2026-09-20T11:30:00+00:00",
        ),),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.comparison_available is False
    assert "baseline_evidence_not_fresh" in result.blockers


def test_api_drift_preview_never_mutates_campaign():
    app = FastAPI()
    app.include_router(create_advertising_router())
    payload = {
        "campaign_id": "campaign-1",
        "now_utc": "2026-09-20T12:00:00+00:00",
        "max_age_seconds": 7200,
        "baseline_observations": [{
            "platform": "google",
            "campaign_id": "campaign-1",
            "creative_id": "creative-1",
            "spend_cents": 10000,
            "attributed_revenue_cents": 20000,
            "attributed_gross_profit_cents": 10000,
            "conversions": 2,
            "observed_at": "2026-09-20T11:00:00+00:00",
            "source": "google_ads_read_adapter",
        }],
        "current_observations": [{
            "platform": "google",
            "campaign_id": "campaign-1",
            "creative_id": "creative-1",
            "spend_cents": 10000,
            "attributed_revenue_cents": 30000,
            "attributed_gross_profit_cents": 15000,
            "conversions": 3,
            "observed_at": "2026-09-20T11:30:00+00:00",
            "source": "google_ads_read_adapter",
        }],
    }
    response = TestClient(app).post(
        "/v1/advertising/campaigns/drift/preview",
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["campaign_creation"] is False
    assert body["budget_mutation"] is False
    assert body["pause_mutation"] is False
    assert body["retarget_execution"] is False
    assert body["drift"]["comparison_available"] is True
    assert body["drift"]["creative_drift"][0]["direction"] == "improving"
