"""Quora joins the existing SEO engine without post, scrape or buyer claims."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import shutil

import pytest
from fastapi.testclient import TestClient

from empire_os.search_intelligence.quora_intelligence import (
    QUEUE, QuoraEvidenceError, canonical_question_url,
    read_topic_queue, review_quora_research,
)
from empire_os.search_intelligence.service import build_search_intelligence_service


NOW = datetime(2026, 10, 21, 17, 55, tzinfo=timezone.utc)


def example(**overrides):
    theme = read_topic_queue()[0]["question_theme"]
    original = {
        "seed_id": "QROOF001",
        "question_url": "https://www.quora.com/How-do-I-know-if-I-need-a-new-roof",
        "question_title": "How do I know whether I need a full roof replacement?",
        "source_ref": "search-fabric:original-verified-labeled-receipt-001",
        "source_query": 'site:quora.com "' + theme + '"',
        "observed_at": NOW.isoformat(),
        "provider": "search_fabric",
    }
    return {**original, **overrides}


def test_existing_8_topics_are_reused_with_no_claimed_quora_posts():
    r = review_quora_research(now=NOW)
    assert r["topic_count"] == 8
    assert r["source_candidates_count"] == 0
    assert r["fresh_source_candidate_count"] == 0
    assert r["verified_quora_questions"] == 0
    assert r["published_answers_verified"] == 0
    assert r["owned_seo_sessions_verified"] == 0
    assert r["third_party_visits_first_party"] is False
    assert r["affiliate_links_authorized"] is False
    assert r["automated_posting_authorized"] is False
    assert r["external_requests_performed"] is False
    assert r["production_writes"] is False
    assert r["execution_authority"] == "NONE"
    assert all(x["editorial_review_required"] for x in r["topics"])
    assert all(x["source_query_plan"].startswith('site:quora.com "') for x in r["topics"])


def test_search_fabric_candidate_is_not_a_verified_question_or_a_buyer():
    r = review_quora_research([example()], now=NOW)
    assert r["source_candidates_count"] == 1
    assert r["fresh_source_candidate_count"] == 1
    item = r["candidate_questions"][0]
    assert item["question_url_candidate"].startswith("https://www.quora.com/")
    assert item["quora_origin_page_verified"] is False
    assert item["author_or_customer_verified"] is False
    assert item["buyer_qualification_verified"] is False
    assert item["posting_authorized"] is False
    assert r["buyer_accepted_calls_verified"] is False
    assert r["realized_revenue_verified"] is False


def test_stale_candidate_does_not_become_fresh():
    r = review_quora_research([example(
        observed_at=(NOW - timedelta(days=9)).isoformat()
    )], now=NOW)
    assert r["fresh_source_candidate_count"] == 0
    assert r["candidate_questions"][0]["source_status"].startswith("STALE_")


@pytest.mark.parametrize("bad_url", [
    "http://www.quora.com/How-do-I-replace-a-roof",
    "https://quora.com.evil.net/How-do-I-replace-a-roof",
    "https://www.quora.com/profile/Spam-Account",
    "https://www.quora.com/topic/Roofing",
    "https://www.quora.com/How-do-I-replace-a-roof?ref=affiliate",
    "https://other.com/How-do-I-replace-a-roof",
    "https://www.quora.com/search?q=roofing",
    "https://user:password@www.quora.com/How-do-I-replace-a-roof",
    "https://www.quora.com:8443/How-do-I-replace-a-roof",
    "javascript:alert(1)",
])
def test_quora_url_cannot_point_elsewhere(bad_url):
    with pytest.raises(QuoraEvidenceError, match="INVALID_QUORA_QUESTION_URL"):
        canonical_question_url(bad_url)


@pytest.mark.parametrize("override", [
    {"provider": "untrusted"},
    {"source_ref": "guess"},
    {"source_query": 'site:quora.com "another topic"'},
    {"seed_id": "QOTHER"},
    {"observed_at": (NOW + timedelta(days=1)).isoformat()},
    {"observed_at": "naive time"},
    {"question_title": ""},
    {"question_url": "https://another.example.org/How-do-I-know"},
])
def test_bad_provenance_is_rejected(override):
    with pytest.raises(QuoraEvidenceError):
        review_quora_research([example(**override)], now=NOW)


def test_duplicate_quora_question_across_seeds_fails_closed():
    with pytest.raises(QuoraEvidenceError, match="DUPLICATE_QUORA_CANDIDATE"):
        review_quora_research([example(), example()], now=NOW)


def test_untrusted_changed_queue_cannot_promote_own_url_or_approval(tmp_path):
    target = tmp_path / "topics.csv"
    shutil.copyfile(QUEUE, target)
    with target.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    rows[0]["answer_status"] = "PUBLISHED"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(QuoraEvidenceError, match="UNAPPROVED_OR_DUPLICATE"):
        read_topic_queue(target)
    target.unlink()
    target.symlink_to(QUEUE)
    with pytest.raises(QuoraEvidenceError, match="QUEUE_UNAVAILABLE"):
        read_topic_queue(target)


def test_service_private_quora_reader_and_preview_are_both_fail_closed():
    client = TestClient(build_search_intelligence_service())
    read = client.get("/v1/search/quora/review")
    assert read.status_code == 200
    assert read.json()["topic_count"] == 8
    assert read.headers["cache-control"] == "no-store"
    assert read.json()["execution_authority"] == "NONE"
    preview = client.post("/v1/search/quora/search-fabric/preview",
                          json={"observations": [example()]})
    assert preview.status_code == 200
    assert preview.json()["verified_quora_questions"] == 0
    assert preview.headers["cache-control"] == "no-store"
    malformed = client.post("/v1/search/quora/search-fabric/preview",
                            json={"observations": [example(question_url="https://evil.com/Q") ]})
    assert malformed.status_code == 422
    assert malformed.json()["detail"] == "invalid_quora_search_evidence"
    extra = client.post("/v1/search/quora/search-fabric/preview",
                        json={"observations": [], "authorize_post": True})
    assert extra.status_code == 422


def _fabric_snapshot(*, engine="brave", cache=False, error=None, rows=None):
    from empire_os.search_intelligence.serp import SearchFabricSerpAdapter
    seed = read_topic_queue()[0]["question_theme"]
    query = 'site:quora.com "' + seed + '"'
    organic = (
        rows if rows is not None else [{
            "title": "How do I know whether I need roof replacement?",
            "link": "https://www.quora.com/How-do-I-know-if-I-need-a-new-roof",
            "snippet": "Homeowner roof advice",
            "position": 1,
        }]
    )
    response = {
        "organic": organic,
        "searchParameters": {"engine": engine, "cache": cache},
        "error": error,
    }
    adapter = SearchFabricSerpAdapter(
        search_fn=lambda *_args, **_kwargs: response,
        clock=lambda: NOW,
    )
    return adapter.snapshot(query)


def test_canonical_search_fabric_snapshot_yields_only_editorial_candidates():
    from empire_os.search_intelligence.quora_intelligence import (
        review_quora_serp_snapshot,
    )
    packet = review_quora_serp_snapshot(
        "QROOF001", _fabric_snapshot(), now=NOW
    )
    assert packet["search_fabric_snapshot_state"] == "CANDIDATE_RESULTS_OBSERVED"
    assert packet["source_candidates_count"] == 1
    assert packet["candidate_questions"][0]["source_ref"].startswith(
        "search-fabric:"
    )
    assert packet["snapshot_provider_reported"] == "brave"
    assert packet["snapshot_google_ranking_verified"] is False
    assert packet["search_fabric_snapshot_candidate_verified"] is False
    assert packet["verified_quora_questions"] == 0
    assert packet["execution_authority"] == "NONE"


@pytest.mark.parametrize("reason", ["cached", "failed", "no_result"])
def test_search_fabric_source_failures_never_promote_quora_discovery(reason):
    from empire_os.search_intelligence.quora_intelligence import (
        review_quora_serp_snapshot,
    )
    snapshot = (
        _fabric_snapshot(cache=True) if reason == "cached"
        else _fabric_snapshot(error="provider refused") if reason == "failed"
        else _fabric_snapshot(rows=[])
    )
    result = review_quora_serp_snapshot("QROOF001", snapshot, now=NOW)
    assert result["source_candidates_count"] == 0
    assert result["search_fabric_snapshot_state"] == "HELD_OR_UNVERIFIED_SOURCE"


def test_provider_result_must_be_a_question_page():
    from empire_os.search_intelligence.quora_intelligence import (
        review_quora_serp_snapshot,
    )
    rows = [
        {"title": "Some roof safety guidance unrelated link",
         "link": "https://example.org/roofing", "position": 1},
        {"title": "Quora roofing answers by unrelated author",
         "link": "https://www.quora.com/profile/Example-Author", "position": 2},
    ]
    result = review_quora_serp_snapshot(
        "QROOF001", _fabric_snapshot(rows=rows), now=NOW
    )
    assert result["source_candidates_count"] == 0
    assert result["search_fabric_snapshot_state"] == (
        "NO_QUORA_QUESTION_RESULTS_IN_RETURNED_SAMPLE"
    )


def test_search_fabric_query_must_match_exact_curated_topic():
    from empire_os.search_intelligence.quora_intelligence import (
        review_quora_serp_snapshot,
    )
    with pytest.raises(QuoraEvidenceError, match="SOURCE_QUERY_MISMATCH"):
        review_quora_serp_snapshot(
            "QROOF002", _fabric_snapshot(), now=NOW
        )
