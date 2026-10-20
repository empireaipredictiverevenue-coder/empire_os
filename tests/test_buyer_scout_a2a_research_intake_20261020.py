"""Read-only Buyer Scout owner acceptance tests for source-bound A2A evidence."""
from copy import deepcopy
import pytest
from empire_os.buyer_scout_a2a_research_intake_20261020 import stage_a2a_owner_research


def sources():
    websites={
        "schema_version":"empire.a2a.first_party_buyer_scout_evidence_handoff.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "verified_buyers":0,"canonical_buyer_records_created":0,
        "buyer_scout_owner_tasks_dispatched":0,"messages_sent":0,
        "scoped_review_packet_count":2,
        "scoped_review_packets":[{
            "public_company_website":"https://roofer.example/",
            "public_company_domain":"roofer.example",
            "target_market":"tampa, fl","target_sector":"roofing",
            "dispatch_status":"PREPARED_NOT_SUBMITTED",
            "verified_customer":False,"buyer_capacity_verified":False,
            "contact_authorized":False,"lead_created":False,
            "source_read_status":"HTTP_200",
            "observed_source_sha256":"a"*64,
            "buyer_scout_ticket_id":"2"*24,
            "ready_for_buyer_scout_owner_research_review":True,
        },{
            "public_company_website":"https://building.example/",
            "public_company_domain":"building.example",
            "target_market":"nyc","target_sector":"general_contractor",
            "dispatch_status":"PREPARED_NOT_SUBMITTED",
            "verified_customer":False,"buyer_capacity_verified":False,
            "contact_authorized":False,"lead_created":False,
            "source_read_status":"ROBOTS_POLICY_HOLD",
            "observed_source_sha256":None,
            "buyer_scout_ticket_id":"3"*24,
            "ready_for_buyer_scout_owner_research_review":False,
        }],
    }
    permits={
        "schema_version":"empire.a2a.official_permit_buyer_scout_owner_review.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "verified_hvac_lead_buyers":0,"owner_tasks_dispatched":0,
        "outbound_sent":0,"source_distribution_rights_unverified":True,
        "businesses_for_owner_review_count":1,
        "source_state":"OFFICIAL_SOURCE_OBSERVED_BUT_PERMIT_ISSUE_DATES_STALE",
        "public_contractor_businesses_for_owner_review":[{
            "company_name_hypothesis":"ACME MECHANICAL LLC",
            "business_name_review_id":"e"*24,
            "not_a_homeowner_lead":True,"not_a_qualified_lead_buyer":True,
            "contact_authorized":False,
        }],
    }
    scout={"mode":"OBSERVE","database_write_performed":False,
           "outbound_sent":False,"candidates":[]}
    searches={"schema_version":"empire.buyer_public_research_seeds.v1",
              "database_write_performed":False,"outbound_sent":False,
              "seeds":[{"website":"https://roofer.example/"}]}
    return websites,permits,scout,searches


def test_owner_read_reconciles_known_source_domain_without_crm_mutation():
    x=stage_a2a_owner_research(*sources())
    assert x["source_evidence_read_into_owner_workspace"]
    assert x["website_research_record_count"]==2
    assert x["website_source_records_eligible_for_further_owner_review"]==0
    assert x["website_records_overlapping_known_search_or_scout"]==1
    assert x["official_company_record_count"]==1
    assert x["owner_canonical_accepted_customer_records"]==0
    assert not x["canonical_crm_read_queried"]
    assert x["messages_sent"]==0
    assert not x["owner_receipt_cryptographic_signature_verified"]


def test_denied_source_not_ready_and_permit_not_a_sales_signal():
    x=stage_a2a_owner_research(*sources())
    assert x["website_research_records"][1]["research_status"]=="SOURCE_STALE_OR_HELD_NOT_CURRENT"
    assert x["official_company_research_records"][0]["actual_lead_purchase_demand_verified"] is False


def test_forged_buyer_promotion_rejected():
    cases=[
        lambda w,p,s,q:w.update({"verified_buyers":1}),
        lambda w,p,s,q:w["scoped_review_packets"][0].update({"contact_authorized":True}),
        lambda w,p,s,q:p.update({"owner_tasks_dispatched":2}),
        lambda w,p,s,q:s.update({"outbound_sent":True}),
        lambda w,p,s,q:q.update({"database_write_performed":True}),
    ]
    for mutate in cases:
        args=list(deepcopy(sources()))
        mutate(*args)
        with pytest.raises(ValueError):
            stage_a2a_owner_research(*args)


def test_untrusted_source_domain_and_wrong_location_are_rejected():
    args=list(sources())
    args[0]["scoped_review_packets"][0]["public_company_website"]="http://127.0.0.1/"
    with pytest.raises(ValueError):
        stage_a2a_owner_research(*args)
    args=list(sources())
    args[0]["scoped_review_packets"][0]["target_market"]="mars"
    with pytest.raises(ValueError):
        stage_a2a_owner_research(*args)


def test_duplicate_website_cannot_become_two_new_discoveries():
    args=list(sources())
    args[0]["scoped_review_packets"].append(deepcopy(args[0]["scoped_review_packets"][0]))
    args[0]["scoped_review_packet_count"]=3
    with pytest.raises(ValueError):
        stage_a2a_owner_research(*args)


def test_recent_label_without_individual_site_receipts_is_not_authoritative():
    w,p,c,q=sources()
    evidence={
        "schema_version":"empire.a2a.first_party_source_recovery_review.v1",
        "execution_authority":"NONE","new_verified_sales_leads":0,
        "outbound_sent":0,
        "source_state":"CACHED_FIRST_PARTY_PUBLIC_RESEARCH_WITHIN_7_DAYS",
    }
    # A recency label alone is insufficient: the original collector must
    # supply every site's matching URL, SHA, source and parser attestation.
    with pytest.raises(ValueError, match="SOURCE_BINDING_RECORD_SET_INCOMPLETE"):
        stage_a2a_owner_research(w,p,c,q,evidence)
    evidence["new_verified_sales_leads"]=1
    with pytest.raises(ValueError,match="UNTRUSTED_SOURCE_FRESHNESS"):
        stage_a2a_owner_research(w,p,c,q,evidence)
