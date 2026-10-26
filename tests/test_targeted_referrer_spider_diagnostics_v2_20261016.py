"""No-network Spider V2 diagnostics and bounded discovery regression tests."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import pytest

from empire_os.search_intelligence.targeted_referrer_spider import (
    _prioritize_discovery, _sitemap_discovery, crawl_pilot,
    plan_from_review, MAX_HTTP_REQUESTS, MAX_PAGES_PER_HOST, SpiderHeld,
)


@dataclass
class Response:
    status: int
    content_type: str
    body: bytes


class StubFetch:
    def __init__(self, pages=None, robots=None):
        self.calls = []
        self.pages = pages or {}
        self.robots = robots if robots is not None else b"User-agent: *\nAllow: /\nCrawl-delay: 2\n"

    def __call__(self, uri, *, max_bytes):
        self.calls.append(uri)
        if uri.endswith("/robots.txt"):
            return Response(200, "text/plain", self.robots)
        return self.pages.get(uri, Response(404, "text/html", b""))


def queue(source=("publisher.org",), targets=("sunrun.com",)):
    rows = [
        {"source_domain": name,
         "observed_target_domains": list(targets),
         "linked_target_count": len(targets),
         "technical_name_hint": False,
         "editorial_link_verified": False,
         "source_page_url_known": False,
         "authority_score": None}
        for name in source
    ]
    return {
        "schema_version": "empire.cc.graph.referrer_review_queue.v1",
        "source": "commoncrawl_2026_domain_webgraph",
        "mode": "OBSERVE",
        "empiredb_writes": False,
        "verified_live_backlink_count": 0,
        "distinct_historical_source_domains": len(rows),
        "manual_review_queue": rows,
    }


def run(fetch, sources=("publisher.org",), targets=("sunrun.com",)):
    delays = []
    plan = plan_from_review(queue(sources, targets), sources)
    outcome = crawl_pilot(plan, fetch=fetch, wait=delays.append)
    return outcome, delays


def test_zero_html_pages_now_explains_redirect_and_sitemap_404():
    f = StubFetch(pages={
        "https://publisher.org/": Response(301, "text/html", b""),
    })
    result, delays = run(f)
    host = result["host_outcomes"][0]
    assert host["pages"] == 0
    assert host["attempted_pages"] == 1
    assert host["no_pages_reason"] == "redirect_not_followed"
    assert host["reason_counts"]["redirect_not_followed"] == 1
    assert host["reason_counts"]["sitemap_not_found"] == 1
    assert host["sitemap_outcome"] == "sitemap_not_found"
    assert host["http_requests"] == 3
    assert result["http_requests"] == 3
    assert result["diagnostic_version"] == 2
    assert all(uri.startswith("https://publisher.org/") for uri in f.calls)
    assert result["empiredb_writes"] is False


def test_zero_html_pages_403_helps_identify_access_policy():
    f = StubFetch(pages={
        "https://publisher.org/": Response(403, "text/html", b""),
    })
    result, _ = run(f)
    h = result["host_outcomes"][0]
    assert h["pages"] == 0
    assert h["reason_counts"]["access_denied"] == 1
    assert h["no_pages_reason"] == "access_denied"
    assert h["status"] == "bounded_scan_complete"


def test_zero_html_pages_200_json_explained_as_non_html():
    f = StubFetch(pages={
        "https://publisher.org/": Response(200, "application/json", b'{"ok":true}'),
    })
    result, _ = run(f)
    host = result["host_outcomes"][0]
    assert host["reason_counts"]["non_html_content"] == 1
    assert host["no_pages_reason"] == "non_html_content"


def test_robots_disallow_sitemap_and_home_does_not_retry():
    f = StubFetch(robots=b"User-agent: *\nDisallow: /\n")
    result, delays = run(f)
    h = result["host_outcomes"][0]
    assert h["no_pages_reason"] == "robots_denied_page"
    assert h["sitemap_outcome"] == "robots_denied_sitemap"
    assert h["reason_counts"]["robots_denied_page"] == 1
    assert result["http_requests"] == 1
    assert not delays


def test_sitemap_eligible_urls_prioritised_before_generic_paths():
    raw = b"""<urlset><url><loc>https://publisher.org/about</loc></url>
    <url><loc>https://publisher.org/updates</loc></url>
    <url><loc>https://publisher.org/news/sunrun-solar-project</loc></url>
    <url><loc>https://evil.com/offsite</loc></url></urlset>"""
    urls, child, reason = _sitemap_discovery(raw, "publisher.org", ["sunrun.com"])
    assert urls[0] == "https://publisher.org/news/sunrun-solar-project"
    assert urls[-1] in ("https://publisher.org/about", "https://publisher.org/updates")
    assert len(urls) == 3
    assert child is None and reason == "sitemap_pages_selected"


def test_sitemap_index_follows_only_one_same_host_xml_child():
    index = b"""<sitemapindex><sitemap><loc>https://other.com/out.xml</loc></sitemap>
    <sitemap><loc>https://publisher.org/image-sitemap.xml</loc></sitemap>
    <sitemap><loc>https://publisher.org/post-sitemap.xml</loc></sitemap></sitemapindex>"""
    child_content = b"""<urlset><url><loc>https://publisher.org/about</loc></url>
    <url><loc>https://publisher.org/posts/sunrun-review</loc></url></urlset>"""
    pages = {
        "https://publisher.org/sitemap.xml": Response(200, "application/xml", index),
        "https://publisher.org/post-sitemap.xml": Response(200, "application/xml", child_content),
        "https://publisher.org/": Response(200, "text/html", b"<html><body>home</body></html>"),
        "https://publisher.org/posts/sunrun-review": Response(
            200, "text/html", b'<a href="https://sunrun.com/solar" rel="sponsored">Solar</a>'),
        "https://publisher.org/about": Response(200, "text/html", b"<html>about</html>"),
    }
    fetch = StubFetch(pages=pages)
    outcome, waits = run(fetch)
    h = outcome["host_outcomes"][0]
    assert "https://publisher.org/post-sitemap.xml" in fetch.calls
    assert "https://other.com/out.xml" not in fetch.calls
    assert h["sitemap_outcome"] == "nested_sitemap_pages_selected"
    assert h["sitemap_candidates_found"] == 2
    assert h["pages"] == 3
    assert outcome["html_anchor_edges_observed"] == 1
    assert outcome["evidence"][0]["observed_rel"] == ["sponsored"]
    assert outcome["http_requests"] == 6
    assert len(waits) == 5


def test_nested_sitemap_429_stops_host_before_homepage():
    index = b"<sitemapindex><sitemap><loc>https://publisher.org/post-sitemap.xml</loc></sitemap></sitemapindex>"
    f = StubFetch(pages={
        "https://publisher.org/sitemap.xml": Response(200, "application/xml", index),
        "https://publisher.org/post-sitemap.xml": Response(429, "text/plain", b""),
    })
    result, _ = run(f)
    host = result["host_outcomes"][0]
    assert host["status"] == "host_retry_later"
    assert host["no_pages_reason"] == "host_backoff"
    assert host["reason_counts"]["nested_sitemap_host_backoff"] == 1
    assert "https://publisher.org/" not in f.calls
    assert result["http_requests"] == 3


def test_request_budget_never_exceeded_for_two_nested_sitemap_hosts():
    hosts = ("publisher.org", "otherpublisher.org")
    index = b"""<sitemapindex><sitemap><loc>https://REPLACE/post-sitemap.xml</loc></sitemap></sitemapindex>"""
    pages = {}
    for host in hosts:
        pages["https://" + host + "/sitemap.xml"] = Response(
            200, "application/xml", index.replace(b"REPLACE", host.encode()))
        pages["https://" + host + "/post-sitemap.xml"] = Response(
            200, "application/xml",
            ("<urlset>" + "".join(
                f"<url><loc>https://{host}/solar-{i}</loc></url>"
                for i in range(7)) + "</urlset>").encode())
        pages["https://" + host + "/"] = Response(200, "text/html", b"<html>home</html>")
        for i in range(7):
            pages[f"https://{host}/solar-{i}"] = Response(200, "text/html", b"<html>story</html>")
    fetch = StubFetch(pages=pages)
    result, waits = run(fetch, sources=hosts)
    assert result["http_requests"] == MAX_HTTP_REQUESTS == 14
    assert len(fetch.calls) == 14
    assert all(h["attempted_pages"] <= MAX_PAGES_PER_HOST for h in result["host_outcomes"])
    assert result["host_outcomes"][1]["reason_counts"]["global_request_budget_exhausted"] == 1
    assert result["scheduled_crawling"] is False


def test_no_network_follow_of_sitemap_index_cross_host():
    index = b"<sitemapindex><sitemap><loc>http://publisher.org/unsafe.xml</loc></sitemap><sitemap><loc>https://evil.com/child.xml</loc></sitemap></sitemapindex>"
    urls, child, reason = _sitemap_discovery(index, "publisher.org", ["sunrun.com"])
    assert urls == [] and child is None
    assert reason == "sitemap_index_without_eligible_child"


def test_no_redirect_follow_even_if_location_points_inside_host():
    f = StubFetch(pages={
        "https://publisher.org/": Response(302, "text/html", b'<a href="https://sunrun.com">fake</a>'),
    })
    result, _ = run(f)
    assert result["html_anchor_edges_observed"] == 0
    assert result["host_outcomes"][0]["reason_counts"]["redirect_not_followed"] == 1


def test_lexical_priority_does_not_produce_authority_or_conversion_claims():
    pages = ["https://publisher.org/about", "https://publisher.org/blog/sunrun-solar-news"]
    ordered = _prioritize_discovery(pages, ["sunrun.com"])
    assert ordered[0].endswith("sunrun-solar-news")
    f = StubFetch(pages={"https://publisher.org/": Response(200, "text/html", b'<a href="https://sunrun.com/">go</a>')})
    result, _ = run(f)
    assert result["evidence"][0]["search_engine_counts_link"] is None
    assert result["evidence"][0]["editorial_link_value_verified"] is False
    assert result["paid_api_calls"] == 0
