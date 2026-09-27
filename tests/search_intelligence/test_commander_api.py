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

    def internal_links(self, *, limit):
        return self._rows("internal_links", limit)

    def ai_visibility(self, *, limit):
        return self._rows("ai_visibility", limit)

    def backlinks(self, *, limit):
        return self._rows("backlinks", limit)


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


def test_competitor_gap_preview_is_observe_only_and_evidence_backed():
    response = _client().post(
        "/v1/search/competitor-gap/preview",
        json={
            "snapshot": {
                "query": "predictive revenue software",
                "observed_at": "2026-09-19T15:00:00+00:00",
                "engine": "duckduckgo_html",
                "quality_gate": "lexical_v1",
                "cache": False,
                "available": True,
                "results": [
                    {
                        "title": "Competitor",
                        "url": "https://competitor.example/",
                        "position": 1,
                        "engine": "duckduckgo_html",
                        "provenance": ["search_fabric"],
                    },
                    {
                        "title": "Empire",
                        "url": "https://empire-ai.co.uk/",
                        "position": 2,
                        "engine": "duckduckgo_html",
                        "provenance": ["search_fabric"],
                    },
                ],
            },
            "empire_domains": ["empire-ai.co.uk"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_allowed"] is False
    assert body["analysis"]["empire_best_position"] == 2
    assert body["opportunity_inputs"] == {
        "competitor_presence": 0.5,
        "current_empire_coverage": 0.5,
        "content_gap": 0.5,
    }


def test_competitor_gap_preview_rejects_missing_empire_domain():
    response = _client().post(
        "/v1/search/competitor-gap/preview",
        json={
            "snapshot": {
                "query": "test",
                "observed_at": "2026-09-19T15:00:00+00:00",
                "engine": "none",
                "available": False,
                "results": [],
            },
            "empire_domains": [],
        },
    )
    assert response.status_code == 422


def test_internal_links_endpoint_uses_canonical_repository_contract():
    repository = FakeSearchRepository()
    response = _repository_client(repository).get("/v1/search/internal-links?limit=9")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "canonical_search_repository"
    assert body["limit"] == 9
    assert body["items"] == [{"kind": "internal_links", "rank": 1}]
    assert repository.calls[-1] == ("internal_links", 9)


def test_ai_visibility_repository_endpoint_uses_canonical_contract():
    repository = FakeSearchRepository()
    response = _repository_client(repository).get(
        "/v1/search/ai-visibility?limit=11"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "canonical_search_repository"
    assert body["limit"] == 11
    assert body["items"] == [{"kind": "ai_visibility", "rank": 1}]


def test_ai_visibility_preview_counts_only_observed_citations():
    response = _client().post(
        "/v1/search/ai-visibility/preview",
        json={
            "query": "predictive revenue software",
            "engine": "answer_engine",
            "empire_domains": ["empire-ai.co.uk"],
            "observations": [
                {
                    "query": "predictive revenue software",
                    "engine": "answer_engine",
                    "observed_at": "2026-09-19T20:00:00+00:00",
                    "cited_url": "https://empire-ai.co.uk/guides/revenue",
                    "source_url": "https://answer.example/result/1",
                    "citation_position": 2,
                    "mention_text": "Empire AI",
                    "provenance": ["provider_capture:1"],
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["analysis"]["available"] is True
    assert body["analysis"]["empire_cited"] is True
    assert body["analysis"]["empire_positions"] == [2]


def test_ai_visibility_preview_keeps_missing_evidence_unknown():
    response = _client().post(
        "/v1/search/ai-visibility/preview",
        json={
            "query": "predictive revenue software",
            "engine": "answer_engine",
            "empire_domains": ["empire-ai.co.uk"],
            "observations": [],
        },
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["available"] is False
    assert analysis["empire_cited"] is None
    assert analysis["reason"] == "no_observed_ai_citation_evidence"


def test_backlinks_repository_endpoint_uses_canonical_contract():
    repository = FakeSearchRepository()
    response = _repository_client(repository).get(
        "/v1/search/backlinks?limit=13"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "canonical_search_repository"
    assert body["limit"] == 13
    assert body["items"] == [{"kind": "backlinks", "rank": 1}]


def test_backlinks_preview_is_evidence_only():
    response = _client().post(
        "/v1/search/backlinks/preview",
        json={
            "empire_domains": ["empire-ai.co.uk"],
            "observations": [{
                "source_url": "https://partner.example/article",
                "target_url": "https://empire-ai.co.uk/guides/revenue",
                "observed_at": "2026-09-20T13:00:00+00:00",
                "anchor_text": "predictive revenue",
                "rel": "",
                "source": "crawler_observation",
                "provenance": ["crawler:1"],
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["link_building_execution"] is False
    assert body["authority_score_invented"] is False
    assert body["analysis"]["available"] is True
    assert body["analysis"]["observed_backlinks"] == 1
    assert body["analysis"]["authority_score"] is None


def test_backlinks_preview_keeps_missing_evidence_unknown():
    response = _client().post(
        "/v1/search/backlinks/preview",
        json={
            "empire_domains": ["empire-ai.co.uk"],
            "observations": [],
        },
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["available"] is False
    assert analysis["observed_backlinks"] == 0
    assert analysis["authority_score"] is None
    assert analysis["reason"] == "no_observed_backlink_evidence"



def test_tag_intelligence_preview_is_observe_only():
    response = _client().post(
        "/v1/search/tag-intelligence/preview",
        json={
            "page_tags": {
                "url": "https://example.com/landing",
                "title": "",
                "meta_description": "",
                "canonical_url": "",
                "robots": "noindex,follow",
                "open_graph": {},
                "twitter": {},
                "meta_keywords_present": True,
            },
            "measurement_tags": {
                "meta_pixel_ids": ["123"],
                "meta_capi_enabled": True,
                "meta_event_id_dedup": False,
            },
            "expectations": {
                "intended_public": True,
                "meta_ads_expected": True,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "empire.tag_intelligence.v1"
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_allowed"] is False
    assert body["analysis"]["critical_count"] >= 2
    assert body["analysis"]["execution_authority"] == "none"
    assert body["analysis"]["estimated_revenue_loss_cents"] is None


def test_tag_intelligence_product_is_in_catalog_and_ready():
    response = _client().get(
        "/v1/search/products/tag_intelligence_monitor"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["product"]["commercial_model"] == "monthly_subscription"
    assert body["product"]["publishing_authority"] is False
    assert body["readiness"]["status"] == "READY"
    assert body["readiness"]["required"]["tag_intelligence"] is True



def test_tag_change_preview_detects_measurement_regression():
    response = _client().post(
        "/v1/search/tag-intelligence/change-preview",
        json={
            "previous_page_tags": {
                "robots": "index,follow",
            },
            "current_page_tags": {
                "robots": "noindex,follow",
            },
            "previous_measurement_tags": {
                "meta_pixel_ids": ["123"],
            },
            "current_measurement_tags": {
                "meta_pixel_ids": [],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["change_monitor"]["critical_change_count"] == 2
    assert body["change_monitor"]["automatic_repair"] is False
