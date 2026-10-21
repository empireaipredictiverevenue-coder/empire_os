"""Regression harness: two-market original evidence, search health and sales gates."""
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from empire_os.research.brokerage_editorial_review import (
    COUNTRY_SOURCES, review_brokerage_editorial
)
from empire_os.research.brokerage_decision_brief import (
    discover_held_candidates, build_brokerage_decision_brief
)

NOW = datetime(2026, 10, 21, 11, 50, tzinfo=timezone.utc)


def offline_original(url):
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(("original|" + url).encode()).hexdigest(),
        "document_headings": ["Original clinical/market publisher page", "Treatment or market study"],
        "visible_excerpt": "Original first-party copy to be checked independently.",
    }


@pytest.mark.parametrize("country", ["US", "GB"])
def test_full_two_country_brief_retains_original_evidence_without_approval(country):
    source = review_brokerage_editorial(country, inspect_fn=offline_original, observed_at=NOW)
    output = build_brokerage_decision_brief(source)
    assert output["status"] == "SOURCE_EVIDENCE_READY_FOR_EDITORIAL_REVIEW"
    assert output["original_pages_inspected"] == 3
    assert output["curated_original_source_count"] == 3
    assert all(r["inspected"] and r["licensing_reuse_cleared"] is False
               for r in output["evidence_ledger"])
    assert {x["original_url"] for x in output["evidence_ledger"]} == {
        url for _, url in COUNTRY_SOURCES[country]
    }
    assert len(output["evidence_fingerprint_sha256"]) == 64
    for name in ("verified_buyer", "editorial_approval", "sources_reuse_licensed",
                 "price_quote_authorized", "outbound_authorized",
                 "client_delivery_authorized", "payment_authorized", "database_writes"):
        assert output[name] is False, name
    assert output["buyer_first_sequence"][-1] == "proposal_only_after_interest"
    assert not any("£395" in q or "buy now" in q.lower() for q in output["editorial_questions"])


def test_uk_official_and_clinic_sources_not_confused():
    report = review_brokerage_editorial("GB", inspect_fn=offline_original, observed_at=NOW)
    brief = build_brokerage_decision_brief(report)
    assert len([x for x in brief["evidence_ledger"]
                if x["source_type"] == "official_public_market_context"]) == 1
    assert len([x for x in brief["evidence_ledger"]
                if x["source_type"] == "practice_first_party_service_page"]) == 2
    assert "CMA" in " ".join(brief["editorial_questions"])


def test_partial_source_does_not_become_complete_market_report():
    def partial(url):
        if "sixwaysdental" in url:
            return {"status": "SOURCE_UNAVAILABLE"}
        return offline_original(url)
    report = review_brokerage_editorial("GB", inspect_fn=partial, observed_at=NOW)
    brief = build_brokerage_decision_brief(report)
    assert brief["status"] == "HELD_MISSING_ORIGINAL_SOURCE_EVIDENCE"
    assert brief["original_pages_inspected"] == 2
    assert brief["editorial_approval"] is False


@pytest.mark.parametrize("country", ["US", "GB"])
def test_unavailable_discovery_not_misclassified_as_no_market(country):
    no_search = discover_held_candidates(country, None)
    assert no_search["status"] == "SEARCH_NOT_RUN_NO_VERIFIED_PROVIDER"
    degraded = discover_held_candidates(
        country,
        lambda q, **kwargs: {
            "error": "All engines failed",
            "searchParameters": {"engine": "none", "search_state": "PROVIDER_DEGRADED"},
            "organic": [],
        },
    )
    assert degraded["status"] == "SEARCH_PROVIDER_DEGRADED_OR_NO_FRESH_EVIDENCE"
    assert degraded["queries_attempted"] == 2
    assert degraded["buyer_intent_verified"] is False
    assert degraded["source_admissions"] == 0
    assert degraded["candidate_urls"] == []


def test_stale_and_synthetic_search_fail_closed():
    def fake(query, **kwargs):
        return {
            "searchParameters": {"engine": "bing_html", "cache": True, "stale": True},
            "organic": [{"link": "https://legitimate-agency.co.uk/about"}]
        }
    result = discover_held_candidates("GB", fake)
    assert not result["any_verified_fresh_results"]
    assert not result["candidate_urls"]


def test_fresh_discovery_candidates_are_not_approved_sources():
    seen = []
    def fake(query, **kwargs):
        seen.append((query, kwargs))
        return {
            "searchParameters": {"engine": "bing_html", "cache": False, "stale": False,
                                 "search_state": "RESULTS", "quality_gate": "lexical_v2"},
            "organic": [
                {"title": "Birmingham dental implant original practice", "link": "https://agency.example-corp.co.uk/dental-implants"},
                {"title": "Malicious", "link": "http://127.0.0.1:8769/health"},
                {"title": "Reserved", "link": "https://example.com/pretend"},
            ],
        }
    found = discover_held_candidates("GB", fake)
    assert found["status"] == "FRESH_DISCOVERY_CANDIDATES_NOT_ADMITTED"
    assert len(found["candidate_urls"]) == 1
    assert len(seen) == 2
    assert all(params["engine"] is None and params["use_cache"] is False
               and params["num"] == 5 for _, params in seen)
    report = review_brokerage_editorial("GB", inspect_fn=offline_original, observed_at=NOW)
    combined = build_brokerage_decision_brief(report, search_diagnostic=found)
    assert combined["current_search_discovery"]["source_admissions"] == 0
    assert all("example-corp" not in x["original_url"] for x in combined["evidence_ledger"])
    assert combined["verified_buyer"] is False


def test_untrusted_source_or_search_attempts_cannot_elevate_commercial_gates():
    report = review_brokerage_editorial("US", inspect_fn=offline_original, observed_at=NOW)
    bad = dict(report)
    bad["source_observations"] = [dict(x) for x in report["source_observations"]]
    bad["source_observations"][0]["url"] = "https://other-jurisdiction.example.com"
    with pytest.raises(ValueError, match="CROSS_MARKET"):
        build_brokerage_decision_brief(bad)
    with pytest.raises(ValueError, match="SEARCH_RESULTS_CANNOT_GRANT"):
        build_brokerage_decision_brief(
            report,
            search_diagnostic={"source_admissions": 1, "buyer_intent_verified": False},
        )


def test_real_provider_quality_flag_is_not_enough_without_niche_relevance():
    def real_shaped_generic(query, **kwargs):
        return {
            "searchParameters": {"engine": "bing_rss", "cache": False,
                                 "search_state": "RESULTS", "quality_gate": "lexical_v2"},
            "organic": [{"title": "Chicago city homepage",
                         "link": "https://www.chicago.gov/city/en.html"},
                        {"title": "Visit Birmingham",
                         "link": "https://visitbirmingham.com/"}],
        }
    result = discover_held_candidates("US", real_shaped_generic, niche="dental")
    assert result["status"] == "SEARCH_PROVIDER_DEGRADED_OR_NO_FRESH_EVIDENCE"
    assert result["candidate_urls"] == []
    assert result["source_admissions"] == 0


def test_search_fabric_result_cannot_admit_cross_niche_candidates():
    def real_shaped_dental(query, **kwargs):
        return {
            "searchParameters": {"engine": "bing_html", "cache": False,
                                 "search_state": "RESULTS", "quality_gate": "lexical_v2"},
            "organic": [{"title": "Birmingham dental implant practice",
                         "link": "https://dental.example-business.co.uk/implants"}],
        }
    result = discover_held_candidates("GB", real_shaped_dental, niche="roofing")
    assert not result["any_verified_fresh_results"]
    assert result["source_admissions"] == 0
