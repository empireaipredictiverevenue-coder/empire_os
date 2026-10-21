"""Test the real operator entrypoint with no network or provider side effects."""
from hashlib import sha256

from scripts.run_brokerage_deep_research_20261021 import run, render_markdown


def fake_inspection(url):
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(url.encode()).hexdigest(),
        "document_headings": ["Observed original service or official-source page"],
        "visible_excerpt": "For review only; no claims independently approved.",
    }


def test_both_market_cli_dispatches_one_shared_research_bot():
    r = run(country="both", inspect_fn=fake_inspection)
    assert r["scope"] == ["US", "GB"]
    assert r["status"] == "ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING"
    assert [x["original_pages_inspected"] for x in r["market_reports"]] == [3, 3]
    assert all(x["editorial_approval"] is False for x in r["market_reports"])
    assert r["database_writes"] is False
    text = render_markdown(r)
    assert "## US" in text and "## GB" in text
    assert "Source" in text or "source" in text
    assert "Do not distribute" in text


def test_provider_degraded_does_not_hide_primary_source_observations():
    def broken(query, **kwargs):
        return {"error": "All engines failed",
                "searchParameters": {"engine": "none", "search_state": "PROVIDER_DEGRADED"},
                "organic": []}
    r = run(country="both", probe_public_search=True,
            search_fn=broken, inspect_fn=fake_inspection)
    assert r["status"] == "ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING"
    for x in r["market_reports"]:
        assert x["current_search_discovery"]["status"] == \
            "SEARCH_PROVIDER_DEGRADED_OR_NO_FRESH_EVIDENCE"
        assert x["original_pages_inspected"] == 3
        assert x["verified_buyer"] is False


def test_no_inferred_approval_even_if_source_inspection_says_approved():
    def fake(url):
        return {**fake_inspection(url), "customer_send_authorized": True,
                "editorial_owner_signed_off": True}
    r = run(country="US", inspect_fn=fake)
    assert not r["editorial_signoff_verified"]
    assert r["market_reports"][0]["editorial_approval"] is False
    assert not r["outbound_sent"]
