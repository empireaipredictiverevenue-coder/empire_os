"""The original daily/weekly SEO owners, not a shadow agent, own this lifecycle."""
from datetime import datetime, timezone
import json
from pathlib import Path
import stat

import pytest

from empire_os.search_intelligence.seo_action_lifecycle_20261026 import (
    build_seo_action_lifecycle, SEOActionHeld
)
from scripts import review_original_seo_action_lifecycle_20261026 as operator

NOW = datetime(2026,10,26,19,6,tzinfo=timezone.utc)
BASE = "https://empire-ai.co.uk"


def action(route, code, priority="P2_INTERNAL_LINKS"):
    return {
        "url":BASE+route,"reason_code":code,"priority":priority,
        "next_action":"REVIEW_EXISTING_EVIDENCE",
        "website_change_authorized":False,"publication_authorized":False,
    }


def sources():
    original={
        "schema_version":"empire.search.seo_growth_action_queue.v1",
        "status":"EVIDENCE_BACKED_ACTION_QUEUE_READY",
        "source_property":"sc-domain:empire-ai.co.uk",
        "as_of":"2026-10-26",
        "execution_authority":"none","website_changed":False,
        "actions":[
            action("/aeo/roofing/DFW","COMMERCIAL_CTA_TWO_HOPS"),
            action("/research/campaign_001","COMMERCIAL_CTA_TWO_HOPS"),
            action("/commercial","NO_GSC_PAGE_ROW_RETURNED","P2_CONTENT_EVIDENCE"),
            action("/aeo/old/404/","RELEVANT_HISTORICAL_404","P2_ORIGINAL_CONTENT_REVIEW"),
        ]
    }
    daily={
        "schema_version":"empire.search.google_index_daily_watch.v1",
        "website_changed":False,"execution_authority":"none","observed_at":NOW.isoformat(),
        "exact_url_states":[],
    }
    journey={
        "schema_version":"empire.search.live_organic_to_buyer_observer.v1",
        "status":"GET_ONLY_PUBLIC_DISCOVERY_AUDIT",
        "site_mutations":False,
        "routes":[
            {"route":"/aeo/roofing/DFW","http_status":200,"issues":[],
             "direct_buyer_destinations":["/commercial"]},
            {"route":"/research/campaign_001","http_status":200,"issues":[],
             "first_party_research_enquiry_form_present":True},
        ],
    }
    release={
        "schema_version":"empire.seo.original_gated_aeo_release_result.v1",
        "status":"ORIGINAL_THREE_AEO_B2B_LINKS_GATED_RELEASE_LIVE_VERIFIED",
        "original_release_valid":True,"exact_approved_pages":3,"live_http_200_pages":3,
    }
    return original,daily,journey,release


def test_real_published_and_preexisting_forms_differ():
    packet=build_seo_action_lifecycle(*sources()[:2],buyer_journey=sources()[2],
                                      aeo_release=sources()[3],observed_at=NOW)
    rows={a["reason_code"]+"|"+a["url"]:a for a in packet["actions"]}
    a=rows["COMMERCIAL_CTA_TWO_HOPS|"+BASE+"/aeo/roofing/DFW"]
    assert a["state"]=="verified"
    assert a["published_claim"] is True
    assert "original_AEO_gated_release_live_receipt" in a["evidence_refs"]
    b=rows["COMMERCIAL_CTA_TWO_HOPS|"+BASE+"/research/campaign_001"]
    assert b["state"]=="verified"
    assert b["published_claim"] is False
    assert b["outcome"]=="ORIGINAL_CONSENTED_RESEARCH_ENQUIRY_FORM_ALREADY_PRESENT"
    assert packet["resolved_existing_owner_actions"]==2
    assert packet["verified_revenue"] is None
    assert packet["automated_publication_authorized"] is False


def test_unverified_release_cannot_invent_publication():
    w,d,j,r=sources()
    r["original_release_valid"]=False
    x=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    target=next(a for a in x["actions"] if "/aeo/roofing" in a["url"])
    assert target["state"]=="staged"
    assert target["published_claim"] is False


def test_404_is_prioritised_not_redirected():
    w,d,j,r=sources()
    x=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    a=next(a for a in x["actions"] if a["reason_code"]=="RELEVANT_HISTORICAL_404")
    assert a["state"]=="prioritised"
    assert a["owner"]=="original_website_editorial_owner"
    assert a["stage"]["publish_eligible"] is False


@pytest.mark.parametrize("bad_url",[
    "http://empire-ai.co.uk/commercial",
    "https://evil.example/commercial",
    "https://empire-ai.co.uk@evil.example/",
    "https://empire-ai.co.uk/commercial?token=secret",
    "https://empire-ai.co.uk/commercial#consent",
])
def test_only_exact_owned_https_urls_are_accepted(bad_url):
    w,d,j,r=sources()
    w["actions"][0]["url"]=bad_url
    with pytest.raises(SEOActionHeld,match="UNTRUSTED_ACTION"):
        build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)


def test_original_authority_must_remain_off():
    w,d,j,r=sources()
    w["actions"][0]["publication_authorized"]=True
    with pytest.raises(SEOActionHeld,match="EXCEEDS"):
        build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)


def test_stable_action_id_independent_of_weekly_age():
    w,d,j,r=sources()
    x=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    w["as_of"]="2026-11-02"
    y=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    assert [(a["id"],a["url"]) for a in x["actions"]]==[
        (a["id"],a["url"]) for a in y["actions"]]


def test_private_immutable_receipt_and_idempotence(tmp_path,monkeypatch):
    root=tmp_path/"existing_daily_owner"
    root.mkdir(mode=0o700)
    w,d,j,r=sources()
    packet=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    packet["read_only_technical_tests_executed"]=0
    monkeypatch.setattr(operator,"build_run",lambda **kwargs:packet)
    result=operator.run(observed=NOW,write=True,root=root)
    assert result["status"]=="ORIGINAL_DAILY_SEO_LIFECYCLE_RECORDED"
    receipt=Path(result["receipt"])
    assert stat.S_IMODE(receipt.stat().st_mode)==0o600
    assert json.loads(receipt.read_text())["original_action_count"]==4
    other=operator.run(observed=NOW,write=True,root=root)
    assert other["status"]=="EXISTING_SEO_LIFECYCLE_RECEIPT_PRESERVED"
    assert receipt.read_text()==receipt.read_text()


def test_no_world_readable_receipts(tmp_path,monkeypatch):
    root=tmp_path/"unsafe"
    root.mkdir(mode=0o755)
    packet=build_seo_action_lifecycle(*sources()[:2],observed_at=NOW)
    packet["read_only_technical_tests_executed"]=0
    monkeypatch.setattr(operator,"build_run",lambda **kwargs:packet)
    with pytest.raises(SEOActionHeld,match="PRIVATE_SEO_OWNER"):
        operator.run(observed=NOW,write=True,root=root)


def test_bounded_executor_never_marks_purchase_or_google_rank_as_real(monkeypatch):
    w,d,j,r=sources()
    packet=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    assert all(a["earned_revenue_verified"] is False for a in packet["actions"])
    assert all(a["organic_visits_verified"] is False for a in packet["actions"])
    assert packet["indexing_requests_submitted"]==0
    assert packet["outbound_sent"] is False
    assert packet["database_writes"] is False


def test_original_daily_owner_invokes_lifecycle_without_second_timer(monkeypatch,capsys):
    from scripts import review_daily_original_google_index_20261026 as daily_owner
    import sys
    monkeypatch.setattr(daily_owner,"execute",lambda **_: {
        "status":"ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED",
        "scope_checked":5,"indexed_verified":3,"unknown_to_google":2,
    })
    calls=[]
    def fake_run(**kwargs):
        calls.append(kwargs)
        return {"status":"EXISTING_SEO_LIFECYCLE_RECEIPT_PRESERVED"}
    monkeypatch.setattr(operator,"run",fake_run)
    monkeypatch.setattr(sys,"argv",["daily-owner","--write-daily"])
    assert daily_owner.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["seo_action_lifecycle"]["status"]=="EXISTING_SEO_LIFECYCLE_RECEIPT_PRESERVED"
    assert calls==[{"write":True}]


def test_daily_owner_preserves_primary_receipt_if_optional_lifecycle_held(monkeypatch,capsys):
    from scripts import review_daily_original_google_index_20261026 as daily_owner
    import sys
    monkeypatch.setattr(daily_owner,"execute",lambda **_: {
        "status":"ORIGINAL_DAILY_GOOGLE_INDEX_REVIEW_RECORDED"})
    monkeypatch.setattr(operator,"run",lambda **_: (_ for _ in ()).throw(ValueError("held")))
    monkeypatch.setattr(sys,"argv",["daily-owner","--write-daily"])
    assert daily_owner.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="ORIGINAL_DAILY_GOOGLE_INDEX_REVIEW_RECORDED"
    assert result["seo_action_lifecycle"]["status"]=="SEO_LIFECYCLE_HELD_PRIMARY_GOOGLE_WATCH_PRESERVED"
