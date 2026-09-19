import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router, router
from empire_os.search_intelligence.commander import SearchCommanderAgent
from empire_os.search_intelligence.config import SearchIntelligenceConfig
from empire_os.search_intelligence.models import SearchExecutionMode, SearchPage


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class FakeSearchRepository:
    def __init__(self):
        self.calls = []

    def summary(self):
        self.calls.append(("summary", None))
        return {
            "pages": 1,
            "opportunities": 1,
            "revenue_cents": 12500,
        }

    def _rows(self, name, limit):
        self.calls.append((name, limit))
        return [{"kind": name, "rank": 1}]

    def pages(self, *, limit):
        return self._rows("pages", limit)

    def opportunities(self, *, limit):
        return self._rows("opportunities", limit)

    def indexation(self, *, limit):
        return self._rows("indexation", limit)

    def decay(self, *, limit):
        return self._rows("decay", limit)

    def cannibalisation(self, *, limit):
        return self._rows("cannibalisation", limit)

    def alerts(self, *, limit):
        return self._rows("alerts", limit)

    def revenue(self, *, limit):
        return self._rows("revenue", limit)


def _repository_client(repository):
    app = FastAPI()
    app.include_router(create_search_router(repository))
    return TestClient(app)


def test_mode_is_hard_clamped_to_observe(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_MODE", "APPROVE_AND_EXECUTE")
    cfg = SearchIntelligenceConfig.from_env()
    assert cfg.mode is SearchExecutionMode.OBSERVE
    assert SearchCommanderAgent(cfg).mutation_allowed() is False


def test_health_reports_no_mutations():
    response = _client().get("/v1/search/health")
    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "OBSERVE"
    assert body["mutations_enabled"] is False


def test_repository_endpoint_fails_closed_not_fake_empty():
    response = _client().get("/v1/search/pages")
    assert response.status_code == 503
    assert response.json()["detail"] == "canonical_search_repository_not_activated"


def test_analysis_is_recommendation_only():
    factors = {
        "originality": 0.9,
        "useful_content": 0.9,
        "intent_coverage": 0.9,
        "factual_support": 0.9,
        "source_quality": 0.9,
        "topic_completeness": 0.9,
        "page_uniqueness": 0.9,
        "internal_link_support": 0.9,
        "structured_data_validity": 0.9,
        "user_value": 0.9,
        "duplication_risk": 0.1,
        "thin_content_risk": 0.1,
        "unsupported_claims_risk": 0.1,
        "keyword_stuffing_risk": 0.1,
        "template_duplication_risk": 0.1,
        "hallucination_risk": 0.1,
    }
    response = _client().post("/v1/search/analyse", json={
        "page": {
            "url": "https://empire-ai.co.uk/guides/revenue",
            "title": "Predictive Revenue Guide",
            "meta_description": "A guide to predictive revenue.",
        },
        "quality_factors": factors,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["recommendation_only"] is True


def test_invalid_quality_factor_env_fails_safe(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_MIN_QUALITY_FACTORS", "not-an-int")
    cfg = SearchIntelligenceConfig.from_env()
    assert cfg.minimum_known_quality_factors == 8



def test_health_exposes_contract_version_and_repository_state():
    response = _client().get("/v1/search/health")
    assert response.status_code == 200
    body = response.json()
    assert body["api_contract_version"] == "search-v1"
    assert body["repository_available"] is False


def test_injected_repository_stabilises_collection_envelope():
    repository = FakeSearchRepository()
    client = _repository_client(repository)

    response = client.get("/v1/search/pages?limit=7")
    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "source": "canonical_search_repository",
        "count": 1,
        "limit": 7,
        "items": [{"kind": "pages", "rank": 1}],
    }
    assert repository.calls == [("pages", 7)]


def test_repository_summary_is_nested_under_stored_metrics():
    repository = FakeSearchRepository()
    response = _repository_client(repository).get("/v1/search/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["repository_available"] is True
    assert body["api_contract_version"] == "search-v1"
    assert body["stored_metrics"]["revenue_cents"] == 12500


def test_collection_limit_is_contract_bounded_by_fastapi():
    repository = FakeSearchRepository()
    client = _repository_client(repository)
    assert client.get("/v1/search/pages?limit=0").status_code == 422
    assert client.get("/v1/search/pages?limit=501").status_code == 422
