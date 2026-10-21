"""Bounded Quora search fallback reuses the original SEO engine without spam."""
from datetime import datetime, timezone

import pytest

from empire_os.search_intelligence.quora_intelligence import (
    QuoraEvidenceError, permitted_discovery_queries, read_topic_queue,
    review_quora_research, review_quora_serp_snapshot,
)
from empire_os.search_intelligence.serp import SearchFabricSerpAdapter
from scripts.review_search_quora_one_shot_20261021 import review_one_shot

NOW = datetime(2026, 10, 21, 21, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("seed,prefix", [
    ("QROOF001", "site:quora.com roof replacement"),
    ("QHVAC001", "site:quora.com heat pump installation"),
    ("QSOLA001", "site:quora.com solar panel installation"),
    ("QDENT001", "site:quora.com dental consultation"),
    ("QLEGL001", "site:quora.com find a lawyer"),
    ("QBUSI001", "site:quora.com lead generation"),
])
def test_broad_query_available_for_each_existing_sector(seed, prefix):
    row = next(x for x in read_topic_queue() if x["item_id"] == seed)
    precise, broad = permitted_discovery_queries(row)
    assert precise.startswith('site:quora.com "')
    assert broad == prefix
    assert all(q.startswith("site:quora.com ") for q in (precise, broad))


def test_plan_defaults_to_precise_and_broad_plan_never_searches():
    calls = []
    def reject(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("planning must not call Search Fabric")
    p = review_one_shot("QHVAC001", live=False, search_fn=reject)
    b = review_one_shot("QHVAC001", live=False, query_mode="broad", search_fn=reject)
    assert p["discovery_mode"] == "precise" and '"' in p["source_query"]
    assert b["source_query"] == "site:quora.com heat pump installation"
    assert b["discovery_mode"] == "broad"
    assert b["search_request_performed"] is False
    assert b["execution_authority"] == "NONE"
    assert calls == []


def test_broad_query_can_produce_a_candidate_but_not_a_verified_question():
    calls = []
    def stub(query, *, num, engine, use_cache):
        calls.append((query, num, engine, use_cache))
        return {
            "organic": [{
                "title": "When should homeowners replace an old roof?",
                "link": "https://www.quora.com/When-should-homeowners-replace-their-roof",
                "snippet": "An independently unverified web result",
                "position": 1,
            }],
            "searchParameters": {"engine": "bing_html", "cache": False},
        }
    packet = review_one_shot(
        "QROOF001", live=True, query_mode="broad",
        search_fn=stub, clock=lambda: NOW,
    )
    assert calls == [("site:quora.com roof replacement", 3, "bing_html", False)]
    assert packet["source_status"] == "CANDIDATE_RESULTS_OBSERVED"
    assert len(packet["question_candidates"]) == 1
    assert packet["question_candidates"][0]["quora_origin_page_verified"] is False
    assert packet["verified_question_count"] == 0
    assert packet["published_answers_verified"] == 0
    assert packet["posting_authorized"] is False


def test_unrecognised_mode_and_seed_fail_without_network():
    def reject(*_args, **_kwargs):
        raise AssertionError("network should not run")
    with pytest.raises(QuoraEvidenceError):
        review_one_shot("QROOF001", live=True, query_mode="other", search_fn=reject)
    with pytest.raises(QuoraEvidenceError):
        review_one_shot("QINVALID", live=True, query_mode="broad", search_fn=reject)


def test_changed_query_outside_bounded_allowlist_fails_source_review():
    from empire_os.search_intelligence.quora_intelligence import (
        QuoraEvidenceError, review_quora_research,
    )
    row = next(x for x in read_topic_queue() if x["item_id"] == "QROOF001")
    obs = {
        "seed_id": row["item_id"],
        "question_url": "https://www.quora.com/When-should-homeowners-replace-their-roof",
        "question_title": "When should homeowners replace their roof?",
        "source_ref": "search-fabric:0123456789abcdefabcdef0123456789",
        "source_query": "site:quora.com everything",
        "observed_at": NOW.isoformat(),
        "provider": "search_fabric",
    }
    with pytest.raises(QuoraEvidenceError, match="SOURCE_QUERY_MISMATCH"):
        review_quora_research([obs], now=NOW)
    obs["source_query"] = "site:quora.com roof replacement"
    assert review_quora_research([obs], now=NOW)["source_candidates_count"] == 1
