"""Real-source contracts tested with synthetic GSC and page HTML only."""
from copy import deepcopy

import pytest

from empire_os.semantic_keyword_search import SemanticSearchInputError
from empire_os.search_intelligence.first_party_semantic_corpus import (
    PRIORITY_PAGES, page_record, prepare_first_party_semantic_corpus,
)
from scripts.review_live_first_party_semantic import build_live_semantic_review


def html(spec, *, canon=None, robots="index,follow"):
    return (
        "<html><head><title>Solar Installer Coverage &amp; Lead Qualification | Empire AI</title>"
        '<meta name="robots" content="' + robots + '">'
        '<link rel="canonical" href="' + (canon or spec.url) + '">'
        "</head><body><h1>Real installer territory</h1></body></html>"
    )


def gsc(rows):
    return {
        "available": True, "source": "google_search_console",
        "site_url": "sc-domain:empire-ai.co.uk",
        "count": len(rows), "items": rows,
    }


def obs(query, url, *, clicks=0, impressions=3, position=5.0):
    return {"keys": [query, url], "clicks": clicks,
            "impressions": impressions, "position": position}


def test_live_page_html_has_source_receipt_and_actual_canonical():
    spec = PRIORITY_PAGES[1]
    row = page_record(spec, html=html(spec), http_status=200)
    assert row["title"].startswith("Solar Installer")
    assert row["eligible_for_local_topic_review"] is True
    assert row["target_query"] is None
    assert row["content_body_reviewed"] is False
    assert row["evidence_refs"][0].startswith("owned-html-sha256:")


@pytest.mark.parametrize("status,canonical,robots", [
    (404, None, "index"), (200, "https://other.example/path", "index"),
    (200, None, "noindex,nofollow"),
])
def test_page_evidence_gate_fails_closed(status, canonical, robots):
    spec = PRIORITY_PAGES[0]
    result = page_record(spec, html=html(spec, canon=canonical, robots=robots),
                         http_status=status)
    assert result["eligible_for_local_topic_review"] is False
    assert result["reason"] == "page_http_canonical_title_or_noindex_gate"


def test_unmapped_legacy_queries_retained_and_title_seeds_are_unmeasured():
    pages = [page_record(spec, html=html(spec), http_status=200)
             for spec in PRIORITY_PAGES]
    data = prepare_first_party_semantic_corpus(
        gsc([obs("antenna mount", "https://empire-ai.co.uk/aeo/antenna-install/EUG/")]),
        pages, start_date="2026-10-03", end_date="2026-10-15"
    )
    assert len(data["mapped_gsc_keywords"]) == 0
    assert len(data["unmapped_gsc_query_pages"]) == 1
    assert len(data["unmeasured_page_title_seeds"]) == 4
    assert data["returned_query_page_impressions"] == 3
    assert all(seed["observed_demand"] is None for seed in data["unmeasured_page_title_seeds"])
    assert all(seed["source_evidence_kind"] == "PAGE_TITLE_UNMEASURED"
               for seed in data["unmeasured_page_title_seeds"])
    assert data["sitewide_search_demand_inferred"] is False


def test_real_query_maps_only_when_page_is_known_and_verified():
    spec = PRIORITY_PAGES[0]
    pages = [page_record(spec, html=html(spec), http_status=200)]
    data = prepare_first_party_semantic_corpus(
        gsc([obs("commercial roofing contracts", spec.url, clicks=1, impressions=7)]),
        pages, start_date="2026-10-03", end_date="2026-10-15"
    )
    row = data["mapped_gsc_keywords"][0]
    assert row["keyword"] == "commercial roofing contracts"
    assert row["gsc_query_page_clicks"] == 1
    assert row["gsc_query_page_impressions"] == 7
    assert row["buyer_fit"] is None
    assert row["observed_demand"] is None
    assert len(row["evidence_refs"]) == 2


def test_gsc_not_from_correct_property_rejected():
    body = gsc([])
    body["site_url"] = "sc-domain:other-site.example"
    with pytest.raises(SemanticSearchInputError, match="first-party"):
        prepare_first_party_semantic_corpus(
            body, [], start_date="2026-10-03", end_date="2026-10-15",
        )


def test_external_result_urls_and_false_gsc_count_rejected():
    with pytest.raises(SemanticSearchInputError, match="not first-party"):
        prepare_first_party_semantic_corpus(
            gsc([obs("sales", "https://external.example/search")]), [],
            start_date="2026-10-03", end_date="2026-10-15",
        )


def test_duplicate_query_page_result_rejected():
    spec = PRIORITY_PAGES[0]
    body = gsc([obs("roofing quotes", spec.url), obs("roofing quotes", spec.url)])
    with pytest.raises(SemanticSearchInputError, match="duplicate GSC"):
        prepare_first_party_semantic_corpus(
            body, [], start_date="2026-10-03", end_date="2026-10-15",
        )


def test_negative_or_out_of_bounds_metrics_rejected():
    for clicks, impressions in [(-1, 4), (5, 4), (0, -2)]:
        with pytest.raises(SemanticSearchInputError, match="metrics"):
            prepare_first_party_semantic_corpus(
                gsc([obs("roofing", PRIORITY_PAGES[0].url,
                         clicks=clicks, impressions=impressions)]), [],
                start_date="2026-10-03", end_date="2026-10-15",
            )


def test_live_review_orchestrates_only_known_web_routes_and_gsc_endpoints():
    calls = []
    spec = PRIORITY_PAGES[0]

    def json_get(path, *, params=None):
        calls.append(("gsc", path))
        if path == "/search-console/status":
            return {"available": True, "site_url": "sc-domain:empire-ai.co.uk"}
        return gsc([obs("roofing quotes", spec.url, impressions=4)])

    def html_get(url):
        calls.append(("page", url))
        page_spec = next(s for s in PRIORITY_PAGES if s.url == url)
        return 200, html(page_spec)

    report = build_live_semantic_review(
        start_date="2026-10-03", end_date="2026-10-15",
        json_get=json_get, html_get=html_get,
    )
    assert report["gsc_query_page_observations"] == 1
    assert report["gsc_query_page_mapped_to_priority_pages"] == 1
    assert report["gsc_query_page_impressions_returned"] == 4
    assert report["public_priority_pages_with_evidence"] == 4
    assert report["real_search_volume_verified"] is False
    assert report["buyer_intent_verified"] is False
    assert report["revenue_verified"] is False
    assert report["spend_usd"] == 0
    assert len([call for call in calls if call[0] == "page"]) == 4


def test_live_review_rejects_bad_date_and_wrong_source():
    with pytest.raises(SemanticSearchInputError, match="window"):
        build_live_semantic_review(
            start_date="2026-01-01", end_date="2026-10-15"
        )
    with pytest.raises(SemanticSearchInputError, match="adapter"):
        build_live_semantic_review(
            start_date="2026-10-03", end_date="2026-10-15",
            json_get=lambda path, **kw: {"available": False}
        )


def test_search_console_www_and_http_aliases_preserve_original_receipts():
    spec = PRIORITY_PAGES[0]
    real = page_record(spec, html=html(spec), http_status=200)
    rows = [
        obs("commercial roofer chicago",
            "https://www.empire-ai.co.uk/industries/roofing", impressions=3),
        obs("commercial roofer quote",
            "http://empire-ai.co.uk/industries/roofing", impressions=2),
    ]
    corpus = prepare_first_party_semantic_corpus(
        gsc(rows), [real], start_date="2026-10-03", end_date="2026-10-15"
    )
    assert corpus["returned_query_page_rows"] == 2
    assert corpus["returned_query_page_impressions"] == 5
    assert len(corpus["mapped_gsc_keywords"]) == 2
    assert corpus["mapped_gsc_keywords"][0]["product_key"] == "roofing"
    assert corpus["mapped_gsc_keywords"][0]["source_evidence_kind"] == "GSC_QUERY_PAGE"


@pytest.mark.parametrize("url", [
    "https://bad.empire-ai.co.uk/industries/roofing",
    "https://empire-ai.co.uk.evil.com/industries/roofing",
    "https://attacker@empire-ai.co.uk/industries/roofing",
    "https://empire-ai.co.uk:9888/industries/roofing",
    "https://empire-ai.co.uk/industries/roofing?q=1",
    "ftp://empire-ai.co.uk/industries/roofing",
])
def test_noncanonical_or_unsafe_external_page_urls_rejected(url):
    with pytest.raises(SemanticSearchInputError, match="not first-party"):
        prepare_first_party_semantic_corpus(
            gsc([obs("roofing", url)]), [],
            start_date="2026-10-03", end_date="2026-10-15",
        )


def test_live_review_adds_read_only_heuristics_not_verified_buyer_claims():
    from scripts.review_live_first_party_semantic import build_live_semantic_review
    spec = PRIORITY_PAGES[0]

    def fetch(path, *, params=None):
        if path == "/search-console/status":
            return {"available": True, "site_url": "sc-domain:empire-ai.co.uk"}
        return gsc([obs("roofing jobs Chicago", "https://empire-ai.co.uk/")])

    def page_fetch(url):
        page_spec = next(s for s in PRIORITY_PAGES if s.url == url)
        return 200, html(page_spec)

    report = build_live_semantic_review(
        start_date="2026-10-03", end_date="2026-10-15",
        json_get=fetch, html_get=page_fetch,
    )
    assert report["gsc_query_intent_reviews"][0]["intent_hypothesis"] == "EMPLOYMENT_OR_TRAINING_REVIEW"
    assert report["gsc_query_intent_reviews"][0]["actual_buyer_verified"] is False
    assert report["gsc_observed_source_is_buyer_identity"] is False
    assert report["gsc_intent_hypothesis_counts"] == {"EMPLOYMENT_OR_TRAINING_REVIEW": 1}
