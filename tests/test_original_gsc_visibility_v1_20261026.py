"""First-party Semrush-like keyword history: no fake ranks, demand or leads."""
from datetime import date,datetime,timezone
import json
from pathlib import Path
import stat
import pytest

from empire_os.search_intelligence.seo_visibility_v1 import (
    build_visibility_review,VisibilityEvidenceHeld
)
from scripts import review_original_gsc_visibility_v1_20261026 as run

BEFORE=(date(2026,10,3),date(2026,10,12))
AFTER=(date(2026,10,13),date(2026,10,22))
AS_OF=date(2026,10,26)
URL="https://empire-ai.co.uk"
def item(q,url,impressions,clicks=0,pos=8.5):
    return {"keys":[q,url],"impressions":impressions,"clicks":clicks,
        "position":pos}
def packet(rows,limit=250):
    return {"available":True,"source":"google_search_console",
        "site_url":"sc-domain:empire-ai.co.uk","limit":limit,"count":len(rows),"items":rows}

def samples():
    return (
        packet([
            item("empire ai",URL+"/",3),
            item("empire ai","https://www.empire-ai.co.uk/",6),
            item("antenna approvals",URL+"/aeo/antenna-install/EUG/",3,pos=91),
        ]),
        packet([
            item("empire ai",URL+"/",8,pos=9.1),
            item("antenna approvals",URL+"/aeo/antenna-install/EUG/",9,pos=76),
            item("antenna approvals",URL+"/aeo/antenna-install/FAR/",2,pos=74),
            item("how do i know which accounts in my tam are actually ready to buy right now",
                URL+"/aeo/accounting/TAM/",1,pos=8),
        ])
    )

def review(before=None,after=None):
    x,y=samples()
    return build_visibility_review(before or x,after or y,
        previous_window=BEFORE,current_window=AFTER,as_of=AS_OF)

def test_real_sample_distinguishes_brand_alias_and_different_aeo_metros():
    report=review()
    assert report["status"]=="REAL_GSC_QUERY_PAGE_VISIBILITY_OBSERVED"
    assert report["previous_sample"]["visible_query_page_impressions"]==12
    assert report["current_sample"]["visible_query_page_impressions"]==20
    assert report["current_sample"]["visible_query_page_clicks"]==0
    by_query={x["query"]:x for x in report["queries"]}
    assert by_query["antenna approvals"]["multiple_distinct_pages_for_query_in_sample"] is True
    assert by_query["antenna approvals"]["cannibalisation_verified"] is False
    assert by_query["empire ai"]["previous"]["exact_page_count"]==2
    assert by_query["empire ai"]["historical_hosts_same_path_in_previous_sample"] is True
    assert report["historical_www_apex_overlap_candidates"]==1
    assert report["current_www_apex_overlap_candidates"]==0
    assert by_query["empire ai"]["current"]["exact_page_count"]==1
    assert report["competitor_rankings_verified"] is False
    assert report["verified_revenue"] is None
    assert report["entire_site_traffic_coverage_verified"] is False

def test_high_intent_question_is_observed_not_assumed_buying_customer():
    report=review()
    first=report["queries"][0]
    assert first["commercial_topic_relevance_observed"] is True
    assert first["current"]["visible_impressions"]==1
    assert first["previous"]["visible_impressions"] is None
    assert first["historical_sample_status"]=="NEW_IN_CURRENT_SAMPLE"
    assert first["independent_live_serp_rank"] is None
    assert first["qualified_enquiries"] is None
    assert first["keyword_monthly_search_volume"] is None

@pytest.mark.parametrize("bad",[
    packet([item("a", "https://external.invalid/", 1)]),
    packet([item("a", URL+"/?token=secret",1)]),
    packet([item("a",URL+"/",3),item("a",URL+"/",1)]),
    packet([item("a",URL+"/",2,3)]),
    packet([item("a",URL+"/",1,pos=float("nan"))]),
    packet([item("a",URL+"/",1)],limit=1),
    {"available":False,"source":"google_search_console","site_url":"sc-domain:empire-ai.co.uk","count":0,"limit":250,"items":[]},
])
def test_malformed_untrusted_or_truncated_provider_packets_fail_closed(bad):
    with pytest.raises(VisibilityEvidenceHeld):
        review(before=bad)

def test_no_row_is_not_zero_demand():
    report=review(after=packet([]))
    assert report["missing_query_is_not_zero_search_demand"] is True
    assert all(x["current"]["visible_impressions"] is None for x in report["queries"])
    assert report["current_sample"]["returned_query_page_rows"]==0

def test_bounded_original_reader_twice_and_immutable_private_file(tmp_path):
    day=AS_OF
    called=[]
    def reader(start,end):
        called.append((start,end))
        return samples()[len(called)-1]
    root=tmp_path/"original_daily_owner"
    root.mkdir(mode=0o700)
    recorded=run.run(as_of=day,write=True,root=root,reader=reader)
    assert recorded["status"]=="ORIGINAL_GSC_VISIBILITY_MONITOR_RECORDED"
    assert len(called)==2
    target=Path(recorded["receipt"])
    assert stat.S_IMODE(target.stat().st_mode)==0o600
    assert json.loads(target.read_text())["observed_queries"]==3
    def never_reader(*args):
        pytest.fail("repeated GSC calls forbidden")
    again=run.run(as_of=day,write=True,root=root,reader=never_reader)
    assert again["status"]=="EXISTING_ORIGINAL_GSC_VISIBILITY_PRESERVED"
    assert again["new_gsc_calls"]==0
    assert target.is_file()

def test_original_daily_owner_hook_is_fail_soft(monkeypatch,capsys):
    from scripts import review_daily_original_google_index_20261026 as owner
    from scripts import review_original_seo_action_lifecycle_20261026 as lifecycle
    import sys
    monkeypatch.setattr(owner,"execute",lambda **kwargs:{
        "status":"ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED","scope_checked":5,
        "indexed_verified":3,"unknown_to_google":2})
    monkeypatch.setattr(lifecycle,"run",lambda **kwargs:{"status":"EXISTING_SEO_LIFECYCLE_RECEIPT_PRESERVED"})
    monkeypatch.setattr(run,"run",lambda **kwargs:{
        "status":"EXISTING_ORIGINAL_GSC_VISIBILITY_PRESERVED"})
    monkeypatch.setattr(sys,"argv",["seo-original-daily","--write-daily"])
    assert owner.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["seo_keyword_visibility"]["status"]=="EXISTING_ORIGINAL_GSC_VISIBILITY_PRESERVED"
    monkeypatch.setattr(run,"run",lambda **kwargs:(_ for _ in ()).throw(ValueError("held")))
    assert owner.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["seo_keyword_visibility"]["status"]=="SEO_KEYWORD_VISIBILITY_HELD_GOOGLE_WATCH_PRESERVED"
