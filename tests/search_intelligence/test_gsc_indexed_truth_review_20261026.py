from datetime import datetime, timezone, timedelta
import pytest
from empire_os.search_intelligence.gsc_indexed_truth_review import (
    IndexedTruthHeld,review_owned_google_index_evidence,
)
from empire_os.search_intelligence.owned_url_inspection import URLS, SITE

def index_packet():
    return dict(
        schema_version="empire.search.owned_gsc_index_inspection.v1",
        status="INDEXED_VERSION_INSPECTION_RECORDED",site=SITE,
        mode="OBSERVE", observed_at=datetime.now(timezone.utc).isoformat(),
        google_live_test_performed=False,google_indexing_request_sent=False,
        full_site_indexation_verified=False,production_database_writes=False,
        execution_authority="none", count=5,
        items=[dict(url=u,google_indexed_version_only=True,live_url_test_performed=False,
                    index_status_reported=True,verdict=("NEUTRAL" if i in (1,3) else "PASS"),
                    coverageState=("URL is unknown to Google" if i in (1,3) else "Submitted and indexed"),
                    googleCanonical=(None if i in (1,3) else u),
                    robotsTxtState=("ROBOTS_TXT_STATE_UNSPECIFIED" if i in (1,3) else "ALLOWED"),
                    pageFetchState=("PAGE_FETCH_STATE_UNSPECIFIED" if i in (1,3) else "SUCCESSFUL"),
                    indexingState=("INDEXING_STATE_UNSPECIFIED" if i in (1,3) else "INDEXING_ALLOWED"),
                    lastCrawlTime=(None if i in (1,3) else "2026-10-22T12:00:00Z"))
               for i,u in enumerate(URLS)],
    )
def crawl():
    return dict(schema_version="empire.seo.index_health.v1",mode="OBSERVE",
                status="HEALTHY_SIGNALS",origin="https://empire-ai.co.uk",
                google_indexed_pages_verified=False,website_changed=False,
                critical_issue_count=0,sitemap_incoming_anchor_counts={
                    URLS[0]:0, URLS[1]:12, URLS[2]:5, URLS[3]:3, URLS[4]:12
                })

def test_exact_two_unknown_three_indexed_keep_no_submission():
    r=review_owned_google_index_evidence(index_packet(),crawl())
    assert r["indexed_version_exact_verified"]==3
    assert r["google_url_unknown_count"]==2
    assert r["other_indexing_review_count"]==0
    assert r["scope_google_urls_checked"]==5
    assert r["full_site_indexation_verified"] is False
    assert r["automatic_index_submissions_authorized"] is False
    unknown=[x for x in r["findings"] if x["state"]=="GOOGLE_HAS_NO_URL_RECORD"]
    assert {x["url"] for x in unknown}=={URLS[1],URLS[3]}
    assert sorted(x["incoming_sitemap_page_links"] for x in unknown)==[3,12]
    assert all("REVIEW_ORIGINAL_PAGE_VALUE" in x["next_owner_action"] for x in unknown)
    assert all(x["ai_answer_citation_attested"] is False for x in r["findings"])

def test_failed_provider_canonical_not_counted_as_indexed():
    p=index_packet()
    p["items"][0]["googleCanonical"]="SAME_PROPERTY_OTHER_PATH"
    result=review_owned_google_index_evidence(p,crawl())
    assert result["indexed_version_exact_verified"]==2
    assert result["other_indexing_review_count"]==1

def test_missing_owned_link_defers_manual_inspection():
    r=crawl()
    r["sitemap_incoming_anchor_counts"].pop(URLS[1])
    out=review_owned_google_index_evidence(index_packet(),r)
    issue=next(x for x in out["findings"] if x["url"]==URLS[1])
    assert issue["next_owner_action"]=="REPAIR_OWNED_SITEMAP_AND_CONTEXTUAL_LINK_DISCOVERY_FIRST"

@pytest.mark.parametrize("edit",[
    {"site":"sc-domain:other.example"},
    {"count":4},
    {"google_live_test_performed":True},
    {"google_indexing_request_sent":True},
    {"production_database_writes":True},
    {"full_site_indexation_verified":True},
])
def test_provider_receipt_strict(edit):
    packet=index_packet();packet.update(edit)
    with pytest.raises(IndexedTruthHeld):
        review_owned_google_index_evidence(packet,crawl())

def test_extra_site_or_missing_result_not_misreported():
    p=index_packet();p["items"][2]["url"]="https://other.example/"
    with pytest.raises(IndexedTruthHeld):
        review_owned_google_index_evidence(p,crawl())

def test_expired_or_future_receipt_hold():
    for when in (datetime.now(timezone.utc)-timedelta(days=8),
                 datetime.now(timezone.utc)+timedelta(days=1)):
        p=index_packet();p["observed_at"]=when.isoformat()
        with pytest.raises(IndexedTruthHeld):
            review_owned_google_index_evidence(p,crawl())

def test_crawl_unavailable_held():
    c=crawl();c["status"]="SOURCE_UNAVAILABLE"
    with pytest.raises(IndexedTruthHeld):
        review_owned_google_index_evidence(index_packet(),c)
