"""Demand-led first-payer research, separate from permit and contractor work.

Original public adverts are *requests*, not verified companies, accepted work,
contact consent or commercial events. Fail closed on modified scopes/prices,
invented readiness or cross-website legal-identity joins.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlparse
import re

from empire_os.executive_buyer_capacity_review import review_buyer_capacity

SOURCE_SCHEMA="empire.jev.direct_b2b_buyer_requests.source.v1"
SCHEMA="empire.jev.direct_b2b_buying_need_review.v1"
KNOWN={
    "freelancer_40778550":(
        "PUBLIC_PLATFORM_JOB","DIRECT_WORDPRESS_WEB_DEVELOPMENT",
        "PUBLIC_ADVERTISED_BUDGET_AUD_250_TO_750",
        "https://www.freelancer.com/projects/web-design/vibrant-car-yard-web-site",
        "2026-10-22","PLATFORM_SCOPED_APPLICATION_OWNER_REVIEW"),
    "reddit_wp_1woeuix":(
        "PUBLIC_HIRING_POST","DIRECT_WEBSITE_BUILD_SUBCONTRACT",
        "NO_FIXED_BUYER_PRICE_PUBLIC",
        "https://www.reddit.com/r/wordpressjobs/comments/1woeuix/hiring_web_designerdeveloper_for_recurring_local/",
        "2026-09-23","WEB_BUILD_PORTFOLIO_AND_AGENCY_IDENTITY_GATE"),
    "reddit_legal_1x46cup":(
        "PUBLIC_HIRING_POST","LEGAL_INDUSTRY_QUALIFIED_LEADS",
        "NO_ACCEPTANCE_OR_PAYOUT_DEFINED",
        "https://www.reddit.com/r/LeadGenMarketplace/comments/1x46cup/we_are_looking_for_lead_generators/",
        "2026-10-12","REGULATED_LEGAL_LEAD_RIGHTS_AND_CAPACITY_HOLD"),
    "reddit_agency_1w7wwwe":(
        "PUBLIC_HIRING_POST","QUALIFIED_AGENCY_LEAD_GEN_PARTNER",
        "COMMISSION_TERMS_UNVERIFIED",
        "https://www.reddit.com/r/LeadGenMarketplace/comments/1w7wwwe/looking_for_a_lead_generation_partner/",
        "2026-09-05","ORIGINAL_PLATFORM_RIGHTS_AND_BUYBOX_HOLD"),
    "reddit_old_1uk1vw1":(
        "PUBLIC_HIRING_POST","FIFTY_ACCEPTED_WEB_STATUS_LEADS",
        "CONDITIONAL_USD_150_PER_FIFTY_PLUS_TEN_PERCENT_PAID_CLOSE",
        "https://www.reddit.com/r/LeadGenMarketplace/comments/1uk1vw1/need_a_leads_gen_for_my_startup_web_agency_150/",
        "2026-06-30","STALE_LOW_UNIT_ECONOMICS_RECONFIRMATION_HOLD"),
}
EXPECTED_CLASSIFICATION={
    "freelancer_40778550":("AU","auto_retail","WORDPRESS_VEHICLE_INVENTORY_AND_REPAIR_BOOKING"),
    "reddit_wp_1woeuix":("US","local_service_web_agency","RECURRING_WORDPRESS_4_TO_6_PAGE_SITES_AND_HANDOVER"),
    "reddit_legal_1x46cup":("US","legal","BUDGET_FRIENDLY_US_LEGAL_LEAD_GENERATORS"),
    "reddit_agency_1w7wwwe":("US","web_agency","LINKEDIN_UPWORK_FREELANCER_SOURCE_RESEARCH_REVENUE_SHARE"),
    "reddit_old_1uk1vw1":("US","web_agency","FIFTY_ORIGINAL_RIGHTS_CLEARED_WEBSITE_STATUS_LEADS"),
}
LANE_PRIORITY={
    "PLATFORM_SCOPED_APPLICATION_OWNER_REVIEW":0,
    "WEB_BUILD_PORTFOLIO_AND_AGENCY_IDENTITY_GATE":1,
    "REGULATED_LEGAL_LEAD_RIGHTS_AND_CAPACITY_HOLD":2,
    "ORIGINAL_PLATFORM_RIGHTS_AND_BUYBOX_HOLD":3,
    "STALE_LOW_UNIT_ECONOMICS_RECONFIRMATION_HOLD":4,
}
TASKS={
 "PLATFORM_SCOPED_APPLICATION_OWNER_REVIEW":[
     "CONFIRM_PLATFORM_PROJECT_STILL_OPEN_AND_CLIENT_PAYMENT_ACCOUNT",
     "DEMONSTRATE_REAL_DELIVERABLE_WORDPRESS_WORK_AND_INVENTORY_BOOKING_TEST",
     "REVIEW_PAID_SCOPE_MILESTONES_SOURCE_ASSETS_AND_HANDOVER",
     "AGREE_PLATFORM_MILESTONE_PAYMENT_TERMS_BEFORE_ANY_BID",
 ],
 "WEB_BUILD_PORTFOLIO_AND_AGENCY_IDENTITY_GATE":[
     "CONFIRM_ORIGINAL_HIRING_REQUEST_STILL_OPEN",
     "OBTAIN_VOLUNTARY_LEGAL_AGENCY_IDENTITY_AND_BUDGET",
     "SHOW_RELEVANT_DELIVERED_WORDPRESS_PORTFOLIO_WITHOUT_INVENTED_CASE_STUDIES",
     "AGREE_CLIENT_OWNERSHIP_HOSTING_RIGHTS_MAINTENANCE_AND_PAYMENT",
 ],
 "REGULATED_LEGAL_LEAD_RIGHTS_AND_CAPACITY_HOLD":[
     "CONFIRM_SPECIFIC_LEGAL_VERTICAL_JURISDICTION_AND_CURRENT_BUYBOX",
     "VERIFY_FIRST_PARTY_OPT_IN_PROVENANCE_LEAD_ROUTING_RIGHTS_AND_RESTRICTIONS",
     "AGREE_ACCEPTANCE_DELIVERY_REFUNDS_AND_WRITTEN_PAYOUT_TERMS",
 ],
 "ORIGINAL_PLATFORM_RIGHTS_AND_BUYBOX_HOLD":[
     "CONFIRM_COMPANY_AUTHORITY_CURRENT_LEAD_REQUIREMENT_AND_BUYING_BUDGET",
     "REVIEW_LINKEDIN_AND_JOB_PLATFORM_DATA_REUSE_RULES_BEFORE_ANY_COLLECTION",
     "CONFIRM_ACCEPTED_APPOINTMENT_CRITERIA_PAYMENT_AND_ORGANIC_ONLY_SUPPLY",
 ],
 "STALE_LOW_UNIT_ECONOMICS_RECONFIRMATION_HOLD":[
     "CONFIRM_DIRECT_LEGAL_BUYER_IDENTITY_AND_REQUIREMENT_STILL_OPEN",
     "REVIEW_WRITTEN_50_ACCEPTED_RECORD_RULES_PAYMENT_AND_SOURCE_LICENSES",
     "PROVE_WEBSITE_STATUS_AND_HUMAN_QA_COSTS_WITH_NO_PERSON_CONTACT_EXPORT",
 ],
}


def review_direct_buyer_requests(
    source:Mapping[str,Any],*,as_of:datetime,buyer_capacity:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("must supply exact aware review time")
    now=as_of.astimezone(timezone.utc)
    day=now.date()
    if (not isinstance(source,Mapping)
        or source.get("schema_version")!=SOURCE_SCHEMA
        or source.get("as_of_utc")!=day.isoformat()
        or source.get("status")!="EXTERNAL_ORIGINAL_POSTS_OBSERVED_OWNER_REVIEW_ONLY"
        or source.get("public_pages_checked_in_web_review") is not True
        or source.get("lawful_use_of_republished_content_not_verified") is not True
        or source.get("legal_buyer_identity_verified") is not False
        or source.get("commercial_terms_signed") is not False
        or source.get("automated_outbound_authorized") is not False):
        raise ValueError("untrusted original demand source contract")
    records=source.get("source_posts")
    if not isinstance(records,list) or len(records)!=len(KNOWN):
        raise ValueError("exact pinned buyer-request source set required")
    seen=set()
    out=[]
    for row in records:
        if not isinstance(row,Mapping):
            raise ValueError("malformed original web observation")
        rid=row.get("id")
        if rid not in KNOWN or rid in seen:
            raise ValueError("unknown or duplicate public source")
        seen.add(rid)
        kind,need,price,url,posted,lane=KNOWN[rid]
        parsed=urlparse(row.get("url",""))
        if (parsed.scheme!="https" or parsed.netloc not in (
              "www.reddit.com","www.freelancer.com")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or (row.get("source_kind"),row.get("need"),row.get("priced"),
                row.get("url"),row.get("posted_date"))!=(kind,need,price,url,posted)
            or (row.get("market"),row.get("sector"),row.get("scope"))!=EXPECTED_CLASSIFICATION[rid]
            or row.get("observed_date")!=day.isoformat()
            or row.get("first_party_explicit_need") is not True
            or row.get("fulfilment_capability_verified") is not False
            or row.get("legal_company_id_verified") is not False
            or row.get("payment_proof") not in (
                "UNVERIFIED",
                "PLATFORM_PAYMENT_METHOD_VERIFIED_BADGE_NOT_CONTRACT")
            or (rid=="freelancer_40778550") != (
                row.get("payment_proof")=="PLATFORM_PAYMENT_METHOD_VERIFIED_BADGE_NOT_CONTRACT")):
            raise ValueError("original source, price or identity forged")
        age=(day-date.fromisoformat(posted)).days
        if age<0 or age>365:
            raise ValueError("invalid original public posting age")
        if row.get("source_kind")=="PUBLIC_PLATFORM_JOB" and row.get("original_platform_bid_only") is not True:
            raise ValueError("platform bid requires platform channel")
        if row.get("source_kind")=="PUBLIC_HIRING_POST" and row.get("original_platform_bid_only") is not False:
            raise ValueError("unexpected platform authority")
        out.append({
            "case_id":rid,
            "original_request_url":url,
            "source_kind":kind,
            "posted_date":posted,
            "age_days_at_review":age,
            "business_need_code":need,
            "market":row["market"],
            "sector":row["sector"],
            "service_scope_code":row["scope"],
            "original_posted_price_code":price,
            "research_lane":lane,
            "next_existing_owner_checks":TASKS[lane],
            "source_author_explicitly_requested_help":True,
            "legal_buyer_company_verified":False,
            "current_open_order_verified":False,
            "specific_business_buybox_verified":False,
            "empire_technical_fulfilment_proven":False,
            "purchase_or_payment_contract_verified":False,
            "licence_consent_and_crm_suppression_verified":False,
            "qualified_pipeline_revenue":False,
            "applicant_contact_or_bid_approved":False,
        })
    if seen!=set(KNOWN):
        raise ValueError("missing exact distinct public post")
    out.sort(key=lambda r:(LANE_PRIORITY[r["research_lane"]],r["case_id"]))
    # The existing Buyer Scout reader confirms aggregate status but cannot
    # prove individual first-party counterparties or project-winning bids.
    capacity=review_buyer_capacity(buyer_capacity,as_of=now)
    if (capacity["execution_authority"]!="none"
        or capacity["specific_buybox_verified"] is not False
        or capacity["lead_delivery_authorized"] is not False):
        raise ValueError("buyer aggregate cannot promote a website request")
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"EXPLICIT_B2B_SERVICE_REQUESTS_NONCONTACT_OWNER_REVIEW",
        "review_date_utc":day.isoformat(),
        "distinct_public_purchase_need_posts":len(out),
        "verified_business_buyers":0,
        "officially_awarded_business_orders":0,
        "buyer_capacity_aggregate_status":capacity["status"],
        "cases":out,
        "agency_june_post_not_recategorized_as_new_buyer":True,
        "government_work_procurements_excluded":True,
        "historical_empiredb_contacts_used":0,
        "promised_organic_leads":0,
        "paid_customer_acceptance_verified":False,
        "live_bids_submitted":0,
        "crm_writes":False,
        "outbound_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }
