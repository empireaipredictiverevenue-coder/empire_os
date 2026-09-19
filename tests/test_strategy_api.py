from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.strategy_api import create_strategy_router


def client():
    app = FastAPI()
    app.include_router(create_strategy_router())
    return TestClient(app)


def test_health_is_observe_only():
    body = client().get("/v1/strategy/health").json()
    assert body["execution_authority"] == "none"
    assert body["market_entry_execution"] is False
    assert body["publishing_enabled"] is False


def test_keyword_preview_does_not_publish():
    response = client().post(
        "/v1/strategy/keywords/rank/preview",
        json={"keywords": [{
            "keyword": "predictive revenue",
            "observed_demand": .8,
            "commercial_intent": .9,
            "product_fit": .95,
            "buyer_fit": .8,
            "coverage_gap": .9,
            "competitor_gap": .8,
            "ai_citation_gap": .8,
            "conversion_evidence": .6,
            "strategic_category_value": 1.0,
            "confidence": .8,
            "evidence_refs": ["kw:1"],
        }]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ranked"][0]["keyword"] == "predictive revenue"
    assert body["publishing_enabled"] is False


def test_ai_capability_review_never_activates_provider():
    response = client().post(
        "/v1/strategy/ai-capability/review",
        json={"data": {
            "capability_key": "verifier",
            "problem": "Need independent verification.",
            "strategic_advantage": "Higher trust.",
            "evidence_refs": ["e:1"],
            "strategic_value": .9,
            "proprietary_data_advantage": .4,
            "expected_quality_gain": .9,
            "privacy_importance": .5,
            "cost_sensitivity": .5,
            "switching_flexibility": .8,
            "confidence": .8,
        }},
    )
    assert response.status_code == 200
    assert response.json()["provider_activation"] is False


def test_market_domination_review_is_observe_only():
    response = client().post(
        "/v1/strategy/market-domination/review",
        json={"data": {
            "market_key": "uk-home-services",
            "territory_key": "manchester",
            "corridor_key": "roofing:manchester",
            "product_key": "territory-seat",
            "demand_strength": .8,
            "buyer_capacity_strength": .8,
            "competition_inverse": .6,
            "product_fit": .9,
            "data_advantage": .9,
            "search_authority": .7,
            "ai_visibility": .6,
            "partner_density": .7,
            "margin_potential": .85,
            "retention_expansion": .8,
            "confidence": .8,
            "verified_buyer_count": 2,
            "verified_capacity_units": 20,
            "verified_outcome_count": 5,
            "repeat_outcome_count": 2,
            "expected_gross_profit_cents": 400000,
            "realized_gross_profit_cents": 300000,
            "time_to_revenue_days": 18,
            "downside_cents": 50000,
            "evidence_refs": ["market:1", "buyer:1", "outcome:1"],
        }},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["market_entry_execution"] is False
    assert body["territory_allocation"] is False
    assert body["market_control_claimed"] is False
    assert body["execution_authority"] == "none"


def test_market_domination_portfolio_never_allocates():
    response = client().post(
        "/v1/strategy/market-domination/portfolio/preview",
        json={"markets": []},
    )
    assert response.status_code == 200
    assert response.json()["allocation_execution"] is False


def test_competitive_search_presence_is_not_market_share():
    response = client().post(
        "/v1/strategy/competitive/search-presence/preview",
        json={
            "observations": [
                {
                    "query": "predictive revenue",
                    "domain": "empire-ai.co.uk",
                    "position": 1,
                    "observed_at": "2026-09-20T00:00:00Z",
                    "provenance": ["search_fabric"],
                },
                {
                    "query": "predictive revenue",
                    "domain": "competitor.example",
                    "position": 2,
                    "observed_at": "2026-09-20T00:00:00Z",
                    "provenance": ["search_fabric"],
                },
            ],
            "empire_domains": ["empire-ai.co.uk"],
            "competitor_domains": ["competitor.example"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["market_share"] is None
    assert body["market_share_inferred"] is False


def test_competitive_landscape_stays_observe_only():
    response = client().post(
        "/v1/strategy/competitive/landscape/preview",
        json={
            "competitor_profiles": [{
                "competitor_key": "c1",
                "domain": "competitor.example",
                "observed_facts": [{
                    "fact_type": "product",
                    "summary": "Observed product page.",
                    "source_ref": "web:c1:product",
                    "observed_at": "2026-09-20T00:00:00Z",
                    "confidence": .9,
                }],
            }],
            "search_observations": [],
            "ai_citation_observations": [],
            "empire_domains": ["empire-ai.co.uk"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["market_entry_execution"] is False
    assert body["publishing_enabled"] is False
    assert body["outreach_enabled"] is False
    assert body["execution_authority"] == "none"
