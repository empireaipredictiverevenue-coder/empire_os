from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.advertising_api import create_advertising_router
from empire_os.advertising_brain import normalise_ad_observation
from empire_os.advertising_review import review_campaign_economics


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
        "observed_at": "2026-09-20T10:00:00+00:00",
        "source": "google_ads_read_adapter",
    }
    values.update(overrides)
    return normalise_ad_observation(values)


def test_complete_attribution_produces_observed_economics():
    result = review_campaign_economics(
        (observation(), observation(
            spend_cents=5000,
            attributed_revenue_cents=10000,
            attributed_gross_profit_cents=5000,
            conversions=2,
            observed_at="2026-09-20T11:00:00+00:00",
        )),
        campaign_id="campaign-1",
    )
    assert result.total_spend_cents == 15000
    assert result.total_attributed_revenue_cents == 40000
    assert result.total_attributed_gross_profit_cents == 20000
    assert result.total_conversions == 6
    assert result.roas == 2.6667
    assert result.profit_roas == 1.3333
    assert result.attribution_complete is True


def test_partial_attribution_stays_unknown():
    result = review_campaign_economics(
        (
            observation(),
            observation(
                attributed_revenue_cents=None,
                attributed_gross_profit_cents=None,
            ),
        ),
        campaign_id="campaign-1",
    )
    assert result.total_attributed_revenue_cents is None
    assert result.total_attributed_gross_profit_cents is None
    assert result.roas is None
    assert result.profit_roas is None
    assert result.attribution_complete is False
    assert "revenue_attribution_incomplete" in result.blockers


def test_empty_observations_do_not_invent_performance():
    result = review_campaign_economics(
        (),
        campaign_id="campaign-1",
    )
    assert result.observation_count == 0
    assert result.roas is None
    assert result.profit_roas is None
    assert result.review_state == "insufficient_attribution_evidence"
    assert result.blockers == ("campaign_observations_missing",)


def test_review_never_grants_ad_mutation():
    result = review_campaign_economics(
        (observation(),),
        campaign_id="campaign-1",
    )
    assert result.execution_authority == "none"
    assert result.budget_mutation is False
    assert result.pause_mutation is False
    assert result.retarget_execution is False


def test_preview_api_is_observe_only():
    app = FastAPI()
    app.include_router(create_advertising_router())
    client = TestClient(app)
    response = client.post(
        "/v1/advertising/campaigns/review/preview",
        json={
            "campaign_id": "campaign-1",
            "observations": [{
                "platform": "google",
                "campaign_id": "campaign-1",
                "spend_cents": 10000,
                "attributed_revenue_cents": 30000,
                "attributed_gross_profit_cents": 15000,
                "conversions": 4,
                "observed_at": "2026-09-20T10:00:00+00:00",
                "source": "google_ads_read_adapter",
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["budget_mutation"] is False
    assert body["pause_mutation"] is False
    assert body["retarget_execution"] is False
    assert body["review"]["attribution_complete"] is True
