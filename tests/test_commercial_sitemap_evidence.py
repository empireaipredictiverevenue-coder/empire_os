"""Commercial page discovery must improve source evidence without fabricating buyer demand."""
from types import SimpleNamespace
import time

import empire_os.search_fabric.site_probe as sp
from empire_os.buyer_claim_provenance import (
    classify_buyer_source_pages, verified_direct_purchase_receipt,
)


def _doc(url, text, *, fmt="html"):
    return SimpleNamespace(
        url=url, canonical_url=url, text=text, format=fmt, title="Buyer",
        description="", structured_data=[], emails=[], phones=[], socials=[],
    )


def test_hidden_buying_page_from_sitemap_is_observed_and_proven(monkeypatch):
    root = "https://acme.test/"
    buying = root + "advertisers/buy-leads/"
    documents = {
        root: _doc(root, '<a href="/about/">About</a><a href="/contact/">Contact</a>'),
        root + "sitemap.xml": _doc(root + "sitemap.xml",
            "<urlset><url><loc>https://other.test/buy-leads/</loc></url>"
            "<url><loc>https://acme.test/leadership/</loc></url>"
            "<url><loc>https://acme.test/advertisers/buy-leads/</loc></url></urlset>", fmt="xml"),
        buying: _doc(buying, "<h1>Our Acquisition Programme</h1><p>We buy leads from qualified publishers.</p>"),
        root + "about/": _doc(root + "about/", "<h1>About Acme</h1>"),
        root + "contact/": _doc(root + "contact/", "Contact Acme"),
    }
    seen = []
    monkeypatch.setattr(sp, "_fetch", lambda _s, url, **_k: (seen.append(url) or documents.get(url)))
    monkeypatch.setattr(sp.time, "sleep", lambda _t: None)
    result = sp.probe_site(
        root, max_pages=5, time_budget_seconds=10, request_timeout=2,
        page_priority="commercial", public_only=True,
    )
    assert result["ok"] is True
    assert len(result["pages_checked"]) <= 5
    assert result["sitemap_commercial_candidates"] == 1
    assert result["sitemap_commercial_pages_fetched"] == 1
    assert buying in [p["url"] for p in result["pages_checked"]]
    assert all("other.test" not in url for url in seen)
    provenance = classify_buyer_source_pages(result["pages_checked"], company_website=root)
    assert provenance["buyer_relationship"] == "direct_inventory_buyer"
    assert verified_direct_purchase_receipt(
        {"buyer_claim_provenance": provenance}, company_website=root,
    )
    assert provenance["outbound_authorized"] is False


def test_sitemap_url_alone_never_establishes_purchasing(monkeypatch):
    root = "https://acme.test/"
    buying = root + "advertisers/buy-leads/"
    pages = {
        root: _doc(root, "<h1>Home</h1>"),
        root + "sitemap.xml": _doc(root + "sitemap.xml",
            f"<urlset><url><loc>{buying}</loc></url></urlset>", fmt="xml"),
        buying: _doc(buying, "<h1>Advertiser information</h1><p>Contact us to learn more.</p>"),
    }
    monkeypatch.setattr(sp, "_fetch", lambda _s, url, **_k: pages.get(url))
    monkeypatch.setattr(sp.time, "sleep", lambda _t: None)
    result = sp.probe_site(root, max_pages=3, request_timeout=1,
                           time_budget_seconds=5, page_priority="commercial", public_only=True)
    assert result["sitemap_commercial_pages_fetched"] == 1
    claim = classify_buyer_source_pages(result["pages_checked"], company_website=root)
    assert not claim["explicit_direct_purchase_observed"]


def test_nested_sitemap_is_bounded_and_off_domain_denied(monkeypatch):
    root = "https://acme.test/"
    seen = []
    pages = {
        root + "sitemap.xml": _doc(root + "sitemap.xml",
            "<sitemapindex><sitemap><loc>https://other.test/page-sitemap.xml</loc></sitemap>"
            "<sitemap><loc>https://acme.test/page-sitemap.xml</loc></sitemap></sitemapindex>", fmt="xml"),
        root + "page-sitemap.xml": _doc(root + "page-sitemap.xml",
            "<urlset><url><loc>https://acme.test/partners/buy-calls/</loc></url>"
            "<url><loc>https://other.test/advertisers/</loc></url></urlset>", fmt="xml"),
    }
    monkeypatch.setattr(sp, "_fetch", lambda _s, url, **_k: (seen.append(url) or pages.get(url)))
    urls = sp._sitemap_people_candidates(
        object(), root, timeout=2, deadline=time.monotonic()+5,
        max_fetches=2, max_urls=3, public_only=True, priority="commercial",
    )
    assert urls == [root + "partners/buy-calls/"]
    assert seen == [root + "sitemap.xml", root + "page-sitemap.xml"]


def test_non_homepage_and_tiny_commercial_probes_do_not_fetch_sitemap(monkeypatch):
    url = "https://acme.test/partners/"
    seen = []
    monkeypatch.setattr(sp, "_fetch", lambda _s, value, **_k: (
        seen.append(value) or (_doc(value, "We buy leads.") if value == url else None)
    ))
    monkeypatch.setattr(sp.time, "sleep", lambda _t: None)
    result = sp.probe_site(url, max_pages=2, request_timeout=1,
                           time_budget_seconds=5, page_priority="commercial", public_only=True)
    assert result["ok"] is True
    assert result["sitemap_commercial_candidates"] == 0
    assert not any("sitemap" in value for value in seen)


def test_existing_explicit_internal_buying_pages_take_precedence(monkeypatch):
    root = "https://acme.test/"
    buy = root + "buy-calls/"
    seen = []
    docs = {
        root: _doc(root, '<a href="/buy-calls/">We buy calls</a>'
                    '<a href="/buy-leads/">We buy leads</a>'),
        buy: _doc(buy, "We buy calls from verified suppliers."),
        root + "buy-leads/": _doc(root+"buy-leads/", "We buy leads."),
    }
    monkeypatch.setattr(sp, "_fetch", lambda _s, value, **_k: (
        seen.append(value) or docs.get(value)
    ))
    monkeypatch.setattr(sp.time, "sleep", lambda _t: None)
    result = sp.probe_site(root, max_pages=3, request_timeout=1,
                           time_budget_seconds=5, page_priority="commercial", public_only=True)
    assert len(result["pages_checked"]) == 3
    assert result["sitemap_commercial_candidates"] == 0
    assert not any("sitemap" in value for value in seen)
