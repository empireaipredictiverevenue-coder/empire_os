"""Stable owner verification queue for actual first-party observations.

No search results, raw webpage data, personal contacts, marketing messages,
consumer leads or verified buyers. Recreates the same IDs each hourly cycle.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

SCHEMA="empire.buyer_scout.source_verification_queue.v1"
INTAKE="empire.buyer_scout.a2a_owner_evidence_intake.v1"
MARKET_PRIORITY={"tampa, fl":1,"little rock, ar":2,"nyc":3}


def make_buyer_scout_source_verification_queue(
    readback: Mapping[str,Any],
)->dict[str,Any]:
    if (not isinstance(readback,Mapping)
            or readback.get("schema_version")!=INTAKE
            or readback.get("mode")!="OBSERVE"
            or readback.get("execution_authority")!="NONE"
            or readback.get("owner")!="existing_buyer_scout"
            or readback.get("owner_verified_buyers")!=0
            or readback.get("owner_live_purchase_demand_verified")!=0
            or readback.get("messages_sent")!=0
            or readback.get("canonical_crm_modified") is not False):
        raise ValueError("UNTRUSTED_BUYER_SCOUT_SOURCE_INTAKE")
    sites=readback.get("website_research_records")
    companies=readback.get("official_company_research_records")
    if (not isinstance(sites,list) or not isinstance(companies,list)
            or len(sites)>9 or len(companies)>40
            or readback.get("website_research_record_count")!=len(sites)
            or readback.get("official_company_record_count")!=len(companies)):
        raise ValueError("UNBOUNDED_OWNER_RESEARCH_INTAKE")

    seen=set()
    ready=[]
    held=[]
    for site in sites:
        if not isinstance(site,Mapping):
            raise ValueError("INVALID_WEBSITE_QUEUE_SOURCE")
        domain=site.get("company_domain")
        market=site.get("market")
        if (not isinstance(domain,str) or not 3<len(domain)<180
                or market not in MARKET_PRIORITY
                or site.get("buyer_identity_verified") is not False
                or site.get("live_buying_need_verified") is not False
                or site.get("contact_authorized") is not False
                or site.get("can_be_added_to_canonical_crm") is not False
                or domain in seen):
            raise ValueError("FAKE_BUYER_OR_DUPLICATE_SITE_QUEUE_RECORD")
        seen.add(domain)
        recent=site.get("research_status")=="PENDING_OWNER_COMPANY_AND_COMMERCIAL_NEED_VERIFICATION"
        if recent and (site.get("source_receipt_bound_to_independent_collector_readback") is not True
                       or not site.get("public_page_content_sha256")):
            raise ValueError("UNBOUND_SOURCE_QUEUED_AS_VERIFIED")
        ticket=site.get("a2a_ticket_id")
        task={
            "stable_review_task_id":sha256(("buyer_scout/site/"+domain).encode()).hexdigest()[:24],
            "source_kind":"INDEPENDENTLY_FETCHED_FIRST_PARTY_COMPANY_SITE",
            "public_company_domain":domain,
            "market":market,
            "sector":site.get("vertical"),
            "source_ticket_id":ticket,
            "source_content_sha256":site.get("public_page_content_sha256") if recent else None,
            "already_in_current_search_or_scout_snapshot":site.get("existing_search_or_scout_domain_overlap") is True,
            "requires_canonical_empiredb_duplicate_and_suppression_check":True,
            "requires_company_identity_and_local_trade_license_review":True,
            "requires_direct_buyer_purchase_intent_and_budget_evidence":True,
            "contact_allowed":False,
            "can_create_customer":False,
            "can_send_message":False,
            "commercial_claims_verified":False,
            "state":("OWNER_REVIEW_NOT_DELIVERED"
                     if recent else "SOURCE_HOLD_NO_RETRY_OR_PERSISTENCE"),
            "priority_group":"SITE_READABLE_FOUNDER_REVIEW" if recent else "SOURCE_RESTRICTION_HOLD",
        }
        (ready if recent else held).append(task)
    ready.sort(key=lambda x:(MARKET_PRIORITY[x["market"]],x["public_company_domain"]))
    held.sort(key=lambda x:(MARKET_PRIORITY[x["market"]],x["public_company_domain"]))
    historical=[]
    seenids=set()
    for company in companies:
        if not isinstance(company,Mapping):
            raise ValueError("INVALID_OFFICIAL_COMPANY_QUEUE_SOURCE")
        ident=company.get("public_business_review_id")
        name=company.get("company_name_hypothesis")
        if (not isinstance(ident,str) or len(ident)!=24
                or ident in seenids or not isinstance(name,str) or len(name)>90
                or company.get("actual_lead_purchase_demand_verified") is not False
                or company.get("individually_contactable") is not False
                or company.get("can_be_added_to_canonical_crm") is not False):
            raise ValueError("FAKE_OFFICIAL_BUYER_OR_DUPLICATE_NAME")
        seenids.add(ident)
        historical.append({
            "stable_review_task_id":sha256(("buyer_scout/permit/"+ident).encode()).hexdigest()[:24],
            "public_business_name_hypothesis":name,
            "public_business_review_id":ident,
            "market":"little rock, ar",
            "source_kind":"OFFICIAL_MECHANICAL_PERMIT_HISTORICAL_COMPANY_CONTEXT",
            "next_step":"VERIFY_BUSINESS_IDENTITY_VIA_LICENSE_AND_OWN_FIRST_PARTY_SITE",
            "permit_source_status":company.get("permit_date_status"),
            "not_a_current_project_demand_signal":True,
            "not_a_verified_buyer":True,
            "contact_allowed":False,
            "can_create_customer":False,
            "state":"HISTORICAL_CONTEXT_NOT_BUYER_PRIORITY",
        })
    historical.sort(key=lambda x:x["public_business_review_id"])
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE","execution_authority":"NONE",
        "owner":"existing_buyer_scout",
        "ready_first_party_verification_tasks":ready,
        "ready_first_party_verification_count":len(ready),
        "held_site_tasks":held,
        "held_site_count":len(held),
        "historical_official_company_context":historical,
        "historical_official_context_count":len(historical),
        "unique_site_review_ids":len(seen),
        "tasks_dispatched_to_live_buyer_scout":0,
        "canonical_empiredb_duplicate_checks_completed":0,
        "canonical_crm_records_created":0,
        "verified_revenue_buyers":0,
        "outbound_messages_sent":0,
        "search_api_results_persisted":False,
        "next_action":"EXISTING_BUYER_SCOUT_OWNER_VALIDATE_COMPANY_TERRITORY_CAPACITY_AND_SUPPRESSION",
    }
