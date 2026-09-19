from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.advertising_api import create_advertising_router
from empire_os.advertising_brain import normalise_ad_observation
from empire_os.advertising_freshness import review_advertising_evidence


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def observation(**overrides):
    values = {
        "platform": "google",
        "campaign_id": "campaign-1",
        "creative_id": "creative-1",
        "spend_cents": 10000,
        "attributed_revenue_cents": 30000,
        "attributed_gross_profit_cents": 15000,
        "impressions": 1000,
        "clicks": 50,
        "conversions": 4,
        "observed_at": "2026-09-20T11:00:00+00:00",
        "source": "google_ads_read_adapter",
    }
    values.update(overrides)
    return normalise_ad_observation(values)


def test_two_complete_creatives_are_comparable():
    review = review_advertising_evidence(
        (
            observation(),
            observation(
                creative_id="creative-2",
                spend_cents=5000,
                attributed_revenue_cents=10000,
                attributed_gross_profit_cents=5000,
            ),
        ),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert review.fresh_for_review is True
    assert review.creative_comparison_available is True
    assert len(review.creatives) == 2
    by_id = {row.creative_id: row for row in review.creatives}
    assert by_id["creative-1"].roas == 3.0
    assert by_id["creative-1"].profit_roas == 1.5
    assert by_id["creative-2"].roas == 2.0
    assert by_id["creative-2"].profit_roas == 1.0
    assert review.execution_authority == "none"
    assert review.budget_mutation is False


def test_stale_and_future_observations_block_fresh_review():
    review = review_advertising_evidence(
        (
            observation(observed_at="2026-09-20T08:00:00+00:00"),
            observation(
                creative_id="creative-2",
                observed_at="2026-09-20T12:05:00+00:00",
            ),
        ),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert review.fresh_for_review is False
    assert "observation_0_evidence_stale" in review.blockers
    assert "observation_1_evidence_from_future" in review.blockers


def test_missing_creative_identity_prevents_comparison():
    review = review_advertising_evidence(
        (
            observation(creative_id=None),
            observation(creative_id="creative-2"),
        ),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert review.fresh_for_review is True
    assert review.creative_comparison_available is False
    assert "creative_identity_missing" in review.blockers


def test_incomplete_attribution_stays_unknown():
    review = review_advertising_evidence(
        (
            observation(
                attributed_revenue_cents=None,
                attributed_gross_profit_cents=None,
            ),
            observation(creative_id="creative-2"),
        ),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert review.creative_comparison_available is False
    first = {row.creative_id: row for row in review.creatives}["creative-1"]
    assert first.roas is None
    assert first.profit_roas is None
    assert first.attribution_complete is False
    assert "creative_creative-1_attribution_incomplete" in review.blockers


def test_empty_observations_do_not_invent_creative_performance():
    review = review_advertising_evidence(
        (),
        campaign_id="campaign-1",
        now=NOW,
        max_age_seconds=7200,
    )
    assert review.observation_count == 0
    assert review.fresh_for_review is False
    assert review.creative_comparison_available is False
    assert review.creatives == ()
    assert review.blockers == ("campaign_observations_missing",)


def test_api_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_advertising_router())
    response = TestClient(app).post(
        "/v1/advertising/campaigns/evidence/preview",
        json={
            "campaign_id": "campaign-1",
            "now_utc": "2026-09-20T12:00:00+00:00",
            "max_age_seconds": 7200,
            "observations": [
                {
                    "platform": "google",
                    "campaign_id": "campaign-1",
                    "creative_id": "creative-1",
                    "spend_cents": 10000,
                    "attributed_revenue_cents": 30000,
                    "attributed_gross_profit_cents": 15000,
                    "conversions": 4,
                    "observed_at": "2026-09-20T11:00:00+00:00",
                    "source": "google_ads_read_adapter",
                },
                {
                    "platform": "google",
                    "campaign_id": "campaign-1",
                    "creative_id": "creative-2",
                    "spend_cents": 5000,
                    "attributed_revenue_cents": 10000,
                    "attributed_gross_profit_cents": 5000,
                    "conversions": 2,
                    "observed_at": "2026-09-20T11:10:00+00:00",
                    "source": "google_ads_read_adapter",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["campaign_creation"] is False
    assert body["budget_mutation"] is False
    assert body["pause_mutation"] is False
    assert body["retarget_execution"] is False
    assert body["review"]["fresh_for_review"] is True
    assert body["review"]["creative_comparison_available"] is True


def test_api_rejects_naive_now_timestamp():
    app = FastAPI()
    app.include_router(create_advertising_router())
    response = TestClient(app).post(
        "/v1/advertising/campaigns/evidence/preview",
        json={
            "campaign_id": "campaign-1",
            "now_utc": "2026-09-20T12:00:00",
            "observations": [],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "now_utc must include timezone"
