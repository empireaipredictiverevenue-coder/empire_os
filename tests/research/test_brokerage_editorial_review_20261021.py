"""Brokerage US + UK bounded research and editorial authority integration."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from empire_os.research.brokerage_editorial_review import (
    US_SOURCES, inspect_known_source, review_brokerage_editorial,
)

NOW = datetime(2026, 10, 21, 11, tzinfo=timezone.utc)


def inspected(url: str):
    assert url in {u for _, u in US_SOURCES}
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(url.encode()).hexdigest(),
        "document_headings": ["Implants", "Dental services"],
        "visible_excerpt": "Public dental service descriptions",
    }


def test_us_uses_original_sources_and_requires_actual_signed_editorial_decision(tmp_path):
    sample = tmp_path / "original.md"
    sample.write_text("Original 20 October 2026 publicly observed US dental sample")
    r = review_brokerage_editorial(
        "US", inspect_fn=inspected, original_sample=sample, observed_at=NOW
    )
    assert r["market_country"] == "US"
    assert r["source_count"] == 3
    assert r["original_pages_inspected"] == 3
    assert r["status"] == "ORIGINAL_SOURCE_PAGES_INSPECTED_EDITORIAL_PENDING"
    assert r["original_sample_sha256"] == sha256(sample.read_bytes()).hexdigest()
    assert len({s["url"] for s in r["source_observations"]}) == 3
    assert all(s["claim_accuracy_verified"] is False
               and s["original_page_inspected"] is True for s in r["source_observations"])
    assert r["research_steps"][-1]["status"] == "blocked"
    assert r["search_engine_live"] is False
    for field in ("factual_claims_independently_verified", "source_reuse_rights_cleared",
                  "editorial_owner_signed_off", "customer_copy_approved",
                  "sales_owner_approval", "buyer_interest_verified", "outbound_authorized",
                  "payments_authorized", "database_writes",
                  "agent_shell_or_browser_execution", "model_inference_performed"):
        assert r[field] is False, field


def test_uk_has_its_own_independently_curated_primary_sources():
    r = review_brokerage_editorial("GB", inspect_fn=lambda url: {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(url.encode()).hexdigest(),
        "document_headings": ["Observed original UK source"],
    }, observed_at=NOW)
    assert r["source_count"] == r["original_pages_inspected"] == 3
    assert r["status"] == "ORIGINAL_SOURCE_PAGES_INSPECTED_EDITORIAL_PENDING"
    assert all(url not in {s["url"] for s in r["source_observations"]}
               for _, url in US_SOURCES)
    assert any(s["source_lane"] == "first_party_official"
               for s in r["source_observations"])
    assert r["editorial_owner_signed_off"] is False
    assert r["outbound_authorized"] is False


def test_partial_source_failure_cannot_clear_editorial():
    broken_url = US_SOURCES[0][1]
    def unavailable(url):
        if url == broken_url:
            return {"status": "ORIGINAL_PUBLIC_SOURCE_FETCH_HELD"}
        return inspected(url)
    r = review_brokerage_editorial("US", inspect_fn=unavailable, observed_at=NOW)
    assert r["original_pages_inspected"] == 2
    assert r["status"] == "SOURCE_DISCOVERY_AND_EDITORIAL_PENDING"
    assert r["editorial_owner_signed_off"] is False


def test_disallows_arbitrary_url_fetch(monkeypatch):
    import urllib.request
    def unexpected(*a, **kw):
        raise AssertionError("must not fetch arbitrary URL")
    monkeypatch.setattr(urllib.request, "urlopen", unexpected)
    for url in ("http://localhost:8769/health", "http://169.254.169.254/latest",
                "https://example.com/data", "https://127.0.0.1/"):
        with pytest.raises(ValueError, match="SOURCE_NOT_IN_REVIEWED"):
            inspect_known_source(url)


def test_bad_country_clock_and_untrusted_source_custody(tmp_path):
    with pytest.raises(ValueError, match="SUPPORTED"):
        review_brokerage_editorial("CA", inspect_fn=inspected)
    with pytest.raises(ValueError, match="CLOCK"):
        review_brokerage_editorial("US", observed_at=datetime(2026, 10, 21))
    p = tmp_path / "source.md"
    p.symlink_to(tmp_path / "nonexistent")
    with pytest.raises(ValueError, match="CUSTODY"):
        review_brokerage_editorial("US", inspect_fn=inspected, original_sample=p)



def test_live_qwen_observed_unsupported_poor_ranking_inference_is_held():
    from empire_os.research.brokerage_editorial_review import triage_local_model_draft
    # Exact substance observed from real local inference on original page
    # headings, without any SERP or patient booking data.
    output = (
        "The three webpages returned HTTP 200 and contained implant-service "
        "headings, but no SERP positions or patient conversion data, which "
        "suggests that the website may not be performing well in search "
        "engine rankings or attracting patients."
    )
    r = triage_local_model_draft(output)
    assert r["status"] == "HELD_UNSUPPORTED_SEO_OR_PATIENT_OUTCOME_INFERENCE"
    assert r["unsupported_outcome_inference_detected"] is True
    assert r["lexical_triage_is_fact_verification"] is False
    assert r["editorial_claims_verified"] is False
    assert r["customer_copy_authorized"] is False
    assert r["outbound_authorized"] is False


def test_even_non_triggering_model_output_cannot_self_approve():
    from empire_os.research.brokerage_editorial_review import triage_local_model_draft
    r = triage_local_model_draft("The publisher website includes a dental implant heading.")
    assert r["status"] == "HELD_MODEL_SUGGESTIONS_REQUIRE_ORIGINAL_CLAIM_VERIFICATION"
    assert r["editorial_claims_verified"] is False
    assert r["independent_research_owner_review_required"] is True
    assert triage_local_model_draft("")["customer_copy_authorized"] is False
