from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.advertising_api import create_advertising_router
from empire_os.advertising_landing_feedback import (
    LandingPageOutcomeEvidence,
    review_landing_page_feedback,
)
from empire_os.advertising_review import CampaignEconomicsReview


def campaign(**overrides):
    values = {
        "campaign_id": "campaign-1",
        "observation_count": 2,
        "total_spend_cents": 10000,
        "total_conversions": 5,
        "total_attributed_revenue_cents": 25000,
        "total_attributed_gross_profit_cents": 15000,
        "roas": 2.5,
        "profit_roas": 1.5,
        "attribution_complete": True,
        "review_state": "evidence_complete_for_operator_review",
        "blockers": (),
    }
    values.update(overrides)
    return CampaignEconomicsReview(**values)


def landing(**overrides):
    values = {
        "campaign_id": "campaign-1",
        "landing_page_id": "page-1",
        "evidence_ref": "landing:observation:1",
        "sessions": 100,
        "qualified_actions": 8,
    }
    values.update(overrides)
    return LandingPageOutcomeEvidence(**values)


def test_complete_campaign_and_landing_evidence_is_review_ready_only():
    result = review_landing_page_feedback(
        campaign=campaign(),
        landing=landing(),
    )
    assert result.review_ready is True
    assert result.landing_conversion_rate == 0.08
    assert result.campaign_roas == 2.5
    assert result.campaign_profit_roas == 1.5
    assert result.execution_authority == "none"
    assert result.budget_mutation is False
    assert result.landing_page_mutation is False
    assert result.publishing_execution is False


def test_missing_landing_evidence_preserves_unknown():
    result = review_landing_page_feedback(
        campaign=campaign(),
        landing=landing(
            evidence_ref=None,
            sessions=None,
            qualified_actions=None,
        ),
    )
    assert result.review_ready is False
    assert result.landing_conversion_rate is None
    assert "landing_page_evidence_missing" in result.blockers
    assert "landing_sessions_unknown" in result.blockers


def test_incomplete_campaign_attribution_blocks_feedback_review():
    result = review_landing_page_feedback(
        campaign=campaign(
            attribution_complete=False,
            roas=None,
            profit_roas=None,
            blockers=("revenue_attribution_incomplete",),
        ),
        landing=landing(),
    )
    assert result.review_ready is False
    assert "campaign_attribution_incomplete" in result.blockers


def test_campaign_identity_mismatch_is_rejected():
    try:
        review_landing_page_feedback(
            campaign=campaign(),
            landing=landing(campaign_id="campaign-2"),
        )
    except ValueError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_api_landing_feedback_is_observe_only():
    app = FastAPI()
    app.include_router(create_advertising_router())
    observation = {
        "platform": "google",
        "campaign_id": "campaign-1",
        "spend_cents": 10000,
        "attributed_revenue_cents": 25000,
        "attributed_gross_profit_cents": 15000,
        "clicks": 20,
        "impressions": 200,
        "conversions": 5,
        "observed_at": "2026-09-20T15:00:00+00:00",
        "source": "canonical:test",
    }
    response = TestClient(app).post(
        "/v1/advertising/campaigns/landing-feedback/preview",
        json={
            "campaign_id": "campaign-1",
            "landing_page_id": "page-1",
            "landing_evidence_ref": "landing:observation:1",
            "landing_sessions": 100,
            "landing_qualified_actions": 8,
            "observations": [observation],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["budget_mutation"] is False
    assert body["landing_page_mutation"] is False
    assert body["publishing_execution"] is False
    assert body["feedback"]["review_ready"] is True
