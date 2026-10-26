import copy
from dataclasses import dataclass
from pathlib import Path
import json
import runpy
import sys
import pytest

from empire_os.search_intelligence.targeted_referrer_spider import (
    SpiderHeld, plan_from_review, crawl_pilot, parse_sitemap, MAX_HTTP_REQUESTS,
)

HOST = "publisher.org"
TARGET = "sunrun.com"


def source_review():
    return {
        "schema_version": "empire.cc.graph.referrer_review_queue.v1",
        "source": "commoncrawl_2026_domain_webgraph",
        "mode": "OBSERVE", "empiredb_writes": False,
        "verified_live_backlink_count": 0,
        "distinct_historical_source_domains": 2,
        "manual_review_queue": [
            {"source_domain": HOST,
             "observed_target_domains": [TARGET, "nationsroof.com"],
             "linked_target_count": 2, "technical_name_hint": False,
             "editorial_link_verified": False,
             "source_page_url_known": False, "authority_score": None},
            {"source_domain": "otherpublisher.org",
             "observed_target_domains": [TARGET],
             "linked_target_count": 1, "technical_name_hint": False,
             "editorial_link_verified": False,
             "source_page_url_known": False, "authority_score": None},
        ],
    }


@dataclass
class Response:
    status: int
    content_type: str
    body: bytes


class FakeFetcher:
    def __init__(self, robots=None, pages=None):
        self.requests = []
        self.robots = robots if robots is not None else b"User-agent: *\nAllow: /\nCrawl-delay: 3\n"
        self.pages = pages or {}

    def __call__(self, uri, *, max_bytes):
        self.requests.append((uri, max_bytes))
        if uri.endswith("/robots.txt"):
            return Response(200, "text/plain", self.robots)
        return self.pages.get(uri, Response(404, "text/html", b""))


def execute(fetch):
    delays = []
    outcome = crawl_pilot(plan_from_review(source_review(), (HOST,)),
                          fetch=fetch, wait=delays.append)
    return outcome, delays


def test_read_only_plan_suggests_no_crawling():
    plan = plan_from_review(source_review())
    assert plan["status"] == "REVIEW_ONLY_SELECT_SOURCES"
    assert plan["network_requests"] == 0
    assert plan["empiredb_writes"] is False
    assert plan["suggested_source_hosts"] == [HOST]


def test_sitemap_and_internal_follow_yield_actual_page_anchor():
    pages = {
        "https://publisher.org/sitemap.xml": Response(200, "application/xml", b'''<urlset><url><loc>https://publisher.org/report</loc></url></urlset>'''),
        "https://publisher.org/": Response(200, "text/html", b'''<a href="/about">About</a>'''),
        "https://publisher.org/report": Response(200, "text/html", b'''<a rel="nofollow sponsored" href="https://sunrun.com/solar">Solar</a>'''),
        "https://publisher.org/about": Response(200, "text/html", b'''<a href="https://nationsroof.com/home">Roofing</a>'''),
    }
    f = FakeFetcher(pages=pages)
    result, delays = execute(f)
    assert result["html_anchor_edges_observed"] == 2
    assert result["html_pages_checked"] == 3
    assert result["http_requests"] == 5
    assert result["empiredb_writes"] is False
    assert result["scheduled_crawling"] is False
    assert len(delays) == 4 and all(x == 3 for x in delays)
    solar = next(x for x in result["evidence"] if x["target_host"] == TARGET)
    assert solar["source_url"] == "https://publisher.org/report"
    assert solar["observed_rel"] == ["nofollow", "sponsored"]
    assert solar["search_engine_counts_link"] is None


def test_robots_disallow_blocks_all_pages_even_from_sitemap():
    f = FakeFetcher(robots=b"User-agent: *\nDisallow: /\n")
    result, delays = execute(f)
    assert result["html_pages_checked"] == 0
    assert result["html_anchor_edges_observed"] == 0
    assert len(f.requests) == 1
    assert delays == []


def test_robots_403_does_not_crawl_anything():
    class Blocked(FakeFetcher):
        def __call__(self, uri, *, max_bytes):
            self.requests.append((uri, max_bytes))
            return Response(403, "text/plain", b"denied")
    f = Blocked()
    result, _ = execute(f)
    assert result["html_pages_checked"] == 0
    assert result["host_outcomes"][0]["status"] == "robots_unavailable"
    assert len(f.requests) == 1


def test_429_sitemap_triggers_host_backoff():
    f = FakeFetcher(pages={"https://publisher.org/sitemap.xml": Response(429,"text/html",b"")})
    result, _ = execute(f)
    assert result["http_requests"] == 2
    assert result["host_outcomes"][0]["status"] == "host_retry_later"


def test_robots_excessive_delay_holds_requests():
    f=FakeFetcher(robots=b"User-agent: *\nCrawl-delay: 35\n")
    result, _=execute(f)
    assert result["html_pages_checked"]==0
    assert len(f.requests)==1
    assert result["host_outcomes"][0]["status"]=="robots_delay_exceeds_budget"


def test_meta_nofollow_prevents_internal_follow_but_records_direct_anchor():
    f=FakeFetcher(pages={
        "https://publisher.org/": Response(200,"text/html", b'''<meta name="robots" content="nofollow"><a href="/internal">Internal</a><a href="https://sunrun.com/">Target</a>'''),
        "https://publisher.org/internal": Response(200,"text/html", b'''<a href="https://nationsroof.com/">Would be found</a>'''),
    })
    result, _=execute(f)
    assert result["html_pages_checked"]==1
    assert result["html_anchor_edges_observed"]==1
    assert result["evidence"][0]["page_robots_meta_nofollow"] is True
    assert all(u!="https://publisher.org/internal" for u,_ in f.requests)


def test_no_outside_host_follow_or_private_url_request():
    f=FakeFetcher(pages={
        "https://publisher.org/": Response(200,"text/html", b'''<a href="https://evil.com/">External</a><a href="https://127.0.0.1/admin">Private</a><a href="https://publisher.org:8443/bad">Port</a>'''),
    })
    result,_=execute(f)
    assert result["html_anchor_edges_observed"]==0
    assert all(u.startswith("https://publisher.org/") for u,_ in f.requests)


def test_malicious_sitemap_xml_rejected_without_external_requests():
    payload = b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset><url><loc>&xxe;</loc></url></urlset>'
    assert parse_sitemap(payload, HOST)==[]


def test_tampered_source_scope_and_unreviewed_domain_rejected():
    original=plan_from_review(source_review(),(HOST,))
    for source in ("127.0.0.1", "notinreview.org"):
        with pytest.raises(SpiderHeld):
            plan_from_review(source_review(), (source,))
    broken=copy.deepcopy(original)
    broken["max_http_requests"]=9999
    with pytest.raises(SpiderHeld):
        crawl_pilot(broken,fetch=FakeFetcher(),wait=lambda _:None)


def test_host_and_frontier_bound_kept():
    f=FakeFetcher(pages={"https://publisher.org/":Response(200,"text/html",(
        "".join(f'<a href="/item{i}">x</a>' for i in range(500))
    ).encode())})
    result,_=execute(f)
    assert result["html_pages_checked"]<=5
    assert result["http_requests"]<=MAX_HTTP_REQUESTS
    assert result["html_anchor_edges_observed"]==0


def test_cli_review_only_uses_no_public_network(tmp_path,monkeypatch,capsys):
    p=tmp_path/"approved.json"
    p.write_text(json.dumps(source_review()))
    script=Path(__file__).resolve().parents[1]/"scripts/review_targeted_referrer_spider.py"
    monkeypatch.setattr(sys,"argv",["spider","--review-only","--historical-review",str(p)])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(script),run_name="__main__")
    assert e.value.code==0
    packet=json.loads(capsys.readouterr().out)
    assert packet["network_requests"]==0
    assert packet["status"]=="REVIEW_ONLY_SELECT_SOURCES"
