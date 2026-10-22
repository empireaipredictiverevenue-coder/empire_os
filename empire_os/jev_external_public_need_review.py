"""Review original public B2B need observations without inventing buyers.

Extends EmpireOS existing Jev/Intent Brain research owner workflow: structured
web-reviewed source pointers only, not canonical identity, outreach tickets,
unlicensed original-text extraction or contact lists. Does not bypass
independent original-source, Business Identity, Buyer Scout or CRM gates.
"""
from __future__ import annotations
from collections import Counter
from datetime import date
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit
import re

INPUT_SCHEMA="empire.jev.external_public_b2b_need_candidates.v1"
SCHEMA="empire.jev.external_public_need_review.v1"
ALLOWED_MARKETS=frozenset(("US","GB"))
ALLOWED_SECTORS=frozenset(("roofing","hvac","general_contractor","web_agency"))
REQUEST_TYPES=frozenset((
    "EXPLICIT_VENDOR_SEARCH","CONSIDERING_OUTSIDE_EXPERT",
    "DISCUSSING_COMMERCIAL_PAIN","ASKING_INDUSTRY_ADVICE",
    "MARKET_DISCUSSION","ASKING_MARKETING_ASSISTANCE",
    "EXPLICIT_SUPPLIER_SEARCH","ASKING_PROVIDER_ADVICE",
))
EXPLICIT=frozenset(("EXPLICIT_VENDOR_SEARCH","EXPLICIT_SUPPLIER_SEARCH"))
CLASSIC=frozenset(("CONSIDERING_OUTSIDE_EXPERT","DISCUSSING_COMMERCIAL_PAIN"))
HOLD_RISKS=frozenset((
    "PAYMENT_AND_CAPABILITY_PROOF","NOT_EXPLICIT_VENDOR_HIRE",
    "EXISTING_VENDOR_RELATIONSHIP","NOT_AN_IDENTIFIED_PURCHASER",
    "NO_FIRST_PARTY_COMPANY_AUTHORITY","CONTACT_DATA_RIGHTS_AND_PROVENANCE",
    "NO_COMPANY_BUYING_AUTHORITY",
))
KNOWN_IDS=frozenset((
    "1wciats","1uzetzd","1wirhh8","1uwpnd6",
    "1wzjygh","1shjssl","1uk1vw1","1v5hfs1",
))
MAX_ROWS=12
# Exact public source classification established from reviewed original
# web-page observations. No injected role, market, date or request escalation.
PINNED={
    "1wciats":("US","roofing","2026-09-10","EXPLICIT_VENDOR_SEARCH","PAYMENT_AND_CAPABILITY_PROOF"),
    "1uzetzd":("US","roofing","2026-07-17","CONSIDERING_OUTSIDE_EXPERT","NOT_EXPLICIT_VENDOR_HIRE"),
    "1wirhh8":("GB","roofing","2026-09-17","DISCUSSING_COMMERCIAL_PAIN","EXISTING_VENDOR_RELATIONSHIP"),
    "1uwpnd6":("US","roofing","2026-07-14","ASKING_INDUSTRY_ADVICE","NOT_EXPLICIT_VENDOR_HIRE"),
    "1wzjygh":("US","general_contractor","2026-10-07","MARKET_DISCUSSION","NOT_AN_IDENTIFIED_PURCHASER"),
    "1shjssl":("US","hvac","2026-04-10","ASKING_MARKETING_ASSISTANCE","NO_FIRST_PARTY_COMPANY_AUTHORITY"),
    "1uk1vw1":("US","web_agency","2026-06-30","EXPLICIT_SUPPLIER_SEARCH","CONTACT_DATA_RIGHTS_AND_PROVENANCE"),
    "1v5hfs1":("US","roofing","2026-07-24","ASKING_PROVIDER_ADVICE","NO_COMPANY_BUYING_AUTHORITY"),
}


def review_public_b2b_needs(source:Mapping[str,Any], *,
                            as_of:date)->dict[str,Any]:
    if type(as_of) is not date:
        raise ValueError("exact review date required")
    if (not isinstance(source,Mapping)
        or source.get("schema_version")!=INPUT_SCHEMA
        or source.get("status")!="ORIGINAL_PUBLIC_WEB_PAGE_OBSERVATIONS_OWNER_VALIDATION_PENDING"
        or source.get("source_method")!="public_original_page_opened_in_web_review_not_authenticated_server_ingest"
        or source.get("server_api_original_fetch_success") is not False
        or source.get("source_license_verified") is not False
        or source.get("original_business_identity_verified") is not False
        or source.get("consent_to_contact_verified") is not False
        or source.get("automatic_research_import_authorized") is not False
        or source.get("crm_writes") is not False
        or source.get("outbound_sent")!=0):
        raise ValueError("public-page discovery record cannot assert authority")
    if source.get("as_of_utc")!=as_of.isoformat():
        raise ValueError("dated manual review source must match the review date")
    data=source.get("rows")
    if not isinstance(data,list) or not 1<=len(data)<=MAX_ROWS:
        raise ValueError("small fixed human-reviewed set required")
    ids=set()
    results=[]
    for row in data:
        if not isinstance(row,Mapping):
            raise ValueError("invalid public evidence row")
        rid=row.get("id")
        source_url=row.get("source_url")
        if not isinstance(source_url,str) or len(source_url)>300:
            raise ValueError("original public Reddit URL required")
        u=urlsplit(source_url)
        m=re.fullmatch(r"/r/([A-Za-z0-9_]+)/comments/([a-z0-9]{6,8})/[a-z0-9_]+/",u.path)
        if (not m or u.scheme!="https"
            or u.netloc!="www.reddit.com"
            or u.query or u.fragment or u.username or u.password
            or rid not in KNOWN_IDS or rid!=m.group(2)
            or rid in ids or row.get("subreddit")!=m.group(1)
            or row.get("market") not in ALLOWED_MARKETS
            or row.get("sector") not in ALLOWED_SECTORS
            or row.get("request") not in REQUEST_TYPES
            or row.get("risk") not in HOLD_RISKS
            or (row.get("market"),row.get("sector"),row.get("date"),
                row.get("request"),row.get("risk"))!=PINNED[rid]
            or row.get("verified_business_name") is not False
            or row.get("actual_service_purchase_verified") is not False):
            raise ValueError("source, scope, identity, or public URL mismatch")
        ids.add(rid)
        try:
            posted=date.fromisoformat(row["date"])
        except (KeyError,TypeError,ValueError):
            raise ValueError("source post date missing") from None
        age=(as_of-posted).days
        if not 0<=age<=730:
            raise ValueError("future or excessively old original source")
        # Exact public claim is a hypothesis; never infer a named business
        # from a handle, nor treat an explicit solicitation as consent to DM.
        direct=row["request"] in EXPLICIT
        considered=row["request"] in CLASSIC
        if direct:
            lane="ORIGINAL_BUSINESS_AND_TERMS_REVIEW"
        elif considered:
            lane="ORIGINAL_COMPANY_NEED_AND_SOLUTION_FIT_REVIEW"
        else:
            lane="PUBLIC_MARKET_RESEARCH_ONLY"
        if row["risk"] in (
            "NO_FIRST_PARTY_COMPANY_AUTHORITY",
            "NO_COMPANY_BUYING_AUTHORITY",
            "NOT_AN_IDENTIFIED_PURCHASER",
        ):
            lane="ROLE_OR_BUYER_AUTHORITY_HOLD"
        if age>90 and lane=="ORIGINAL_BUSINESS_AND_TERMS_REVIEW":
            lane="STALE_PURCHASE_REQUEST_REVALIDATION_REQUIRED"
        risk_terms=(row["risk"] in (
            "PAYMENT_AND_CAPABILITY_PROOF","CONTACT_DATA_RIGHTS_AND_PROVENANCE",
        ))
        results.append({
            "public_post_id":rid,
            "source_url":source_url,
            "source_date":posted.isoformat(),
            "source_age_days":age,
            "market":row["market"],
            "region":row["region"] if type(row.get("region")) is str
                      and len(row["region"])<=80 else "UNVERIFIED",
            "sector":row["sector"],
            "stated_need_code":row["need"],
            "stated_commercial_request":row["request"],
            "proposed_review_lane":lane,
            "payment_or_data_rights_risk_review":risk_terms,
            "original_business_identity_verified":False,
            "buyer_authority_verified":False,
            "current_demand_confirmed":False,
            "valid_consent_to_contact_verified":False,
            "existing_crm_relationship_and_suppression_checked":False,
            "commercial_terms_verified":False,
            "qualified_revenue_opportunity":False,
            "recommended_research_owner":"existing_jev_intent_research_owner",
            "buyer_scout_promotion_authorized":False,
            "crm_insertion_authorized":False,
            "outreach_authorized":False,
        })
    if ids!=KNOWN_IDS:
        raise ValueError("external public review requires the exact pinned source set")
    lane_order={
        "ORIGINAL_BUSINESS_AND_TERMS_REVIEW":0,
        "ORIGINAL_COMPANY_NEED_AND_SOLUTION_FIT_REVIEW":1,
        "STALE_PURCHASE_REQUEST_REVALIDATION_REQUIRED":2,
        "ROLE_OR_BUYER_AUTHORITY_HOLD":3,
        "PUBLIC_MARKET_RESEARCH_ONLY":4,
    }
    results.sort(key=lambda x:(lane_order[x["proposed_review_lane"]],
                              x["source_age_days"],x["public_post_id"]))
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"PUBLIC_B2B_NEED_SOURCE_CANDIDATES_RESEARCH_OWNER_REVIEW_ONLY",
        "review_date":as_of.isoformat(),
        "original_source_pages_observed_in_web_review":len(results),
        "original_pages_readable_by_server_api":False,
        "verified_legal_business_buyers":0,
        "direct_claims_of_provider_search":sum(x["stated_commercial_request"] in EXPLICIT
                                               for x in results),
        "markets":dict(sorted(Counter(x["market"] for x in results).items())),
        "lanes":dict(sorted(Counter(x["proposed_review_lane"] for x in results).items())),
        "items":results,
        "existing_jev_client_pain_or_buyer_scout_owner_approval_required":True,
        "historical_empiredb_contacts_matched":0,
        "personal_contacts_enriched":0,
        "b2b_lead_sales_ready":0,
        "approved_outbound_messages":0,
        "model_calls":0,
        "crm_writes":False,
        "execution_authority":"none",
    }
