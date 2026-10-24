"""No-network validation of the existing Website & Growth GET-only buyer audit."""
import json
from urllib.parse import urlsplit

import pytest

from scripts import review_live_organic_buyer_journey_20261024 as audit


@pytest.fixture
def first_party():
    paths = sorted(audit.PRIORITY | {"/research/sample"})
    requests = []

    def fake(path):
        requests.append(path)
        if path == "/robots.txt":
            return 200, {"Content-Type": "text/plain"}, (
                b"User-agent: *\nAllow: /\nSitemap: https://empire-ai.co.uk/sitemap.xml\n"
            )
        if path == "/sitemap.xml":
            xml = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                + "".join("<url><loc>https://empire-ai.co.uk" + p + "</loc></url>" for p in paths)
                + "</urlset>")
            return 200, {"Content-Type": "application/xml"}, xml.encode()
        if path == "/v1/checkout/commercial/offers":
            return 200, {"Content-Type": "application/json"}, json.dumps(
                {"offers": [{"code": "consultancy"}]}
            ).encode()
        if path == "/v1/checkout/predictive-revenue/products":
            return 200, {"Content-Type": "application/json"}, json.dumps(
                {"products": [{"code": "pr"}]}
            ).encode()
        if path in paths:
            href = '<a href="/commercial">Discuss a commercial offer</a>'
            if path == "/research/sample":
                href = '<a href="/about">About</a>'
            html = ('<html><head><link rel="canonical" href="https://empire-ai.co.uk' +
                path + '"></head><body>' + href + '</body></html>')
            return 200, {"Content-Type": "text/html"}, html.encode()
        raise AssertionError("UNEXPECTED_GET_ROUTE_" + path)

    return fake, requests


def zero_snapshot():
    return {"generated_at": "2026-10-24T13:00:00Z",
        "canonical_sales_source_ops": {
            "status": "CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED",
            "source_count_verified": True,
            "canonical_sales_acquisitions": 0,
            "canonical_predictive_revenue_enquiries": 0,
            "canonical_commercial_enquiries": 0,
        }}


def test_all_discovery_and_buyer_checks_are_get_only(first_party):
    getter, calls = first_party
    r = audit.review(getter, zero_snapshot())
    assert r["sitemap_routes_checked"] == 9
    assert r["routes_with_http_canonical_indexability_issues"] == []
    assert r["direct_buyer_link_review_candidates"] == ["/research/sample"]
    assert r["catalogues"]["/v1/checkout/commercial/offers"]["count"] == 1
    assert r["gtm_snapshot"]["canonical_enquiries"] == 0
    assert r["google_indexing_verified"] is False
    assert r["organic_attribution_verified"] is False
    assert r["publication_authorized"] is False
    assert r["customer_submissions"] == 0
    assert set(calls).issubset({"/robots.txt", "/sitemap.xml"} | audit.PRIORITY
                                  | {"/research/sample"} |
                                  {"/v1/checkout/commercial/offers",
                                   "/v1/checkout/predictive-revenue/products"})


def test_unverified_gtm_null_is_not_false_zero():
    snapshot = zero_snapshot()
    snapshot["canonical_sales_source_ops"]["status"] = "HELD_CANONICAL_ACQUISITION_OWNER_OPS_RECEIPT_REQUIRED"
    snapshot["canonical_sales_source_ops"]["source_count_verified"] = False
    assert audit._gtm_summary(snapshot)["canonical_enquiries"] is None
    snapshot["canonical_sales_source_ops"]["status"] = "CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED"
    snapshot["canonical_sales_source_ops"]["canonical_commercial_enquiries"] = None
    assert audit._gtm_summary(snapshot)["canonical_enquiries"] is None


def test_offsite_sitemap_url_fails_closed(first_party):
    original, _ = first_party
    def bad(path):
        if path == "/sitemap.xml":
            return 200, {"Content-Type": "application/xml"}, (
                b'<urlset><url><loc>https://hostile.invalid/foo</loc></url></urlset>'
            )
        return original(path)
    with pytest.raises(audit.AuditHeld, match="SITEMAP_OFF_HOST_OR_UNSAFE_URL"):
        audit.review(bad, zero_snapshot())


def test_meta_noindex_is_a_problem_not_organic_success(first_party):
    original, _ = first_party
    def bad(path):
        status, headers, body = original(path)
        if path == "/commercial":
            body = body.replace(b"</head>", b'<meta name="robots" content="noindex"></head>')
        return status, headers, body
    r = audit.review(bad, zero_snapshot())
    assert "/commercial" in r["routes_with_http_canonical_indexability_issues"]
    assert r["traffic_growth_verified"] is False


def test_catalogue_empty_is_unhealthy_not_a_sale(first_party):
    original, _ = first_party
    def bad(path):
        if path == "/v1/checkout/commercial/offers":
            return 200, {"Content-Type": "application/json"}, b'{"offers":[]}'
        return original(path)
    r = audit.review(bad, zero_snapshot())
    assert "EXISTING_READONLY_CATALOGUE_API" in r["routes_with_http_canonical_indexability_issues"]
    assert r["gtm_snapshot"]["money_received_verified"] is False


def test_explicit_buyer_url_allowlist_only():
    assert audit._links_to_buyers([
        "/commercial#commercial-enquiry",
        "https://empire-ai.co.uk/predictive-revenue#deployment-request",
        "https://hostile.invalid/commercial",
        "/other", "/commerciality",
        "//hostile.invalid/commercial",
    ]) == {"/commercial", "/predictive-revenue"}
