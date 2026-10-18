"""Reuse canonical legacy 404 probe with verified page-only Search Console."""
from datetime import date
import json

import pytest

from scripts import review_live_search_404_revenue_readonly as existing
from scripts import review_live_search_page_404_revenue_readonly as runner
from empire_os.search_intelligence.legacy_404_page_review import (
    LegacyPageReviewHeld, review_page_only_legacy_404,
)

START=date(2026,10,8)
END=date(2026,10,17)
TODAY=date(2026,10,18)


def row(path, impres=2, clicks=0, ctr=None, position=9.5):
    return {
        "keys":[path],
        "impressions":impres,
        "clicks":clicks,
        "ctr": clicks/impres if ctr is None and impres else ctr or 0,
        "position":position,
    }


def packet(rows):
    return {
        "source":"google_search_console", "site_url":existing.SITE,
        "available":True,"count":len(rows),"items":rows,
        "dimensions":["page"],"data_state":"final",
        "window":[START.isoformat(),END.isoformat()],
    }


def run_review(rows, *, origin_status=lambda _:404):
    return review_page_only_legacy_404(
        packet(rows), start=START, end=END, today=TODAY,
        safe_path=existing._safe_path, origin_status=origin_status,
    )


def test_live_like_priority_and_reconciled_total_are_only_page_dimension():
    rows=[
        row("https://empire-ai.co.uk/",13,0,0,7.1),
        row("https://www.empire-ai.co.uk/",3,0,0,24.7),
        row("https://empire-ai.co.uk/aeo/empire/ai_lead_gen/",2),
        row("https://empire-ai.co.uk/aeo/roof-repair/MIN/",2),
        row("https://empire-ai.co.uk/aeo/accounting/TAM/",1),
        row("https://empire-ai.co.uk/aeo/antenna-install/EUG/",4),
    ]
    seen=[]
    report=run_review(rows,origin_status=lambda path:seen.append(path) or 404)
    assert report["returned_page_rows"]==6
    assert report["returned_page_impressions"]==25
    assert report["returned_page_clicks"]==0
    assert report["missing_legacy_page_count"]==4
    assert report["missing_legacy_page_impressions"]==9
    assert len(seen)==4
    assert set(seen)=={
        "/aeo/empire/ai_lead_gen/","/aeo/roof-repair/MIN/",
        "/aeo/accounting/TAM/","/aeo/antenna-install/EUG/",
    }
    assert report["query_page_rows_joined_or_added"] is False
    assert report["returned_page_totals_are_sitewide"] is False
    assert [x["review_category"] for x in report["missing_review_queue"]]==[
        "BUYER_INTENT_EDITORIAL_REVIEW","EMPIRE_PRODUCT_TOPIC_REVIEW",
        "ROOFING_RESEARCH_REVIEW","OFF_CORE_RETAIN_404_PENDING_EVIDENCE",
    ]
    assert report["redirect_authorized"] is False
    assert report["publication_authorized"] is False
    assert report["revenue_verified"] is False
    assert report["database_writes"] is False
    assert report["outbound_sent"] is False
    assert "query" not in json.dumps(report).replace("query_page_rows_joined_or_added","")
    assert all(item["restore_authorized"] is False for item in report["missing_review_queue"])


def test_known_page_now_200_not_reported_as_broken():
    report=run_review([
        row("https://empire-ai.co.uk/aeo/empire/ai_lead_gen/",1),
    ],origin_status=lambda path:200)
    assert report["missing_legacy_page_count"]==0
    assert report["missing_review_queue"]==[]


def test_unknown_off_core_is_not_recommended_to_be_redirected():
    report=run_review([
        row("https://empire-ai.co.uk/aeo/antenna-install/EUG/",4),
    ])
    x=report["missing_review_queue"][0]
    assert x["review_action"]=="DO_NOT_REDIRECT_WITHOUT_GENUINE_EQUIVALENT_CONTENT"
    assert x["current_page_equivalence_verified"] is False
    assert x["publisher_rights_verified"] is False
    assert x["redirect_authorized"] is False


@pytest.mark.parametrize("bad",[
    "http://empire-ai.co.uk/aeo/empire/ai_lead_gen/",
    "https://www.empire-ai.co.uk/aeo/empire/ai_lead_gen/",
    "https://empire-ai.co.uk.evil.test/aeo/empire/ai_lead_gen/",
    "https://empire-ai.co.uk:5443/aeo/empire/ai_lead_gen/",
    "https://empire-ai.co.uk/aeo/empire/ai_lead_gen/?email=secret",
    "https://empire-ai.co.uk/aeo/empire/ai_lead_gen/#foo",
    "https://empire-ai.co.uk/admin",
    "https://empire-ai.co.uk/%2e%2e/secret",
    "file:///etc/passwd",
])
def test_untrusted_paths_never_trigger_http_get(bad):
    called=[]
    result=run_review([row(bad,4)],origin_status=lambda path:called.append(path) or 404)
    assert called==[]
    assert result["excluded_not_allowlisted_urls"]==1
    assert result["missing_legacy_page_count"]==0
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(available=False),
    lambda x: x.update(source="pretend_gsc"),
    lambda x: x.update(site_url="sc-domain:attacker.test"),
    lambda x: x.update(data_state="partial"),
    lambda x: x.update(dimensions=["query","page"]),
    lambda x: x.update(window=["2026-09-08","2026-10-17"]),
    lambda x: x.update(count=2),
    lambda x: x.update(items="bad"),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/aeo/roofing/PVD/", -1)]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/aeo/roofing/PVD/", True)]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/aeo/roofing/PVD/", 1,2)]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/aeo/roofing/PVD/", 2,0,.7)]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/aeo/roofing/PVD/", 1,0,0,float("nan"))]),
    lambda x: x.update(items=[{"keys":["private","https://empire-ai.co.uk/aeo/roofing/PVD/"],"clicks":0,"impressions":1,"ctr":0,"position":3}]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/aeo/roofing/PVD/")]*2),
])
def test_bad_page_only_gsc_packets_fail_closed(mutation):
    r=packet([row("https://empire-ai.co.uk/aeo/roofing/PVD/")])
    mutation(r)
    with pytest.raises(LegacyPageReviewHeld):
        review_page_only_legacy_404(
            r,start=START,end=END,today=TODAY,
            safe_path=existing._safe_path,origin_status=lambda _:404)


@pytest.mark.parametrize("start,end,today",[
    (START,END,END),
    (END,START,TODAY),
    (date(2026,8,1),END,TODAY),
])
def test_date_cannot_be_current_or_unbounded(start,end,today):
    with pytest.raises(LegacyPageReviewHeld):
        review_page_only_legacy_404(
            packet([]),start=start,end=end,today=today,
            safe_path=existing._safe_path,origin_status=lambda _:404)


def test_duplicate_alias_or_unexpected_origin_http_fail_closed():
    with pytest.raises(LegacyPageReviewHeld,match="AMBIGUOUS_PAGE_ALIASES"):
        run_review([
            row("https://empire-ai.co.uk/aeo/roof-repair/MIN"),
            row("https://empire-ai.co.uk/aeo/roof-repair/MIN/"),
        ])
    with pytest.raises(LegacyPageReviewHeld,match="UNVERIFIED_ORIGIN_HTTP_STATUS"):
        run_review([row("https://empire-ai.co.uk/aeo/roof-repair/MIN/")],
                   origin_status=lambda _:500)


def test_runner_reuses_existing_readonly_transport_and_no_raw_queries(monkeypatch):
    called=[]
    def fake(path):
        called.append(path)
        if path=="/search-console/status":
            return {"available":True,"site_url":existing.SITE}
        assert path.startswith("/search-console/pages?")
        return packet([
            row("https://empire-ai.co.uk/aeo/empire/ai_lead_gen/",2),
        ])
    monkeypatch.setattr(existing,"_json_get",fake)
    monkeypatch.setattr(existing,"_get",lambda path,*,search:(404,b""))
    report=runner.run(start=START,end=END,today=TODAY)
    assert report["missing_legacy_page_count"]==1
    assert "/search-console/observations" not in str(called)
    assert any("/search-console/pages?" in x for x in called)
    assert report["execution_authority"]=="none"


def test_missing_page_dimension_api_never_claims_no_broken_pages(monkeypatch):
    def fake(path):
        if path=="/search-console/status":
            return {"available":True,"site_url":existing.SITE}
        raise existing.ReviewHeld("READ_ONLY_ENDPOINT_FAILURE")
    monkeypatch.setattr(existing,"_json_get",fake)
    d=runner.run(start=START,end=END,today=TODAY)
    assert d["status"]=="HELD"
    assert d["reason_code"]=="READ_ONLY_ENDPOINT_FAILURE"
    assert d["publication_authorized"] is False


def test_transport_allowlist_accepts_only_fixed_new_reader():
    try:
        existing._get("/search-console/pages?start_date=2026-10-08&end_date=2026-10-17&limit=250",
                      search=True)
    except existing.ReviewHeld as exc:
        assert str(exc)!="UNAPPROVED_SEARCH_API"
    with pytest.raises(existing.ReviewHeld,match="UNAPPROVED_SEARCH_API"):
        existing._get("/search-console/page-delete",search=True)
