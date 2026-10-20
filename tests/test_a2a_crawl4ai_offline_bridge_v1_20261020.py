"""Crawl4AI receives only previously fetched approved HTML; not an extra crawler."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import pytest

from empire_os.a2a_crawl4ai_offline_bridge_v1 import (
    SCHEMA, parse_crawl4ai_existing_html,
)
from empire_os.a2a_first_party_site_recovery_v1 import collect_approved_first_party_sites
from empire_os.a2a_first_party_recovery_readback_v1 import review_first_party_research
from tests.test_a2a_first_party_site_recovery_v1_20261020 import sample, Session, fake_dns, NOW

HTML=b'<html><body><h1>Roofing services Tampa</h1><p>We serve Tampa Bay.</p><p>Person: jane@example.org</p></body></html>'


def test_real_offline_crawl4ai_helper_never_outputs_raw_page():
    record=parse_crawl4ai_existing_html(HTML,source_url="https://roofer.example/")
    assert record["schema_version"]==SCHEMA
    assert record["status"]=="CRAWL4AI_MARKDOWN_EXTRACTED"
    assert record["source_html_sha256"]==sha256(HTML).hexdigest()
    assert record["markdown_chars_bounded"]>0
    assert "jane@example.org" not in str(record)
    assert not record["headless_browser_launched"]
    assert not record["source_url_fetched_by_this_module"]
    assert not record["buyer_purchase_intent_verified"]


def test_collector_one_fetch_two_offline_extractor_hooks():
    session=Session(body=HTML)
    parsed=collect_approved_first_party_sites(
        sample(),session=session,dns_resolve=fake_dns,now=NOW,
        offline_crawl4ai_parser=parse_crawl4ai_existing_html)
    assert len(session.calls)==2
    assert parsed["pages_converted_with_crawl4ai_offline"]==1
    row=parsed["records"][0]
    assert row["source_body_sha256"]==row["offline_crawl4ai_extraction"]["source_html_sha256"]
    reviewed=review_first_party_research(sample(),parsed,now=NOW)
    assert reviewed["crawl4ai_offline_site_count"]==1
    assert not reviewed["commercial_buying_intent_verified"]


def test_robots_denied_means_zero_browser_or_crawl4ai():
    s=Session(robot=200,body=HTML)
    result=collect_approved_first_party_sites(
        sample(),session=s,dns_resolve=fake_dns,now=NOW,
        offline_crawl4ai_parser=parse_crawl4ai_existing_html)
    assert len(s.calls)==1
    assert result["pages_converted_with_crawl4ai_offline"]==0


def test_crawl4ai_digest_mismatch_rejected_by_hourly_readback():
    s=Session(body=HTML)
    packet=collect_approved_first_party_sites(
        sample(),session=s,dns_resolve=fake_dns,now=NOW,
        offline_crawl4ai_parser=parse_crawl4ai_existing_html)
    packet["records"][0]["offline_crawl4ai_extraction"]["source_html_sha256"]="a"*64
    with pytest.raises(ValueError,match="UNBOUND_CRAWL4AI"):
        review_first_party_research(sample(),packet,now=NOW)
