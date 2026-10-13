"""MyJobQuote prospective UK affiliate page: offline, fail-closed contract."""
from __future__ import annotations

from pathlib import Path
import re

from empire_os import public_gateway

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "apps/empire-public-site/src/app/uk/roofing/page.tsx"


def test_uk_editorial_page_exists_but_no_public_gateway_route():
    assert PAGE.is_file()
    assert public_gateway._site_html_path("uk/roofing") is None


def test_uk_page_not_indexed_and_emits_no_customer_conversion():
    source = PAGE.read_text(encoding="utf-8")
    assert 'canonical: "/uk/roofing"' in source
    assert "robots: { index: false, follow: false" in source
    assert "disabled" in source and 'aria-disabled="true"' in source
    assert "Prelaunch" in source
    assert "not enabled" in source
    for forbidden in (
        "https://click.myjobquote", "https://www.myjobquote",
        "tel:", "<form", "<iframe", "<script", "fetch(",
        "XMLHttpRequest", "window.location", "localStorage",
        "sessionStorage", "dataLayer", "gtag(", "fbq(",
    ):
        assert forbidden not in source, forbidden


def test_no_lead_smart_us_buyer_mix_or_referral_without_approval():
    source = PAGE.read_text(encoding="utf-8")
    for forbidden in ("Ringba", "CA8278", "18883579305", "ZIP code",
                      "USA", "New Jersey", "Lead Smart",
                      "/roofing/coverage-check"):
        assert forbidden not in source, forbidden
    values = re.findall(r'\bhref="([^"]+)"', source)
    assert values == ["#roofing-checklist", "#roof-types"]
    for forbidden in ("30%", "£6", "£12", "guaranteed", "approved publisher",
                      "free quote", "available roofers"):
        assert forbidden.lower() not in source.lower(), forbidden


def test_page_distinguishes_advice_from_contract_or_quote_service():
    text = PAGE.read_text(encoding="utf-8")
    assert "not an inspection" in text.lower()
    assert "potential paid affiliate arrangement" in text
    assert "Partner links, quotation submissions and call connections are not enabled" in text
    assert "Future affiliate links would be clearly disclosed" in text
    assert "A better enquiry starts with better information" in text


def test_export_validator_fails_closed_on_missing_or_active_elements(tmp_path):
    from scripts.verify_myjobquote_uk_roofing_export import audit, audit_html_bytes

    assert audit(tmp_path / "missing.html")["result"] == "FAIL_CLOSED"
    harmless = (
        '<html><head><meta name="robots" content="noindex, nofollow">'
        '</head><body><a href="#roofing-checklist">Guide</a>'
        '<a href="#roof-types">Types</a>'
        '<img src="/brand/empire-mark.svg">'
        '<p>Ad · planned partner link (inactive)</p>'
        '<p>Empire AI may earn commission when a qualifying referral meets the agreed terms.</p>'
        '<p>No affiliate link is currently active</p>'
        '<button disabled aria-disabled="true">Quote enquiry unavailable during affiliate review</button>'
        '</body></html>'
    ).encode()
    assert audit_html_bytes(harmless)["result"] == "PASS"
    for added in (
        '<a href="https://click.myjobquote.co.uk">Go</a>',
        '<form action="/leads"></form>',
        '<iframe src="https://example.org"></iframe>',
        '<script src="https://example.org/a.js"></script>',
        '<input name="phone">',
        '<a href="tel:+441234567">Call</a>',
    ):
        assert audit_html_bytes(harmless + added.encode())["result"] == "FAIL_CLOSED"
    assert audit_html_bytes(harmless.replace(b"noindex", b"index"))["result"] == "FAIL_CLOSED"
    assert audit_html_bytes(harmless.replace(b" disabled ", b" "))["result"] == "FAIL_CLOSED"
    assert audit_html_bytes(
        harmless.replace("Ad · planned partner link (inactive)".encode("utf-8"), b"See quotes")
    )["result"] == "FAIL_CLOSED"


def test_rendered_static_export_if_available():
    from scripts.verify_myjobquote_uk_roofing_export import EXPORT, audit
    if EXPORT.exists():
        assert audit(EXPORT)["result"] == "PASS"



def test_planned_affiliate_ad_disclosure_precedes_disabled_quote_action():
    source = PAGE.read_text(encoding="utf-8")
    assert 'role="note"' in source
    assert 'aria-label="Planned affiliate advertisement disclosure"' in source
    assert "Ad · planned partner link (inactive)" in source
    assert "Empire AI may earn" in source
    assert "commission when a qualifying referral" in source
    assert "No affiliate link is currently active" in source
    assert source.index("Ad · planned partner link (inactive)") < source.index(
        "Quote enquiry unavailable during affiliate review"
    )
