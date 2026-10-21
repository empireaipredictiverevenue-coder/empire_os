"""Live Quora research uses ONE bounded canonical zero-key Search Fabric query."""
from datetime import datetime, timezone

import pytest

from scripts.review_search_quora_one_shot_20261021 import review_one_shot
from empire_os.search_intelligence.quora_intelligence import QuoraEvidenceError


NOW = datetime(2026, 10, 21, 19, tzinfo=timezone.utc)


def test_default_is_plan_only_no_network():
    def forbidden(*_args, **_kwargs):
        raise AssertionError("No network use expected")
    result = review_one_shot(
        "QROOF001", live=False, search_fn=forbidden, clock=lambda: NOW,
    )
    assert result["mode"] == "PLAN_ONLY"
    assert result["source_query"].startswith('site:quora.com "')
    assert result["search_request_performed"] is False
    assert result["execution_authority"] == "NONE"


def test_single_live_query_goes_through_existing_source_without_cache():
    called = []
    def observed(query, *, num, engine, use_cache):
        called.append((query, num, engine, use_cache))
        return {
            "organic": [{
                "title": "How can I tell whether I need a roof replacement?",
                "link": "https://www.quora.com/How-to-tell-if-my-roof-needs-replacement",
                "snippet": "One answer to an existing roof question",
                "position": 1,
            }],
            "searchParameters": {"engine": "bing_html", "cache": False},
        }
    result = review_one_shot(
        "QROOF001", live=True, search_fn=observed, clock=lambda: NOW
    )
    assert len(called) == 1
    assert called[0][1:] == (3, "bing_html", False)
    assert result["source_status"] == "CANDIDATE_RESULTS_OBSERVED"
    assert len(result["question_candidates"]) == 1
    assert result["question_candidates"][0]["quora_origin_page_verified"] is False
    assert result["verified_question_count"] == 0
    assert result["posting_authorized"] is False


def test_failed_provider_is_held_instead_of_fake_research():
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider failure should not be echoed")
    result = review_one_shot(
        "QROOF001", live=True, search_fn=unavailable, clock=lambda: NOW
    )
    # Failure should never leak the exception or yield a fake Quora page.
    assert result["question_candidates"] == []
    assert result["verified_question_count"] == 0


def test_cached_serp_cannot_be_claimed_fresh():
    def cached(query, **_kwargs):
        return {
            "organic": [{
                "title": "How can I tell whether I need a roof replacement?",
                "link": "https://www.quora.com/How-to-tell-if-my-roof-needs-replacement",
                "position": 1,
            }],
            "searchParameters": {"engine": "bing_html", "cache": True},
        }
    result = review_one_shot(
        "QROOF001", live=True, search_fn=cached, clock=lambda: NOW
    )
    assert result["source_status"] == "HELD_OR_UNVERIFIED_SOURCE"
    assert result["question_candidates"] == []


def test_unknown_seed_never_queries_provider():
    with pytest.raises(QuoraEvidenceError):
        review_one_shot("QFAKE", live=True, search_fn=lambda *_a,**_k: None)
