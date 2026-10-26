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
        "status":"GOOGLE_INDEX_WATCH_RECORDED",
        "scope_checked":5,
        "google_indexing_submissions":0,
        "database_writes":False,
        "full_site_indexation_verified":False,
        "indexed_verified":3,
        "unknown_to_google":2,
        "exact_url_states":{
            BASE+"/":"GOOGLE_INDEXED_VERSION_VERIFIED",
            BASE+"/commercial":"GOOGLE_HAS_NO_URL_RECORD",
            BASE+"/industries/roofing":"GOOGLE_INDEXED_VERSION_VERIFIED",
            BASE+"/industries/solar":"GOOGLE_HAS_NO_URL_RECORD",
            BASE+"/predictive-revenue":"GOOGLE_INDEXED_VERSION_VERIFIED",
        },
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
    monkeypatch.setattr(operator,"build_run",lambda **kwargs:pytest.fail("duplicate_live_source_read"))
    other=operator.run(observed=NOW,write=True,root=root)
    assert other["status"]=="EXISTING_SEO_LIFECYCLE_RECEIPT_PRESERVED"
    assert other["new_live_checks"]==0
    assert len(list(root.glob("seo-actions-*.json")))==1


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

def test_actual_original_google_mapping_is_carried_to_each_action():
    w,d,j,r=sources()
    result=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    states={a["url"]:a["index_status_first_party"] for a in result["actions"]}
    assert states[BASE+"/commercial"]=="GOOGLE_HAS_NO_URL_RECORD"
    assert states[BASE+"/aeo/roofing/DFW"] is None
    assert result["indexing_requests_submitted"]==0


def test_real_original_aeo_v2_receipt_is_not_rejected_as_old_release():
    w,d,j,r=sources()
    r={
        "schema_version":"empire.seo.original_gated_aeo_source_hint_release.v2",
        "status":"ORIGINAL_THREE_AEO_SOURCE_HINT_RELEASE_LIVE_VERIFIED",
        "other_aeo_pages_untouched":207,
        "no_database_writes":True,"no_indexing_submissions":True,
        "original_release_valid":True,
        "exact_approved_pages":3,"live_http_200_pages":3,
    }
    out=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    a=next(x for x in out["actions"] if "/aeo/roofing/DFW" in x["url"])
    assert a["state"]=="verified"
    assert a["published_claim"] is True
    r["no_indexing_submissions"]=False
    bad=build_seo_action_lifecycle(w,d,buyer_journey=j,aeo_release=r,observed_at=NOW)
    a=next(x for x in bad["actions"] if "/aeo/roofing/DFW" in x["url"])
    assert a["published_claim"] is False


def test_google_malformed_or_wrong_counts_fail_closed():
    w,d,j,r=sources()
    d["indexed_verified"]=4
    with pytest.raises(SEOActionHeld,match="GOOGLE_INDEX_EVIDENCE_UNTRUSTED"):
        build_seo_action_lifecycle(w,d,observed_at=NOW)
    d["indexed_verified"]=3
    d["exact_url_states"]["https://evil.example/"]="GOOGLE_INDEXED_VERSION_VERIFIED"
    with pytest.raises(SEOActionHeld,match="GOOGLE_INDEX_EVIDENCE_UNTRUSTED"):
        build_seo_action_lifecycle(w,d,observed_at=NOW)


def verified_owner_sales(n=0):
    return {
      "status":"CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED" if n==0
       else "CANONICAL_SALES_ENQUIRIES_PRESENT_EXACT_READBACK_REQUIRED",
      "canonical_commercial_enquiries":n,
      "canonical_predictive_revenue_enquiries":0,
      "canonical_sales_acquisitions":n,
      "source_count_verified":True,
      "exact_crm_readback_verified":False,
      "specific_response_consent_current_verified":False,
      "individual_buyer_identity_verified":False,
      "outreach_authorized":False,
      "payments_authorized":False,
      "database_writes":False,
      "execution_authority":"none",
    }


def test_zero_sales_do_not_become_zero_organic_visits_or_aeo_leads():
    w,d,j,r=sources()
    out=build_seo_action_lifecycle(w,d,ops_sales=verified_owner_sales(0),observed_at=NOW)
    sales=out["canonical_sitewide_sales_evidence"]
    assert sales["sitewide_sales_acquisitions"]==0
    assert sales["verified_aeo_origin_enquiries"] is None
    assert sales["verified_organic_conversions"] is None
    assert sales["next_existing_owner_action"]=="IMPROVE_SEARCH_DISCOVERY_AND_WAIT_FOR_GENUINE_CONSENTED_ENQUIRY"
    assert out["verified_revenue"] is None


def test_positive_sales_require_exact_original_crm_receipt_review():
    w,d,j,r=sources()
    out=build_seo_action_lifecycle(w,d,ops_sales=verified_owner_sales(2),observed_at=NOW)
    evidence=out["canonical_sitewide_sales_evidence"]
    assert evidence["sitewide_sales_acquisitions"]==2
    assert evidence["exact_crm_enquiry_receipt_verified"] is False
    assert evidence["next_existing_owner_action"]=="REVIEW_EXISTING_CRM_OWNER_EXACT_REAL_ENQUIRY_LINEAGE"
    assert evidence["verified_aeo_origin_enquiries"] is None
    assert out["verified_revenue"] is None


def test_stale_or_unverified_ops_does_not_fabricate_zero_sales():
    w,d,j,r=sources()
    out=build_seo_action_lifecycle(w,d,ops_sales={"source_count_verified":False},observed_at=NOW)
    assert out["canonical_sitewide_sales_evidence"]["sitewide_sales_acquisitions"] is None
    forged=verified_owner_sales(1)
    forged["exact_crm_readback_verified"]=True
    with pytest.raises(SEOActionHeld,match="EXCEEDS_AUTHORITY"):
        build_seo_action_lifecycle(w,d,ops_sales=forged,observed_at=NOW)

def test_existing_daily_owner_picks_action_by_actual_google_state_not_repeat_publication(monkeypatch):
    from scripts import review_live_organic_buyer_journey_20261024 as journey_owner
    from empire_os import gtm_ops_first_sale_source as ops_owner
    from pathlib import Path
    w,d,j,r=sources()
    def documents(path):
        if path.name.startswith("google-index-"):return d
        if path.name.startswith("weekly_seo_growth_actions_"):return w
        return r
    monkeypatch.setattr(operator,"_trusted_json",documents)
    monkeypatch.setattr(operator,"_latest_weekly",lambda:Path("weekly_seo_growth_actions_2026-10-26.json"))
    monkeypatch.setattr(journey_owner,"review",lambda:j)
    monkeypatch.setattr(ops_owner,"observe_owner_ops_first_sale",
                        lambda root,now:verified_owner_sales(0))
    calls=[]
    def observe(url):
        calls.append(url)
        return {
          "status":"TESTED_READ_ONLY_NO_MUTATION",
          "http_status":200,"self_canonical":True,"html_content_type":True,
          "indexable":True,"website_changed":False,
        }
    result=operator.build_run(observed=NOW,get=observe)
    page=next(a for a in result["actions"] if a["url"]==BASE+"/commercial")
    assert page["state"]=="tested"
    assert page["index_status_first_party"]=="GOOGLE_HAS_NO_URL_RECORD"
    assert page["next_action"]==(
        "REVIEW_EXACT_GOOGLE_URL_INSPECTION_AND_ORIGINAL_CONTENT;"
        "MANUALLY_REQUEST_INDEXING_IF_ELIGIBLE"
    )
    assert result["canonical_sitewide_sales_evidence"]["sitewide_sales_acquisitions"]==0
    assert result["indexing_requests_submitted"]==0
    assert result["automated_publication_authorized"] is False
    assert result["outbound_sent"] is False


def test_indexed_existing_page_focuses_queries_not_republishing(monkeypatch):
    from scripts import review_live_organic_buyer_journey_20261024 as journey_owner
    from empire_os import gtm_ops_first_sale_source as ops_owner
    from pathlib import Path
    w,d,j,r=sources()
    w["actions"].append(action("/industries/roofing","LOW_VOLUME_OR_RECENT_PAGE_OBSERVATION","P3_MEASURE_AND_IMPROVE"))
    def documents(path):
        if path.name.startswith("google-index-"):return d
        if path.name.startswith("weekly_seo_growth_actions_"):return w
        return r
    monkeypatch.setattr(operator,"_trusted_json",documents)
    monkeypatch.setattr(operator,"_latest_weekly",lambda:Path("weekly_seo_growth_actions_2026-10-26.json"))
    monkeypatch.setattr(journey_owner,"review",lambda:j)
    monkeypatch.setattr(ops_owner,"observe_owner_ops_first_sale",
                        lambda root,now:verified_owner_sales(0))
    yes=lambda _:{"status":"TESTED_READ_ONLY_NO_MUTATION","http_status":200,
                  "self_canonical":True,"html_content_type":True,"indexable":True}
    result=operator.build_run(observed=NOW,get=yes)
    page=next(a for a in result["actions"] if a["url"]==BASE+"/industries/roofing")
    assert page["state"]=="tested"
    assert page["next_action"]=="MEASURE_FINAL_GSC_QUERIES_CTR_AND_GENUINE_CONSENTED_BUYER_OUTCOMES"
