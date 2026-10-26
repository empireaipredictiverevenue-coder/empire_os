"""Existing GSC weekly owner produces an immutable evidence-based research view."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import stat
import sys

import pytest

from empire_os.weekly_keyword_intent_review import (
    build_weekly_keyword_intent_review,
    run_weekly_keyword_intent_review,
)
from scripts import report_weekly_two_page_gsc_20261022 as owner


AS_OF=date(2026,10,26)


def packet():
    return {
        "source":"google_search_console",
        "site_url":"sc-domain:empire-ai.co.uk",
        "available":True,
        "count":2,
        "limit":250,
        "items":[
            {
                "keys":["how do i know which accounts in my tam are actually ready to buy right now",
                        "https://empire-ai.co.uk/aeo/accounting/TAM/"],
                "clicks":0,"impressions":1,"ctr":0.0,"position":8.0,
            },
            {
                "keys":["unrelated historical query","https://empire-ai.co.uk/"],
                "clicks":1,"impressions":5,"ctr":0.2,"position":15.0,
            },
        ],
    }


def test_automated_weekly_review_one_gsc_get_for_four_markets():
    calls=[]
    def transport(url):
        calls.append(url)
        return json.dumps(packet()).encode("utf8")
    result=build_weekly_keyword_intent_review(as_of=AS_OF,transport=transport)
    assert len(calls)==1
    assert calls[0].startswith("http://127.0.0.1:8771/v1/search/search-console/observations?")
    assert "start_date=2026-10-17" in calls[0]
    assert "end_date=2026-10-23" in calls[0]
    assert result["gsc_window"]==["2026-10-17","2026-10-23"]
    assert result["source_status"]=="FIRST_PARTY_GSC_QUERY_PAGE_OBSERVED"
    assert result["market_research_count"]==4
    tam=next(t for t in result["market_reviews"] if t["market_key"]=="b2b-tam-buyer-readiness")
    assert tam["first_party_exact_query_matches"]==1
    assert tam["observed_exact_query_page_evidence"][0]["page_evidence"][0]["reported_impressions"]==1
    assert tam["observed_exact_query_page_evidence"][0]["page_evidence"][0]["reported_clicks"]==0
    assert result["paid_provider_calls"]==0
    assert result["search_fabric_calls"]==0
    assert result["sale_or_revenue_verified"] is False
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False


def test_missing_source_is_reported_held_without_fake_no_demand():
    r=build_weekly_keyword_intent_review(as_of=AS_OF,transport=lambda _: b'bad-json')
    assert r["source_status"]=="HELD_GSC_QUERY_PAGE_SOURCE_UNAVAILABLE_OR_UNVERIFIED"
    assert r["original_query_page_rows_returned"] is None
    assert all(t["first_party_exact_query_matches"] is None for t in r["market_reviews"])
    assert all(t["real_market_keyword_volume"] is None for t in r["market_reviews"])


def test_archive_is_private_immutable_and_same_existing_review_folder(tmp_path):
    root=tmp_path/"existing_seo_weekly"
    root.mkdir(mode=0o700)
    result=run_weekly_keyword_intent_review(
        as_of=AS_OF,write_private=True,root=root,
        transport=lambda _:json.dumps(packet()).encode(),
    )
    assert result["status"]=="PRIVATE_WEEKLY_KEYWORD_REVIEW_WRITTEN"
    receipt=Path(result["receipt"])
    assert receipt.parent==root
    assert stat.S_IMODE(receipt.stat().st_mode)==0o600
    assert json.loads(receipt.read_text())["market_research_count"]==4
    with pytest.raises(ValueError,match="NO_OVERWRITE"):
        run_weekly_keyword_intent_review(
            as_of=AS_OF,write_private=True,root=root,
            transport=lambda _:json.dumps(packet()).encode(),
        )
    assert len(list(root.glob("weekly_keyword_intent_*.json")))==1


def test_no_world_accessible_receipts(tmp_path):
    root=tmp_path/"unsafe"
    root.mkdir(mode=0o755)
    with pytest.raises(ValueError,match="OWNER_DIRECTORY_UNSAFE"):
        run_weekly_keyword_intent_review(
            as_of=AS_OF,write_private=True,root=root,
            transport=lambda _:json.dumps(packet()).encode(),
        )


def test_existing_weekly_observer_calls_research_without_changed_public_contract(monkeypatch,capsys):
    calls=[]
    monkeypatch.setattr(owner,"run",lambda *,as_of,write_private:{
        "status":"PRIVATE_WEEKLY_GSC_REPORT_WRITTEN","as_of":as_of.isoformat(),
    })
    def supplement(*,as_of,write_private):
        calls.append((as_of,write_private))
        return {"status":"PRIVATE_WEEKLY_KEYWORD_REVIEW_WRITTEN"}
    monkeypatch.setattr(owner,"run_weekly_keyword_intent_review",supplement)
    monkeypatch.setattr(sys,"argv",["weekly", "--as-of","2026-10-26","--write-private"])
    owner.main()
    response=json.loads(capsys.readouterr().out)
    assert response["status"]=="PRIVATE_WEEKLY_GSC_REPORT_WRITTEN"
    assert response["keyword_intent_review"]["status"]=="PRIVATE_WEEKLY_KEYWORD_REVIEW_WRITTEN"
    assert calls==[(AS_OF,True)]


def test_weekly_owner_fails_supplement_but_preserves_original_receipt(monkeypatch,capsys):
    monkeypatch.setattr(owner,"run",lambda *,as_of,write_private:{
        "status":"PRIVATE_WEEKLY_GSC_REPORT_WRITTEN","as_of":as_of.isoformat(),
    })
    def failure(*,as_of,write_private):
        raise ValueError("bounded_keyword_subreview_not_available")
    monkeypatch.setattr(owner,"run_weekly_keyword_intent_review",failure)
    monkeypatch.setattr(sys,"argv",["weekly","--as-of","2026-10-26","--write-private"])
    owner.main()
    response=json.loads(capsys.readouterr().out)
    assert response["status"]=="PRIVATE_WEEKLY_GSC_REPORT_WRITTEN"
    assert response["keyword_intent_review"]["status"]=="HELD_WEEKLY_KEYWORD_REVIEW_NOT_ARCHIVED"
    assert response["keyword_intent_review"]["primary_weekly_gsc_receipt_unmodified"] is True


def test_plain_existing_weekly_review_remains_unchanged(monkeypatch,capsys):
    monkeypatch.setattr(owner,"run",lambda *,as_of,write_private:{"status":"READ_ONLY"})
    monkeypatch.setattr(owner,"run_weekly_keyword_intent_review",
                        lambda **_:pytest.fail("should_not_run_for_normal_read"))
    monkeypatch.setattr(sys,"argv",["weekly","--as-of","2026-10-26"])
    owner.main()
    assert json.loads(capsys.readouterr().out)=={"status":"READ_ONLY"}


def test_unmatched_real_gsc_queries_feed_original_semantic_review():
    report=build_weekly_keyword_intent_review(
        as_of=AS_OF,transport=lambda _:json.dumps(packet()).encode(),
    )
    assert report["unmatched_first_party_query_page_rows"] == 1
    rows=report["unmatched_first_party_semantic_review_preview"]
    assert len(rows)==1
    assert rows[0]["query"]=="unrelated historical query"
    assert rows[0]["source_kind"]=="GSC_QUERY_PAGE"
    assert rows[0]["evidence_ref"].startswith("gsc-query-page-sha256:")
    assert rows[0]["matched_original_seed"] is False
    assert rows[0]["qualified_buyer_verified"] is False
    assert rows[0]["ai_answer_citation_verified"] is False
    assert rows[0]["market_search_volume"] is None
    assert all("how do i know" not in row["query"] for row in rows)


def test_missing_gsc_evidence_stays_unknown_for_unmatched_discovery():
    report=build_weekly_keyword_intent_review(
        as_of=AS_OF,transport=lambda _:b'{invalid',
    )
    assert report["unmatched_first_party_query_page_rows"] is None
    assert report["unmatched_first_party_semantic_review_preview"] == []


def test_private_research_drops_email_like_observed_keyword():
    source=packet()
    source["items"][1]["keys"][0]="client@example.com audit request"
    result=build_weekly_keyword_intent_review(
        as_of=AS_OF,transport=lambda _:json.dumps(source).encode(),
    )
    assert result["unmatched_first_party_query_page_rows"]==0
    assert result["source_query_rows_redacted_for_privacy"]==1
    assert result["unmatched_first_party_semantic_review_preview"]==[]
