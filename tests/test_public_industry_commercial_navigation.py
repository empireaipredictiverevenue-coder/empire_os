"""Industry-to-commerce paths: verified offer routing, no invented checkout."""
from pathlib import Path
from html.parser import HTMLParser
import os

import pytest

from empire_os import public_gateway


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "apps/empire-public-site/src/components/IndustryIntelligencePage.tsx"
SITEMAP = ROOT / "apps/empire-public-site/src/app/industries/page.tsx"
INDUSTRIES = (
    "roofing", "hvac", "solar", "property", "private-equity", "legal-mass-tort"
)


def test_all_industry_pages_share_one_safe_commercial_component():
    source = COMPONENT.read_text(encoding="utf-8")
    assert 'href="/commercial"' in source
    assert source.count('href="/commercial"') == 2
    assert 'href="/buy"' in source
    assert source.count('href="/buy"') == 1
    assert 'mailto:founder@empire-ai.co.uk' not in source
    assert "Request a nonbinding proposal" in source
    assert "Discuss a scoped proposal" in source
    assert "View listed intelligence products" in source
    assert "not a claim that" in source
    assert "scope and pricing" in source
    assert "Buy now" not in source
    assert "guaranteed revenue" not in source.lower()
    # No frontend direct checkout/payment or remote partner/lead destinations.
    for forbidden in (
        "https://click.myjobquote", "tel:", "/v1/checkout/orders",
        "wallet", "transferFrom(", "fetch(", "window.location",
    ):
        assert forbidden not in source


def test_converting_paths_are_existing_first_party_pages_only():
    assert public_gateway._site_html_path("buy") is not None
    assert public_gateway._site_html_path("commercial") is not None
    assert public_gateway._site_html_path("uk/roofing") is None
    listing = SITEMAP.read_text(encoding="utf-8")
    assert 'href={`/industries/${page.slug}`}' in listing


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def test_explicit_isolated_static_build_links():
    # The production export is intentionally not rebuilt by a source-only
    # integration. Audit a named preview export, never the live old HTML.
    preview_root = os.environ.get("EMPIRE_INDUSTRY_PREVIEW_EXPORT_ROOT")
    if not preview_root:
        pytest.skip("No isolated preview export selected; production HTML stays unchanged")
    out = Path(preview_root).resolve() / "industries"
    assert out.is_dir(), "Selected preview export is missing its industries directory"
    for slug in INDUSTRIES:
        path = out / f"{slug}.html"
        assert path.is_file(), f"Preview missing {slug} industry HTML"
        parser = _Anchors()
        parser.feed(path.read_text(encoding="utf-8"))
        assert "/buy" in parser.hrefs
        assert "/commercial" in parser.hrefs
        assert all("mailto:founder@empire-ai.co.uk" not in x for x in parser.hrefs)
