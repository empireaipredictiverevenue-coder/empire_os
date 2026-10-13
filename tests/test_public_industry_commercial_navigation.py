"""Industry-to-commerce paths: verified offer routing, no invented checkout."""
from pathlib import Path
from html.parser import HTMLParser

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


def test_isolated_static_build_links_if_available():
    out = ROOT / "apps/empire-public-site/out/industries"
    if not out.is_dir():
        return
    for slug in INDUSTRIES:
        path = out / f"{slug}.html"
        if not path.is_file():
            continue
        parser = _Anchors()
        parser.feed(path.read_text(encoding="utf-8"))
        assert "/buy" in parser.hrefs
        assert "/commercial" in parser.hrefs
        assert all("mailto:founder@empire-ai.co.uk" not in x for x in parser.hrefs)
