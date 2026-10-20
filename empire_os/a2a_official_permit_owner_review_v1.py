"""Read back official government permit research into Buyer Scout's owner queue.

No public-property records, individual names, contact extraction, or official
dataset resale. Permit issuance is not evidence a company buys our leads.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
import re

from empire_os.a2a_official_mechanical_permit_research_v1 import SCHEMA as PERMIT_SCHEMA,_company,LAYER
from empire_os.a2a_owner_research_protocol_v1 import OUTBOX_SCHEMA

SCHEMA="empire.a2a.official_permit_buyer_scout_owner_review.v1"
_SHA=re.compile(r"^[0-9a-f]{64}$")
_ID=re.compile(r"^[a-f0-9]{24}$")


def permit_owner_review(
    permit: Mapping[str,Any] | None,
    owner_pickup: Mapping[str,Any],
    *, now: datetime | None=None,
) -> dict[str,Any]:
    clock=now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("OWNER_REVIEW_CLOCK_AWARE_REQUIRED")
    if (not isinstance(owner_pickup,Mapping)
            or owner_pickup.get("schema_version")!=OUTBOX_SCHEMA
            or owner_pickup.get("execution_authority")!="NONE"
            or owner_pickup.get("owner_dispatches")!=0):
        raise ValueError("UNTRUSTED_OWNER_PICKUP")
    pool=owner_pickup.get("pickup_by_owner")
    jobs=pool.get("buyer_scout") if isinstance(pool,Mapping) else None
    if not isinstance(jobs,list) or len(jobs)>10:
        raise ValueError("NO_BUYER_SCOUT_RESEARCH_OWNER")
    matched=[]
    for entry in jobs:
        if not isinstance(entry,Mapping):
            raise ValueError("INVALID_OWNER_HANDOFF_ENTRY")
        req=entry.get("research_request")
        if (isinstance(req,Mapping)
                and req.get("market")=="little rock, ar"
                and req.get("sector")=="hvac"
                and entry.get("execution_state")=="PICKUP_AVAILABLE_NOT_DELIVERED"):
            matched.append(entry)
    if len(matched)!=1:
        raise ValueError("OWNER_TARGET_MISSING_OR_AMBIGUOUS")
    ticket=matched[0]
    if permit is None:
        return _hold(ticket,"OFFICIAL_SOURCE_NOT_COLLECTED")
    if (not isinstance(permit,Mapping)
            or permit.get("schema_version")!=PERMIT_SCHEMA
            or permit.get("mode")!="OBSERVE"
            or permit.get("execution_authority")!="NONE"
            or permit.get("market")!="little rock, ar"
            or permit.get("sector")!="hvac"
            or permit.get("source_layer_url")!=LAYER
            or permit.get("verified_local_hvac_lead_buyers")!=0
            or permit.get("crm_writes")!=0
            or permit.get("outbound_messages")!=0
            or permit.get("source_terms_and_commercial_redistribution_cleared") is not False
            or permit.get("personal_contacts_or_property_addresses_exported") is not False):
        raise ValueError("UNTRUSTED_PERMIT_OWNER_SOURCE")
    stamp=permit.get("source_response_observed_at_utc")
    if not isinstance(stamp,str):
        raise ValueError("PERMIT_RECEIPT_TIMESTAMP_MISSING")
    t=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    if t.tzinfo is None or t > clock+timedelta(minutes=5):
        raise ValueError("PERMIT_SOURCE_TIMESTAMP_INVALID")
    digest=permit.get("source_http_body_sha256")
    if not isinstance(digest,str) or not _SHA.fullmatch(digest):
        raise ValueError("PERMIT_SOURCE_SHA_REQUIRED")
    rows=permit.get("contractor_company_research_records")
    if not isinstance(rows,list) or len(rows)>40 or permit.get("conservative_business_names_retained") != len(rows):
        raise ValueError("UNBOUNDED_PERMIT_COMPANY_LIST")
    results=[]
    seen=set()
    for row in rows:
        if not isinstance(row,Mapping):
            raise ValueError("INVALID_PERMIT_COMPANY_ROW")
        name=row.get("public_contractor_business_name_for_owner_review")
        identity=row.get("business_name_review_id")
        if (_company(name)!=name or not isinstance(identity,str) or not _ID.fullmatch(identity)
                or identity in seen
                or row.get("business_identity_independently_verified") is not False
                or row.get("lead_purchase_intent_verified") is not False
                or row.get("customer_contact_authorized") is not False
                or row.get("contact_authorized") is True
                or row.get("buyer_identity_verified") is True
                or row.get("buyer_budget_verified") is True):
            raise ValueError("UNVERIFIED_OR_DUPLICATE_PERMIT_BUSINESS")
        seen.add(identity)
        identifiers=row.get("official_permit_object_ids")
        if (not isinstance(identifiers,list) or not 1<=len(identifiers)<=40
                or any(type(v) is not int or v<=0 for v in identifiers)):
            raise ValueError("UNVERIFIABLE_PERMIT_ROW_IDS")
        results.append({
            "company_name_hypothesis":name,
            "business_name_review_id":identity,
            "official_source_url":permit["source_layer_url"],
            "permit_record_count_observed":len(identifiers),
            "permit_record_source_ids":identifiers,
            "buyer_scout_ticket_id":ticket["ticket_id"],
            "needs_canonical_company_identity_match":True,
            "needs_business_site_and_license_validation":True,
            "needs_territory_and_buying_capacity_confirmation":True,
            "needs_existing_crm_duplicate_and_suppression_checks":True,
            "not_a_homeowner_lead":True,
            "not_a_qualified_lead_buyer":True,
            "contact_authorized":False,
            "status":"PUBLIC_PERMIT_COMPANY_RESEARCH_NOT_SUBMITTED",
        })
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","execution_authority":"NONE",
        "source_state":("SOURCE_RESPONSE_RECENT_WITH_RECENT_ISSUED_PERMITS"
                        if permit.get("source_fresh_within_14_days") is True
                        else "OFFICIAL_SOURCE_OBSERVED_BUT_PERMIT_ISSUE_DATES_STALE"),
        "source_body_sha256":digest,
        "source_response_observed_at_utc":stamp,
        "buyer_scout_ticket_id":ticket["ticket_id"],
        "source_records_scanned":permit["source_records_scanned"],
        "source_may_be_truncated":permit.get("provider_response_may_be_truncated") is True,
        "public_contractor_businesses_for_owner_review":results,
        "businesses_for_owner_review_count":len(results),
        "all_permit_records_are_context_not_verified_buyers":True,
        "source_distribution_rights_unverified":True,
        "owner_inbox_published":False,
        "owner_tasks_dispatched":0,
        "verified_hvac_lead_buyers":0,
        "new_customer_records":0,
        "outbound_sent":0,
    }


def _hold(ticket: Mapping[str,Any],reason: str)->dict[str,Any]:
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","execution_authority":"NONE",
        "source_state":reason,"source_body_sha256":None,
        "source_records_scanned":None,
        "buyer_scout_ticket_id":ticket["ticket_id"],
        "public_contractor_businesses_for_owner_review":[],
        "businesses_for_owner_review_count":None,
        "owner_inbox_published":False,
        "owner_tasks_dispatched":0,
        "verified_hvac_lead_buyers":0,
        "new_customer_records":0,
        "outbound_sent":0,
    }
