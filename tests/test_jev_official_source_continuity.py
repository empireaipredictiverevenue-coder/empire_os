"""Wave 8: search-outage continuity via explicit, official primary pages."""
from hashlib import sha256

import pytest

from empire_os.jev_gtm_research_bridge import (
    run_jev_evidence_gap,
    run_jev_official_source_review,
    inspect_jev_official_source,
)
from empire_os.research.deep_research_intake import ResearchLimits, run_research
from scripts.probe_jev_evidence_research_v2 import _synthetic_decision

ONS = "https://www.ons.gov.uk/businessindustryandtrade/constructionindustry/bulletins/constructionoutputingreatbritain/latest"
GOV = "https://www.gov.uk/government/organisations/department-for-business-and-trade"
DIGEST = sha256(b"mock independently received official source").hexdigest()


def fixture_inspect(url: str):
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "source_url": url,
        "content_sha256": DIGEST,
        "document_headings": ["Official public construction research page"],
        "visible_excerpt": "Fixture only, not actual commercial market evidence.",
        "claim_accuracy_verified": False,
    }


def test_source_only_avoids_outage_search_engine_and_uses_operator_evidence():
    sent = []
    result = run_jev_evidence_gap(
        _synthetic_decision(),
        public_niche="roofing", public_market="Manchester",
        search_fn=lambda *args, **kw: sent.append(True),
        inspect_fn=fixture_inspect,
        official_source_urls=(ONS,),
        source_only=True,
    )
    assert sent == []
    assert result["source_discovery_disabled"] is True
    assert result["searches_executed"] == 0
    assert result["pages_considered"] == 1
    assert result["inspected_source_count"] == 1
    assert result["sources"][0]["observation_type"] == "operator_supplied_primary_source"
    assert result["sources"][0]["content_sha256"] == DIGEST
    assert result["sources"][0]["claim_accuracy_verified"] is False
    assert result["buyer_intent_verified"] is False
    assert result["commercial_promotion_authorized"] is False
    assert result["outbound_sent"] is False


def test_public_search_failed_then_explicit_official_page_inspected():
    queries = []
    result = run_jev_evidence_gap(
        _synthetic_decision(),
        public_niche="roofing", public_market="Manchester",
        search_fn=lambda query, num: queries.append(query) or {
            "organic": [], "error": "CIRCUIT_OPEN",
        },
        inspect_fn=fixture_inspect,
        official_source_urls=(GOV,),
    )
    assert len(queries) == 2
    assert result["inspected_source_count"] == 1
    assert result["sources"][0]["observation_type"] == "operator_supplied_primary_source"
    assert result["status"] == "EVIDENCE_READY_FOR_SYNTHESIS"
    assert result["claims_unverified"] == []
    assert result["commercial_promotion_authorized"] is False


def test_same_source_discovered_and_provided_inspected_once():
    calls = []
    research = run_research(
        "UK roofing procurement",
        search_fn=lambda q, num: {"organic": [{"url": GOV, "title": "Official source"}]},
        inspect_fn=lambda url: calls.append(url) or fixture_inspect(url),
        operator_primary_urls=(GOV,),
        initial_queries=("roofing",),
        limits=ResearchLimits(max_queries=1, max_pages=2),
    )
    assert calls == [GOV]
    assert research["source_count"] == 1
    assert research["budget"]["pages_considered"] == 1


@pytest.mark.parametrize("url", [
    "http://www.gov.uk/organisation",
    "https://evil.com/research",
    "https://attacker.gov.uk.evil.net/",
    "https://localhost/",
    "https://169.254.169.254/",
    "https://user:password@www.gov.uk/foo",
    "https://foo.internal/",
    "https://www.gov.uk:9443/foo",
])
def test_untrusted_user_supplied_sources_refused_before_callbacks(url):
    called = []
    with pytest.raises(ValueError):
        run_jev_evidence_gap(
            _synthetic_decision(),
            public_niche="roofing", public_market="Manchester",
            search_fn=lambda *a, **k: called.append("search"),
            inspect_fn=lambda url: called.append("inspect"),
            official_source_urls=(url,),
            source_only=True,
        )
    assert called == []


def test_source_only_no_sources_rejected_before_callbacks():
    called = []
    with pytest.raises(ValueError):
        run_jev_evidence_gap(
            _synthetic_decision(),
            public_niche="roofing", public_market="Manchester",
            search_fn=lambda *a, **k: called.append(1),
            inspect_fn=lambda url: called.append(2),
            official_source_urls=(),
            source_only=True,
        )
    assert called == []


def test_max_three_official_pages_and_budget_enforced():
    urls = tuple(
        f"https://www.gov.uk/guidance/construction-official-{i}"
        for i in range(4)
    )
    with pytest.raises(ValueError, match="bounded"):
        run_jev_evidence_gap(
            _synthetic_decision(),
            public_niche="roofing", public_market="Manchester",
            search_fn=lambda q, num: {"organic": []},
            inspect_fn=fixture_inspect,
            official_source_urls=urls,
            source_only=True,
        )


def test_official_source_inspector_rejects_non_official_before_imported_fetcher():
    assert inspect_jev_official_source("https://example.org/") == {
        "status": "NON_OFFICIAL_SOURCE_REJECTED"
    }
    assert inspect_jev_official_source("http://www.gov.uk/") == {
        "status": "UNSAFE_URL_REJECTED"
    }


def test_pinned_inspector_receipt_remains_unverified_even_if_page_inspected():
    receipt = run_jev_official_source_review(
        _synthetic_decision(), public_niche="roofing", public_market="Manchester",
        official_source_urls=(ONS,),
        inspector=fixture_inspect,
    )
    assert receipt["source_discovery_disabled"] is True
    assert receipt["operator_primary_sources_attempted"] == 1
    assert receipt["inspected_source_count"] == 1
    assert receipt["sources"][0]["buyer_identity_verified"] is False
    assert receipt["contact_clearance_verified"] is False
    assert receipt["commercial_promotion_authorized"] is False


def test_official_source_timeout_and_failure_abstains():
    result = run_jev_official_source_review(
        _synthetic_decision(), public_niche="roofing", public_market="Manchester",
        official_source_urls=(ONS,),
        inspector=lambda url: {"status": "NETWORK_OR_TLS_UNAVAILABLE"},
    )
    assert result["status"] == "INSUFFICIENT_PRIMARY_EVIDENCE"
    assert result["source_count"] == 1
    assert result["inspected_source_count"] == 0
    assert result["commercial_promotion_authorized"] is False
