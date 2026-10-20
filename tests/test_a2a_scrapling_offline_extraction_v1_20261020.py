"""Scrapling parses only already-fetched bounded public HTML, without network."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

import pytest

from empire_os.a2a_scrapling_offline_extraction_v1 import safe_offline_parse
from empire_os.a2a_first_party_site_recovery_v1 import collect_approved_first_party_sites
from empire_os.a2a_first_party_recovery_readback_v1 import review_first_party_research
from tests.test_a2a_first_party_site_recovery_v1_20261020 import (
    sample, Session, fake_dns, NOW,
)


HTML = (b'<html><head><title>Roofing in Tampa</title>'
        b'<meta name="description" content="Tampa Bay roofing"></head>'
        b'<body><h1>Serving Tampa</h1><script type="application/ld+json">'
        b'{"@type":"LocalBusiness"}</script><p>Roofing contractor in Tampa Bay.</p>'
        b'<p>Email us at a_private_person@example.org</p></body></html>')


def test_offline_scrapling_structures_html_and_does_not_export_contacts():
    out = safe_offline_parse(HTML, source_url="https://roofer.example/")
    assert out["status"] == "SCRAPLING_STRUCTURED_PAGE_PARSED"
    assert out["document_sha256"] == sha256(HTML).hexdigest()
    assert out["public_page_title_observed"]
    assert out["public_h1_count_bounded"] == 1
    assert out["public_meta_description_observed"]
    assert out["json_ld_blocks_seen_bounded"] == 1
    assert not out["network_access_performed_by_parser"]
    assert not out["raw_page_or_private_contacts_exported"]
    assert "a_private_person" not in str(out)
    assert out["records_promoted_to_crm"] == 0


def test_existing_robots_checked_collector_only_passes_approved_page_html():
    session=Session(body=HTML)
    config=sample()
    collected=collect_approved_first_party_sites(
        config,session=session,dns_resolve=fake_dns,now=NOW,
        offline_html_parser=safe_offline_parse,
    )
    assert collected["pages_structured_with_scrapling"] == 1
    first=collected["records"][0]
    assert first["site_fetch_status"]=="HTTP_200"
    assert first["source_body_sha256"] == first["offline_structured_extraction"]["document_sha256"]
    assert len(session.calls)==2
    assert all(x[1]["allow_redirects"] is False for x in session.calls)
    assert collected["buyers_verified"] == 0


def test_robots_denial_prevents_scrapling_parsing():
    session=Session(robot=200,body=HTML)
    out=collect_approved_first_party_sites(
        sample(),session=session,dns_resolve=fake_dns,now=NOW,
        offline_html_parser=safe_offline_parse)
    assert out["pages_structured_with_scrapling"]==0
    assert out["records"][0]["offline_structured_extraction"] is None
    assert len(session.calls)==1


def test_local_readback_rejects_hash_mismatch_or_buyer_claim():
    session=Session(body=HTML)
    valid=collect_approved_first_party_sites(
        sample(),session=session,dns_resolve=fake_dns,now=NOW,
        offline_html_parser=safe_offline_parse)
    reviewed=review_first_party_research(sample(),valid,now=NOW)
    assert reviewed["scrapling_structured_site_count"]==1
    assert not reviewed["commercial_buying_intent_verified"]
    valid["records"][0]["offline_structured_extraction"]["document_sha256"]="0"*64
    with pytest.raises(ValueError, match="UNBOUND_SCRAPLING"):
        review_first_party_research(sample(),valid,now=NOW)
