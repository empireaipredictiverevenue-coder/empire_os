from datetime import datetime,timezone,timedelta
import pytest
from empire_os.search_intelligence.google_index_change_watch import (
    IndexChangeEvidenceHeld,summarize_verified_google_index,URLS,
)
GOOD="GOOGLE_INDEXED_VERSION_VERIFIED"
UNKNOWN="GOOGLE_HAS_NO_URL_RECORD"
OTHER="GOOGLE_INDEX_STATUS_NEEDS_REVIEW"
NOW=datetime(2026,10,26,18,0,tzinfo=timezone.utc)

def review():
    return {
        "schema_version":"empire.search.google_indexed_truth_review.v1",
        "mode":"OBSERVE",
        "source":"ORIGINAL_FIVE_URL_GSC_INSPECTION_PLUS_LIVE_CRAWL",
        "execution_authority":"none", "database_writes":False,
        "automatic_index_submissions_authorized":False,
        "full_site_indexation_verified":False,
        "scope_google_urls_checked":5,
        "provider_receipt_observed_at":NOW.isoformat(),
        "indexed_version_exact_verified":3, "google_url_unknown_count":2,
        "site_audit_critical_issue_count":0,
        "findings":[{
            "url":url,"state":UNKNOWN if i in (1,3) else GOOD,
            "external_search_rank_attested":False,
            "ai_answer_citation_attested":False,
            "lead_or_sale_attested":False,
        } for i,url in enumerate(URLS)],
    }

def test_first_day_baseline_three_two_no_omission():
    d=summarize_verified_google_index(review(),now=NOW)
    assert d["indexed_verified"]==3 and d["unknown_to_google"]==2
    assert d["change_count"]==0 and d["previous_watch_exists"] is False
    assert d["exact_url_states"][URLS[1]]==UNKNOWN
    assert d["google_indexing_submissions"]==0
    assert d["database_writes"] is False

def test_real_change_is_recorded_not_assumed():
    yesterday=summarize_verified_google_index(review(),now=NOW)
    next_day=review()
    next_day["provider_receipt_observed_at"]=(NOW+timedelta(days=1)).isoformat()
    next_day["findings"][3]["state"]=GOOD
    next_day["indexed_version_exact_verified"]=4
    next_day["google_url_unknown_count"]=1
    result=summarize_verified_google_index(next_day,yesterday,now=NOW+timedelta(days=1))
    assert result["change_count"]==1
    assert result["indexed_verified"]==4
    assert result["changes_since_previous_review"][0]["url"]==URLS[3]
    assert result["changes_since_previous_review"][0]["google_indexed_newly_verified"] is True

@pytest.mark.parametrize("edit",[
    {"google_indexing_submissions":1},
    {"database_writes":True},
    {"scope_checked":4},
    {"status":"FAKE"},
])
def test_prior_receipt_must_be_owned_exact(edit):
    prior=summarize_verified_google_index(review(),now=NOW)
    prior.update(edit)
    with pytest.raises(IndexChangeEvidenceHeld):
        summarize_verified_google_index(review(),prior,now=NOW)

@pytest.mark.parametrize("offset",[-38,1])
def test_stale_or_future_provider_receipt_cannot_assert_indexing(offset):
    r=review();r["provider_receipt_observed_at"]=(NOW+timedelta(hours=offset)).isoformat()
    with pytest.raises(IndexChangeEvidenceHeld):
        summarize_verified_google_index(r,now=NOW)

def test_wrong_order_or_missing_url_is_rejected():
    r=review();r["findings"][3]["url"]="https://example.com"
    with pytest.raises(IndexChangeEvidenceHeld):
        summarize_verified_google_index(r,now=NOW)

def test_invalid_rank_and_ai_claims_rejected():
    r=review();r["findings"][0]["ai_answer_citation_attested"]=True
    with pytest.raises(IndexChangeEvidenceHeld):
        summarize_verified_google_index(r,now=NOW)

def test_data_count_mismatch_rejected():
    r=review();r["google_url_unknown_count"]=0
    with pytest.raises(IndexChangeEvidenceHeld):
        summarize_verified_google_index(r,now=NOW)
