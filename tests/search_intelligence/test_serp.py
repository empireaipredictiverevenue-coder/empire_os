from datetime import datetime, timezone

import pytest

from empire_os.search_intelligence.serp import (
    SearchFabricSerpAdapter,
    SerpSnapshotError,
)


FIXED_TIME = datetime(
    2026, 9, 19, 15, 40, tzinfo=timezone.utc
)


def test_serp_snapshot_preserves_real_search_fabric_evidence():
    def fake_search(query, num, engine=None):
        assert query == "predictive revenue software"
        assert num == 5
        assert engine is None
        return {
            "organic": [{
                "title": "Empire AI",
                "link": "https://empire-ai.co.uk/",
                "snippet": "Predictive revenue.",
                "position": 1,
                "relevance_score": 0.94,
            }],
            "searchParameters": {
                "q": query,
                "num": num,
                "engine": "duckduckgo_html",
                "quality_gate": "lexical_v1",
                "cache": False,
            },
        }

    snapshot = SearchFabricSerpAdapter(
        fake_search,
        clock=lambda: FIXED_TIME,
    ).snapshot("predictive revenue software", num=5)

    assert snapshot.available is True
    assert snapshot.observed_at == FIXED_TIME.isoformat()
    assert snapshot.engine == "duckduckgo_html"
    assert len(snapshot.results) == 1
    result = snapshot.results[0]
    assert result.position == 1
    assert result.url == "https://empire-ai.co.uk/"
    assert result.relevance_score == 0.94
    assert result.provenance == (
        "search_fabric",
        "engine:duckduckgo_html",
        "quality_gate:lexical_v1",
        "cache:false",
    )


def test_serp_snapshot_never_invents_missing_positions():
    def fake_search(query, num, engine=None):
        return {
            "organic": [{
                "title": "Unranked",
                "link": "https://example.test/",
                "snippet": "",
            }],
            "searchParameters": {
                "q": query,
                "num": num,
                "engine": "duckduckgo_html",
            },
        }

    snapshot = SearchFabricSerpAdapter(
        fake_search,
        clock=lambda: FIXED_TIME,
    ).snapshot("test")
    assert snapshot.available is False
    assert snapshot.results == ()


def test_failed_search_is_explicitly_unavailable_not_fake_empty_success():
    def fake_search(query, num, engine=None):
        return {
            "organic": [],
            "searchParameters": {
                "q": query,
                "num": num,
                "engine": "none",
            },
            "error": "All engines failed",
        }

    snapshot = SearchFabricSerpAdapter(
        fake_search,
        clock=lambda: FIXED_TIME,
    ).snapshot("test")
    assert snapshot.available is False
    assert snapshot.engine == "none"
    assert snapshot.error == "All engines failed"
    assert snapshot.results == ()


def test_serp_query_is_required():
    with pytest.raises(SerpSnapshotError, match="query required"):
        SearchFabricSerpAdapter(lambda *args, **kwargs: {}).snapshot("  ")
