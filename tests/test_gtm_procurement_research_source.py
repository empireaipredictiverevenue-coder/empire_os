from datetime import datetime,timedelta,timezone
import copy
import json

from empire_os.gtm_procurement_research_source import (
    assess_procurement,observe_procurement,summarize_acquisition_truth,
)

NOW=datetime(2026,10,23,12,0,tzinfo=timezone.utc)


def packet():
    return {
        "schema_version":"empire.acquisition_official_procurement_review.v1",
        "mode":"OBSERVE","observed_at":NOW.isoformat(),
        "releases_inspected":10,
        "open_service_requirements_identified":1,
        "product_hypotheses":0,
        "canonical_qualified":0,
        "external_bid_submitted":False,
        "verified_customer_inquiry":False,
        "outbound_authorized":False,"crm_writes":False,
        "model_training_authorized":False,"verified_revenue":None,
        "records":[{
            "review_status":"NO_PAID_TRAFFIC_POLICY_HOLD",
            "candidate_product_code":None,
            "notice_url":"https://www.find-tender.service.gov.uk/Notice/096037-2026",
            "outbound_authorized":False,"contact_permission_cleared":False,
            "buyer_interest_in_empire_ai_verified":False,
            "product_fit_verified":False,
        }],
    }


def test_official_research_never_becomes_a_sales_intake():
    r=assess_procurement(packet(),now=NOW)
    assert r["current_research_receipt"]
    assert r["public_service_requests_observed"]==1
    assert r["verified_empire_ai_buyers"]==0
    assert not r["contact_authorized"]


def test_stale_and_malformed_promotion_fail_closed():
    mutations=[
        ("observed_at",(NOW-timedelta(days=2)).isoformat()),
        ("outbound_authorized",True),
        ("canonical_qualified",1),
        ("verified_customer_inquiry",True),
        ("external_bid_submitted",True),
        ("open_service_requirements_identified",2),
        ("product_hypotheses",1),
    ]
    for name,value in mutations:
        r=packet()
        r[name]=value
        assert not assess_procurement(r,now=NOW)["current_research_receipt"],name
    r=packet()
    r["records"][0]["notice_url"]="https://unrelated.example/Notice/096037-2026"
    assert not assess_procurement(r,now=NOW)["current_research_receipt"]


def test_sealed_research_receipt_read_and_symlink_refused(tmp_path):
    dest=tmp_path/"runtime/acquisition_research/official_procurement_requirements_latest.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(packet()))
    dest.chmod(0o600)
    assert observe_procurement(tmp_path,now=NOW)["current_research_receipt"]
    dest.chmod(0o644)
    assert not observe_procurement(tmp_path,now=NOW)["current_research_receipt"]
    dest.unlink()
    original=tmp_path/"source.json"
    original.write_text(json.dumps(packet()))
    dest.symlink_to(original)
    assert not observe_procurement(tmp_path,now=NOW)["current_research_receipt"]


def test_absent_canonical_ops_is_unknown_even_with_public_procurement():
    research=assess_procurement(packet(),now=NOW)
    r=summarize_acquisition_truth(
        {"source_count_verified":False,"canonical_sales_acquisitions":None},
        {"status":"HELD_OWNER_SOURCE_AND_CRM_RECONCILIATION_REQUIRED"},research)
    assert r["status"]=="FIRST_PARTY_OWNER_COUNT_UNVERIFIED"
    assert r["canonical_first_party_sales_acquisitions"] is None
    assert r["procurement_research"]["public_service_requests_observed"]==1
    assert r["contact_review_ready"] is False
    assert r["copy_briefs_generated"]==0


def test_canonical_zero_and_nonzero_both_hold_copy():
    research=assess_procurement(packet(),now=NOW)
    for count,expected in (
        (0,"FIRST_PARTY_NO_RECORDED_SALES_ENQUIRIES"),
        (1,"FIRST_PARTY_SALES_ENQUIRY_REQUIRES_EXACT_RECEIPT_REVIEW"),
    ):
        result=summarize_acquisition_truth(
            {"source_count_verified":True,"canonical_sales_acquisitions":count},
            {"status":"HELD_OWNER_SOURCE_AND_CRM_RECONCILIATION_REQUIRED"},
            research,
        )
        assert result["status"]==expected
        assert result["canonical_first_party_sales_acquisitions"]==count
        assert result["exact_customer_lineage_verified"] is False
        assert result["specific_current_response_consent_verified"] is False
        assert result["outbound_authorized"] is False


def test_existing_gtm_observer_includes_separate_evidence_lane(tmp_path):
    from empire_os.gtm_integration_observer import observe_gtm_integration
    research=tmp_path/"runtime/acquisition_research/official_procurement_requirements_latest.json"
    research.parent.mkdir(parents=True)
    research.write_text(json.dumps(packet()))
    research.chmod(0o600)
    r=observe_gtm_integration(tmp_path,now=NOW)
    link=r["acquisition_owner_truth"]
    assert link["status"]=="FIRST_PARTY_OWNER_COUNT_UNVERIFIED"
    assert link["procurement_research"]["public_service_requests_observed"]==1
    assert link["public_procurement_not_counted_as_first_party"] is True
    assert r["outreach_sent"] is False
    assert r["crm_write_performed"] is False
