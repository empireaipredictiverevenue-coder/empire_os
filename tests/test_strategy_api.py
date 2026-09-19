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
