"""Per-website source binding and stable buyer-owner verification queue."""
from copy import deepcopy
from hashlib import sha256
import pytest

from tests.test_buyer_scout_a2a_research_intake_20261020 import sources
from empire_os.buyer_scout_a2a_research_intake_20261020 import stage_a2a_owner_research
from empire_os.buyer_scout_source_verification_queue_20261020 import (
    make_buyer_scout_source_verification_queue,
)


def packets():
    w,p,s,q=sources()
    w["scoped_review_packets"][0]["scrapling_structured_page_parsed"]=True
    readback={
        "schema_version":"empire.a2a.first_party_source_recovery_review.v1",
        "execution_authority":"NONE","new_verified_sales_leads":0,
        "outbound_sent":0,
        "source_state":"CACHED_FIRST_PARTY_PUBLIC_RESEARCH_WITHIN_7_DAYS",
        "sites_read":2,
        "source_records":[
            {
                "source_url":"https://roofer.example/",
                "market":"tampa, fl","sector":"roofing",
                "read_status":"HTTP_200",
                "source_sha256_if_http_200":"a"*64,
                "buyer_or_lead_verified":False,"contact_allowed":False,
                "scrapling_document_matches_collector_sha":True,
                "crawl4ai_digest_matches_collector":True,
                "scrapling_structured_page_parsed":True,
                "crawl4ai_offline_markdown_extracted":True,
            },
            {
                "source_url":"https://building.example/",
                "market":"nyc","sector":"general_contractor",
                "read_status":"ROBOTS_POLICY_HOLD",
                "source_sha256_if_http_200":None,
                "buyer_or_lead_verified":False,"contact_allowed":False,
                "scrapling_document_matches_collector_sha":False,
                "crawl4ai_digest_matches_collector":False,
                "scrapling_structured_page_parsed":False,
                "crawl4ai_offline_markdown_extracted":False,
            },
        ],
    }
    return w,p,s,q,readback


def test_exact_sha_and_parser_bound_queue():
    x=stage_a2a_owner_research(*packets())
    assert x["website_receipts_individually_bound_to_source"]==1
    assert x["website_source_records_eligible_for_further_owner_review"]==1
    queue=make_buyer_scout_source_verification_queue(x)
    assert queue["ready_first_party_verification_count"]==1
    assert queue["held_site_count"]==1
    assert queue["historical_official_context_count"]==1
    site=queue["ready_first_party_verification_tasks"][0]
    assert site["public_company_domain"]=="roofer.example"
    assert site["state"]=="OWNER_REVIEW_NOT_DELIVERED"
    assert site["requires_canonical_empiredb_duplicate_and_suppression_check"]
    assert site["requires_direct_buyer_purchase_intent_and_budget_evidence"]
    assert site["contact_allowed"] is False
    assert queue["verified_revenue_buyers"]==0
    assert queue["tasks_dispatched_to_live_buyer_scout"]==0
    assert queue["search_api_results_persisted"] is False


def test_same_inputs_have_same_stable_ids_and_no_duplicate_growth():
    v=stage_a2a_owner_research(*packets())
    a=make_buyer_scout_source_verification_queue(v)
    b=make_buyer_scout_source_verification_queue(v)
    assert a==b
    assert a["ready_first_party_verification_tasks"][0]["stable_review_task_id"]==b["ready_first_party_verification_tasks"][0]["stable_review_task_id"]


@pytest.mark.parametrize("change", [
    lambda a:a[4]["source_records"][0].update({"source_sha256_if_http_200":"b"*64}),
    lambda a:a[4]["source_records"][0].update({"market":"little rock, ar"}),
    lambda a:a[4]["source_records"][0].update({"contact_allowed":True}),
    lambda a:a[4]["source_records"][0].update({"scrapling_document_matches_collector_sha":False}),
    lambda a:a[4]["source_records"][0].update({"crawl4ai_digest_matches_collector":False}),
    lambda a:a[4]["source_records"][1].update({"source_sha256_if_http_200":"f"*64}),
    lambda a:a[4].update({"sites_read":1}),
    lambda a:a[4].update({"source_records":[a[4]["source_records"][0]]*2}),
    lambda a:a[0]["scoped_review_packets"][0].update({"source_read_status":"ROBOTS_POLICY_HOLD"}),
])
def test_untrusted_readback_never_promotes_website(change):
    values=list(deepcopy(packets()))
    change(values)
    with pytest.raises(ValueError,match="SOURCE_BINDING"):
        stage_a2a_owner_research(*values)


def test_no_original_receipt_cannot_be_queued_as_current():
    w,p,s,q,rb=packets()
    x=stage_a2a_owner_research(w,p,s,q)
    assert x["website_receipts_individually_bound_to_source"]==0
    queue=make_buyer_scout_source_verification_queue(x)
    assert queue["ready_first_party_verification_count"]==0
    assert queue["held_site_count"]==2


def test_queue_rejects_false_buyer_signal_and_duplicate_site():
    x=stage_a2a_owner_research(*packets())
    x["website_research_records"][0]["live_buying_need_verified"]=True
    with pytest.raises(ValueError,match="FAKE_BUYER"):
        make_buyer_scout_source_verification_queue(x)
    x=stage_a2a_owner_research(*packets())
    x["website_research_records"][1]["company_domain"]=x["website_research_records"][0]["company_domain"]
    with pytest.raises(ValueError,match="FAKE_BUYER"):
        make_buyer_scout_source_verification_queue(x)


def test_queue_prevents_current_demands_from_old_permit_hypotheses():
    x=stage_a2a_owner_research(*packets())
    item=make_buyer_scout_source_verification_queue(x)["historical_official_company_context"][0]
    assert item["not_a_current_project_demand_signal"]
    assert item["not_a_verified_buyer"]
    assert item["next_step"]=="VERIFY_BUSINESS_IDENTITY_VIA_LICENSE_AND_OWN_FIRST_PARTY_SITE"
