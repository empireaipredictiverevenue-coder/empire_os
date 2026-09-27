from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.recommendation_intelligence import (
    AiAnswerObservation,
    analyse_recommendation_visibility,
)


def answer(**overrides):
    values = {
        "query": "best predictive revenue software",
        "engine": "answer_engine",
        "observed_at": "2026-09-22T20:00:00+00:00",
        "provenance": ("capture:1",),
        "answer_ref": "answer:1",
        "cited_urls": ("https://empire-ai.co.uk/product",),
        "mentioned_domains": ("empire-ai.co.uk",),
        "recommended_domains": ("empire-ai.co.uk",),
    }
    values.update(overrides)
    return AiAnswerObservation(**values)


def test_observed_brand_recommendation_metrics_are_evidence_scoped():
    result = analyse_recommendation_visibility(
        (
            answer(),
            answer(
                query="best revenue intelligence platform",
                cited_urls=("https://competitor.example/guide",),
                mentioned_domains=("competitor.example",),
                recommended_domains=("competitor.example",),
                provenance=("capture:2",),
            ),
        ),
        brand_domains=("empire-ai.co.uk",),
        competitor_domains=("competitor.example",),
    )
    assert result.available is True
    assert result.observed_answers == 2
    assert result.brand_answer_presence_rate == 0.5
    assert result.brand_citation_rate == 0.5
    assert result.brand_recommendation_rate == 0.5
    assert result.share_of_observed_recommendations == 0.5
    assert result.recommendation_gap_queries == (
        "best revenue intelligence platform",
    )
    assert result.market_share_claimed is False
    assert result.recommendation_guaranteed is False
    assert result.execution_authority == "none"


def test_no_captures_remain_unknown_not_zero():
    result = analyse_recommendation_visibility(
        (),
        brand_domains=("empire-ai.co.uk",),
    )
    assert result.available is False
    assert result.brand_recommendation_rate is None
    assert result.share_of_observed_recommendations is None
    assert result.reason == "no_observed_ai_answer_evidence"


def test_preview_api_is_observe_only():
    app = FastAPI()
    app.include_router(create_search_router())
    client = TestClient(app)

    response = client.post(
        "/v1/search/recommendation-visibility/preview",
        json={
            "brand_domains": ["empire-ai.co.uk"],
            "competitor_domains": ["competitor.example"],
            "observations": [{
                "query": "best predictive revenue software",
                "engine": "answer_engine",
                "observed_at": "2026-09-22T20:00:00+00:00",
                "provenance": ["capture:1"],
                "answer_ref": "answer:1",
                "cited_urls": ["https://empire-ai.co.uk/product"],
                "mentioned_domains": ["empire-ai.co.uk"],
                "recommended_domains": ["empire-ai.co.uk"],
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["recommendation_guaranteed"] is False
    assert body["analysis"]["brand_recommendation_rate"] == 1.0
