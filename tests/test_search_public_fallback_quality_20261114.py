"""Original Search Fabric provider-quality arbitration regression tests.

Mock ONLY upstream HTTP, keeping the original Bing parser protocol and the
actual original _quality_filter unchanged. No paid source, external egress,
DB write, module clone, or unreviewed gateway change.
"""
from urllib.parse import urlparse

import importlib
import pytest

from empire_os.search_fabric import public_fallback as pf
search = importlib.import_module("empire_os.search_fabric.search")


QUERY = "UK companies buying roofing leads"


def _row(title, url, engine="bing_html", *, snippet=""):
    return {
        "title": title,
        "link": url,
        "snippet": snippet,
        "position": 1,
        "engine": engine,
    }


BING_GENERIC = _row(
    "Wikipedia, the free encyclopedia",
    "https://en.wikipedia.org/wiki/Main_Page",
)
BING_RELEVANT = _row(
    "UK Roofing Leads — Connect With Roofing Contractors",
    "https://example.org/roofing-leads",
)
DDG_RELEVANT = _row(
    "Buy UK roofing leads — Roofing Contractor Enquiries",
    "https://roofers.example.org/roofing-leads",
    "duckduckgo_html",
)
DDG_AD = _row(
    "UK Roofing Leads — Sponsored Ad",
    "https://duckduckgo.com/y.js?ad_domain=ads.example",
    "duckduckgo_html",
)
BRAVE_RELEVANT = _row(
    "UK roofing lead buyers and contractors — roofing enquiries",
    "https://roofing.example.org/buy-leads",
    "brave_web",
)
GOOGLE_RELEVANT = _row(
    "Buy roofing leads in the UK — roofing contractors",
    "https://roofing.example.co.uk/buy-leads",
    "google_html",
)


def _fetch_marker(url, *, timeout, events):
    host = urlparse(url).hostname
    events.append(host)
    return {
        "www.bing.com": "<div id='realbing'>BING</div>",
        "html.duckduckgo.com": "<div>DDG</div>",
        "search.brave.com": "<div data-type='web'>BRAVE</div>",
        "www.google.com": "<div>GOOGLE</div>",
    }[host]


def _stub(monkeypatch, *, bing, brave, google, duckduckgo=()):
    events = []
    monkeypatch.setattr(
        pf, "_fetch", lambda url, *, timeout:
        _fetch_marker(url, timeout=timeout, events=events),
    )
    monkeypatch.setattr(search, "_parse_bing_html", lambda html: list(bing))
    monkeypatch.setattr(
        search, "_parse_duckduckgo_html", lambda html: list(duckduckgo),
    )
    monkeypatch.setattr(
        pf, "parse_public_search_html",
        lambda page, *, provider, limit:
        list(brave if provider == "brave_web" else google),
    )
    return events


def test_unrelated_bing_does_not_prevent_relevant_brave_fallback(monkeypatch):
    events = _stub(
        monkeypatch, bing=[BING_GENERIC], brave=[BRAVE_RELEVANT], google=[],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert result.provider_available is True
    assert len(result) == 1
    assert result[0]["title"] == BRAVE_RELEVANT["title"]
    assert result[0]["engine"] == "brave_web"
    assert result[0]["relevance_score"] >= 0.34
    assert events == ["www.bing.com", "html.duckduckgo.com", "search.brave.com"]


def test_healthy_relevant_bing_avoids_further_egress(monkeypatch):
    events = _stub(
        monkeypatch, bing=[BING_RELEVANT], brave=[BRAVE_RELEVANT],
        google=[GOOGLE_RELEVANT],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert result.provider_available is True
    assert len(result) == 1
    assert result[0]["engine"] == "bing_html"
    assert events == ["www.bing.com"]


def test_irrelevant_all_sources_fail_closed_instead_of_false_green(monkeypatch):
    events = _stub(
        monkeypatch, bing=[BING_GENERIC],
        brave=[_row("Wikipedia", "https://en.wikipedia.org", "brave_web")],
        google=[_row("Wikipedia free encyclopedia", "https://www.wikipedia.org",
                     "google_html")],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert list(result) == []
    assert result.provider_available is False
    assert events == ["www.bing.com", "html.duckduckgo.com", "search.brave.com", "www.google.com"]


def test_google_is_tried_if_bing_and_brave_irrelevant(monkeypatch):
    events = _stub(
        monkeypatch, bing=[BING_GENERIC], brave=[],
        google=[GOOGLE_RELEVANT],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert result.provider_available is True
    assert result[0]["engine"] == "google_html"
    assert events == ["www.bing.com", "html.duckduckgo.com", "search.brave.com", "www.google.com"]


def test_explicit_bing_no_results_remains_healthy_empty(monkeypatch):
    events = []
    def fetch(url, *, timeout):
        host = urlparse(url).hostname
        events.append(host)
        return '<div id="b_results"><li class="b_no">No results</li></div>' if host == "www.bing.com" else ""
    monkeypatch.setattr(pf, "_fetch", fetch)
    monkeypatch.setattr(search, "_parse_bing_html", lambda html: [])
    result = pf.search_public_web(QUERY, num=2)
    assert result.provider_available is True
    assert result == []
    assert events == ["www.bing.com", "html.duckduckgo.com", "search.brave.com", "www.google.com"]


def test_unrelated_bing_with_brave_unavailable_goes_to_google(monkeypatch):
    events = []
    def fetch(url, *, timeout):
        host = urlparse(url).hostname
        events.append(host)
        if host == "search.brave.com":
            raise TimeoutError("unavailable")
        return "BING" if host == "www.bing.com" else "GOOGLE"
    monkeypatch.setattr(pf, "_fetch", fetch)
    monkeypatch.setattr(search, "_parse_bing_html", lambda html: [BING_GENERIC])
    monkeypatch.setattr(
        pf, "parse_public_search_html",
        lambda page, *, provider, limit: [GOOGLE_RELEVANT],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert len(result) == 1 and result[0]["engine"] == "google_html"
    assert events == ["www.bing.com", "html.duckduckgo.com", "search.brave.com", "www.google.com"]


def test_unrelated_bing_does_not_expose_wikipedia_as_buyer(monkeypatch):
    _stub(monkeypatch, bing=[BING_GENERIC], brave=[], google=[])
    result = pf.search_public_web(QUERY, num=2)
    assert result.provider_available is False
    assert all("Wikipedia" not in row.get("title", "") for row in result)



def test_repaired_first_party_collector_reaches_existing_duckduckgo(monkeypatch):
    events = _stub(
        monkeypatch, bing=[BING_GENERIC],
        duckduckgo=[DDG_RELEVANT], brave=[BRAVE_RELEVANT], google=[],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert result.provider_available is True
    assert len(result) == 1
    assert result[0]["title"] == DDG_RELEVANT["title"]
    assert result[0]["engine"] == "duckduckgo_html"
    assert result[0]["relevance_score"] >= 0.34
    assert events == ["www.bing.com", "html.duckduckgo.com"]


def test_duckduckgo_ad_redirect_is_never_relabelled_or_sold(monkeypatch):
    events = _stub(
        monkeypatch, bing=[BING_GENERIC],
        duckduckgo=[DDG_AD, DDG_RELEVANT], brave=[], google=[],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert result.provider_available is True
    assert len(result) == 1
    assert result[0]["link"] == DDG_RELEVANT["link"]
    assert all("duckduckgo.com" not in row["link"] for row in result)
    assert events == ["www.bing.com", "html.duckduckgo.com"]


def test_duckduckgo_only_irrelevant_results_continue_to_brave(monkeypatch):
    events = _stub(
        monkeypatch, bing=[BING_GENERIC],
        duckduckgo=[_row(
            "Wikipedia, the free encyclopedia",
            "https://www.wikipedia.org/",
            "duckduckgo_html",
        )],
        brave=[BRAVE_RELEVANT], google=[],
    )
    result = pf.search_public_web(QUERY, num=2)
    assert len(result) == 1 and result[0]["engine"] == "brave_web"
    assert events == ["www.bing.com", "html.duckduckgo.com", "search.brave.com"]
