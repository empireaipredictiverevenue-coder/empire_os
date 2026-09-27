from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.ai_visibility import (
    AiCitationObservation,
)
from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.citation_gap import analyse_citation_gap


def citation(url):
    return AiCitationObservation(
        query="predictive revenue software",
        engine="answer_engine",
        observed_at="2026-09-20T14:00:00+00:00",
        cited_url=url,
        source_url="https://answer.example/result/1",
        citation_position=1,
        provenance=("capture:1",),
    )


def test_competitor_only_citation_is_observed_gap():
    result = analyse_citation_gap(
        (citation("https://competitor.example/page"),),
        query="predictive revenue software",
        engine="answer_engine",
        empire_domains=("empire-ai.co.uk",),
        competitor_domains=("competitor.example",),
    )
    assert result.available is True
    assert result.empire_cited is False
    assert result.competitor_cited_domains == ("competitor.example",)
    assert result.citation_gap_observed is True
    assert result.execution_authority == "none"


def test_empire_citation_closes_observed_gap():
    result = analyse_citation_gap(
        (
            citation("https://competitor.example/page"),
            citation("https://empire-ai.co.uk/guide"),
        ),
        query="predictive revenue software",
        engine="answer_engine",
        empire_domains=("empire-ai.co.uk",),
        competitor_domains=("competitor.example",),
    )
    assert result.empire_cited is True
    assert result.citation_gap_observed is False


def test_no_observations_remain_unknown():
    result = analyse_citation_gap(
        (),
        query="predictive revenue software",
        engine="answer_engine",
        empire_domains=("empire-ai.co.uk",),
        competitor_domains=("competitor.example",),
    )
    assert result.available is False
    assert result.empire_cited is None
    assert result.citation_gap_observed is None
    assert result.reason == "no_observed_ai_citation_evidence"


def test_preview_api_is_observe_only():
    app = FastAPI()
    app.include_router(create_search_router())
    client = TestClient(app)
    response = client.post(
        "/v1/search/citation-gap/preview",
        json={
            "query": "predictive revenue software",
            "engine": "answer_engine",
            "empire_domains": ["empire-ai.co.uk"],
            "competitor_domains": ["competitor.example"],
            "observations": [{
                "query": "predictive revenue software",
                "engine": "answer_engine",
                "observed_at": "2026-09-20T14:00:00+00:00",
                "cited_url": "https://competitor.example/page",
                "source_url": "https://answer.example/result/1",
                "citation_position": 1,
                "provenance": ["capture:1"],
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["analysis"]["citation_gap_observed"] is True
