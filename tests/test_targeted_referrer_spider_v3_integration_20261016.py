"""True-app tests, run in EmpireOS feature worktree after guarded V3 patch."""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlsplit
import pytest

from empire_os.search_intelligence.targeted_referrer_spider import (
    LinkParser, _approved_target_host, _observed_outbound_url,
    _known_fetch_hold_code, safe_fetch, crawl_pilot, plan_from_review,
    MAX_HTTP_REQUESTS,
)
from empire_os.search_intelligence.backlink_live_verifier import VerificationHeld


@dataclass
class Response:
    status: int
    content_type: str
    body: bytes


def graph_review():
    return {
        "schema_version":"empire.cc.graph.referrer_review_queue.v1",
        "source":"commoncrawl_2026_domain_webgraph",
        "mode":"OBSERVE", "empiredb_writes":False,
        "verified_live_backlink_count":0,
        "distinct_historical_source_domains":1,
        "manual_review_queue":[{
            "source_domain":"publisher.org",
            "observed_target_domains":["sunrun.com"],
            "linked_target_count":1, "technical_name_hint":False,
            "editorial_link_verified":False,
            "source_page_url_known":False,"authority_score":None,
        }],
    }


@pytest.mark.parametrize("actual,expected",[
    ("sunrun.com","sunrun.com"),
    ("www.sunrun.com","sunrun.com"),
    ("sunrun.com.attacker.org",None),
    ("solar.sunrun.com",None),
    ("www.notapproved.com",None),
    (None,None),
])
def test_strict_target_host_equivalence(actual,expected):
    assert _approved_target_host(actual,frozenset(["sunrun.com"])) == expected


@pytest.mark.parametrize("href,expected",[
    ("http://www.sunrun.com/a#section","http://www.sunrun.com/a"),
    ("https://www.sunrun.com/a#section","https://www.sunrun.com/a"),
    ("//www.sunrun.com/a","https://www.sunrun.com/a"),
    ("javascript:alert(1)",None),
    ("http://127.0.0.1/a",None),
    ("http://sunrun.com:8080/a",None),
    ("http://login:secret@sunrun.com/a",None),
    ("http://[::1]/admin",None),
])
def test_text_only_outbound_url_no_network(href,expected):
    assert _observed_outbound_url("https://publisher.org/",href)==expected


def test_parser_extracts_http_www_but_never_follows_internal_http():
    p=LinkParser("https://publisher.org/","publisher.org",frozenset(["sunrun.com"]))
    p.feed('''<a href="http://www.sunrun.com/a" rel="nofollow">S</a>
        <a href="https://www.sunrun.com/b" rel="sponsored">B</a>
        <a href="https://blog.sunrun.com/c">not scoped</a>
        <a href="http://publisher.org/unsafe">no internal http</a>
        <a href="/approved">approved internal</a>''')
    assert set(p.outbound)=={"http://www.sunrun.com/a", "https://www.sunrun.com/b"}
    assert p.outbound["http://www.sunrun.com/a"]=={"nofollow"}
    assert p.internal==["https://publisher.org/approved"]


def test_pilot_provenance_uses_reviewed_apex_and_does_not_fetch_target():
    fetched=[]
    html=b'<a rel="sponsored" href="http://www.sunrun.com/solar">solar</a>'
    def mock_fetch(url,*,max_bytes):
        fetched.append(url)
        if url=="https://publisher.org/robots.txt":
            return Response(200,"text/plain",b"User-agent: *\nAllow: /\n")
        if url=="https://publisher.org/sitemap.xml":
            return Response(404,"text/html",b"")
        if url=="https://publisher.org/":
            return Response(200,"text/html",html)
        raise AssertionError("No target fetch permitted: "+url)
    plan=plan_from_review(graph_review(),("publisher.org",))
    result=crawl_pilot(plan,fetch=mock_fetch,wait=lambda _:None)
    assert result["http_requests"]==3
    assert result["html_anchor_edges_observed"]==1
    row=result["evidence"][0]
    assert row["target_host"]=="www.sunrun.com"
    assert row["approved_target_host"]=="sunrun.com"
    assert row["outbound_href_scheme"]=="http"
    assert row["target_url_not_fetched"] is True
    assert row["search_engine_counts_link"] is None
    assert row["editorial_link_value_verified"] is False
    assert result["empiredb_writes"] is False
    assert result["http_requests"]<=MAX_HTTP_REQUESTS
    assert all(url.startswith("https://publisher.org/") for url in fetched)


@pytest.mark.parametrize("reason,expected",[
    ("dns_lookup_failed","fetch_held_dns_failure"),
    ("nonpublic_dns_address_blocked","fetch_held_private_dns_blocked"),
    ("network_or_tls_error","fetch_held_network_tls_failure"),
    ("response_exceeds_byte_budget","fetch_held_byte_budget"),
    ("encoded_body_not_supported","fetch_held_encoded_body"),
    ("a secret 192.168.0.7 address","fetch_held"),
])
def test_coarse_hold_codes_do_not_leak(reason,expected):
    assert _known_fetch_hold_code(VerificationHeld(reason))==expected
    def bad_fetch(*a,**kw):
        raise VerificationHeld(reason)
    assert safe_fetch(bad_fetch,"https://publisher.org/",4096)==(None,expected)
