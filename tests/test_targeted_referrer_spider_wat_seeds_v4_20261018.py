"""Offline page-level WAT seeding tests. No network access or production mutations."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from empire_os.search_intelligence.historical_spider_seeds import add_wat_page_seeds
from empire_os.search_intelligence.targeted_referrer_spider import (
    MAX_HTTP_REQUESTS, SpiderHeld, crawl_pilot, plan_from_review,
)

SOURCE = "publisher.org"
TARGET = "sunrun.com"
PAGE = "https://publisher.org/reports/solar-study"


def graph_review():
    return {
        "schema_version": "empire.cc.graph.referrer_review_queue.v1",
        "source": "commoncrawl_2026_domain_webgraph",
        "mode": "OBSERVE", "empiredb_writes": False,
        "verified_live_backlink_count": 0,
        "distinct_historical_source_domains": 1,
        "manual_review_queue": [{
            "source_domain": SOURCE, "observed_target_domains": [TARGET],
            "linked_target_count": 1, "technical_name_hint": False,
            "editorial_link_verified": False, "source_page_url_known": False,
            "authority_score": None,
        }],
    }


def observation(source=PAGE, target="https://sunrun.com/solar"):
    return {
        "source": "commoncrawl_wat_archived_link",
        "source_url": source, "target_url": target,
        "provenance": [
            "commoncrawl", "CC-MAIN-2026-39", "archive:sample.wat.gz",
            "type:html_anchor", "status:historical_unverified",
        ],
    }


def wat_receipt(rows=None):
    rows = [observation()] if rows is None else rows
    return {
        "schema_version": "empire.commoncrawl.wat_backlinks.review.v1",
        "source": "commoncrawl_historical_wat",
        "mode": "OBSERVE", "network_requests": 0,
        "database_writes": False, "execution_authority": "none",
        "candidate_backlink_edges": len(rows),
        "observations": rows,
    }


def seeded_plan(rows=None):
    return add_wat_page_seeds(
        plan_from_review(graph_review(), (SOURCE,)),
        wat_receipt(rows),
    )


@dataclass
class Response:
    status: int
    content_type: str
    body: bytes


class FakeFetch:
    def __init__(self, *, denied=False, backoff=False):
        self.calls = []
        self.denied = denied
        self.backoff = backoff

    def __call__(self, url, *, max_bytes):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            rules = b"User-agent: *\nDisallow: /\n" if self.denied else b"User-agent: *\nAllow: /\n"
            return Response(200, "text/plain", rules)
        if url.endswith("/sitemap.xml"):
            return Response(429 if self.backoff else 404, "text/html", b"")
        if url == PAGE:
            return Response(200, "text/html", b'<a href="https://sunrun.com/solar" rel="nofollow">Solar</a>')
        return Response(404, "text/html", b"")


def test_valid_wat_url_becomes_one_archival_seed_without_network():
    plan = seeded_plan()
    assert plan["historical_page_seed_count"] == 1
    assert plan["historical_page_seeds"] == {SOURCE: [PAGE]}
    assert plan["network_requests"] == 0
    assert plan["empiredb_writes"] is False
    assert plan["historical_seed_provenance"].endswith("_unverified")


def test_wat_seed_fetch_observes_html_only_under_regular_limits():
    f = FakeFetch()
    result = crawl_pilot(seeded_plan(), fetch=f, wait=lambda _: None)
    assert f.calls[:3] == [
        "https://publisher.org/robots.txt",
        "https://publisher.org/sitemap.xml", PAGE,
    ]
    assert all(x.startswith("https://publisher.org/") for x in f.calls)
    assert result["http_requests"] <= MAX_HTTP_REQUESTS
    assert result["html_pages_checked"] == 1
    assert result["html_anchor_edges_observed"] == 1
    assert result["evidence"][0]["evidence_type"] == "spider_observed_html_anchor"
    assert result["evidence"][0]["search_engine_counts_link"] is None
    assert result["host_outcomes"][0]["historical_seed_pages_html_checked"] == 1
    assert result["production_changed"] is False
    assert result["empiredb_writes"] is False


def test_robots_disallow_stops_all_seed_pages():
    f = FakeFetch(denied=True)
    result = crawl_pilot(seeded_plan(), fetch=f, wait=lambda _: None)
    assert f.calls == ["https://publisher.org/robots.txt"]
    assert result["html_anchor_edges_observed"] == 0
    assert result["host_outcomes"][0]["historical_seed_pages_attempted"] == 0


def test_host_backoff_stops_seed_pages():
    f = FakeFetch(backoff=True)
    result = crawl_pilot(seeded_plan(), fetch=f, wait=lambda _: None)
    assert f.calls == ["https://publisher.org/robots.txt", "https://publisher.org/sitemap.xml"]
    assert result["html_pages_checked"] == 0
    assert result["host_outcomes"][0]["historical_seed_pages_attempted"] == 0


@pytest.mark.parametrize("source", [
    "http://publisher.org/reports/solar-study",
    "https://publisher.org/admin/reports",
    "https://publisher.org/solar?secret=1",
    "https://sub.publisher.org/solar",
    "https://publisher.org:8443/solar",
    "https://publisher.org@private.org/solar",
    "https://publisher.org/article.pdf",
])
def test_ineligible_archived_source_never_enters_fetch_queue(source):
    p = seeded_plan([observation(source=source)])
    assert p["historical_page_seed_count"] == 0


def test_unrelated_wat_target_is_not_a_seed():
    p = seeded_plan([observation(target="https://anothercompany.com")])
    assert p["historical_page_seed_count"] == 0


@pytest.mark.parametrize("change", [
    lambda x: x.update({"source": "untrusted_archive"}),
    lambda x: x.update({"network_requests": 1}),
    lambda x: x.update({"database_writes": True}),
    lambda x: x.update({"candidate_backlink_edges": 5}),
    lambda x: x["observations"][0].update({"source": "invented_backlink"}),
    lambda x: x["observations"][0].update({"provenance": []}),
])
def test_untrusted_or_inconsistent_archival_receipt_is_rejected(change):
    r = wat_receipt()
    change(r)
    with pytest.raises(SpiderHeld):
        add_wat_page_seeds(plan_from_review(graph_review(), (SOURCE,)), r)


def test_dedup_and_five_page_limit():
    urls = [f"https://publisher.org/news/solar-{n}" for n in range(11)]
    receipt = wat_receipt([observation(source=u) for u in reversed(urls)] + [observation(source=urls[0])])
    plan = add_wat_page_seeds(plan_from_review(graph_review(), (SOURCE,)), receipt)
    assert plan["historical_page_seeds"][SOURCE] == sorted(urls)[:5]
    assert plan["historical_page_seed_count"] == 5


@pytest.mark.parametrize("mutation", [
    lambda p: p["historical_page_seeds"].update({SOURCE: ["https://other.org/abc"]}),
    lambda p: p.update({"historical_page_seed_count": 2}),
    lambda p: p.update({"historical_seed_provenance": "invented"}),
    lambda p: p["historical_page_seeds"].update({SOURCE: ["http://publisher.org/a"]}),
])
def test_tampered_seed_plan_is_rejected_before_network(mutation):
    plan = seeded_plan()
    mutation(plan)
    f = FakeFetch()
    with pytest.raises(SpiderHeld):
        crawl_pilot(plan, fetch=f, wait=lambda _: None)
    assert f.calls == []


def test_cli_review_only_redacts_source_page_url(tmp_path):
    root = Path(__file__).resolve().parents[1]
    graph = tmp_path / "graph.json"
    wat = tmp_path / "wat.json"
    graph.write_text(json.dumps(graph_review()))
    wat.write_text(json.dumps(wat_receipt()))
    command = [
        sys.executable, str(root / "scripts/review_targeted_referrer_spider.py"),
        "--review-only", "--historical-review", str(graph),
        "--source-host", SOURCE, "--wat-evidence", str(wat),
    ]
    done = subprocess.run(command, text=True, capture_output=True,
                          env={**os.environ, "PYTHONPATH": str(root)}, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    result = json.loads(done.stdout)
    assert result["historical_page_seed_count"] == 1
    assert "historical_page_seeds" not in result
    assert PAGE not in done.stdout
    assert result["network_requests"] == 0


def test_cli_no_selected_host_with_wat_evidence_is_held(tmp_path):
    root = Path(__file__).resolve().parents[1]
    graph = tmp_path / "graph.json"
    wat = tmp_path / "wat.json"
    graph.write_text(json.dumps(graph_review()))
    wat.write_text(json.dumps(wat_receipt()))
    done = subprocess.run(
        [sys.executable, str(root / "scripts/review_targeted_referrer_spider.py"),
         "--review-only", "--historical-review", str(graph),
         "--wat-evidence", str(wat)],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(root)},
    )
    assert done.returncode == 2
    assert json.loads(done.stdout)["status"] == "TARGETED_SPIDER_HELD"
