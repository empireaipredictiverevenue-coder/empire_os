"""Non-allocating per-lead source-owner duplicate and consent research audit.

Consumes only an *existing* Lead Supply owner review packet, not raw consumer
contacts. A source-owned classification is not independently authenticated
consent, geographic acceptance or a paid lead. Identical lead/event replay
never becomes two inventory units.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import re
from typing import Any,Mapping

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_commercial_requirements import SCHEMA as REQUIREMENT

SCHEMA="empire.predictive_revenue.lead_eligibility_owner_audit.v1"
OWNER_SCHEMA="empire.lead_supply.owner_eligibility_preview.v1"
SHA=re.compile(r"^[a-f0-9]{64}$")
KINDS=frozenset(("owner_claimed_billable","research_unqualified",
                 "duplicate_suppressed","rejected","withdrawn"))
EVENTS=frozenset(("consented_form","verified_inbound_call","booked_appointment"))
ROW_KEYS=frozenset((
    "lead_ref_sha256","original_event_ref_sha256","zip_code",
    "source_event_at","event_type","classification",
    "original_consent_proof_authenticated","billable_customer_acceptance_verified",
    "source_event_delivery_authenticated",
))


def review_lead_eligibility_owner_preview(
    requirement:Mapping[str,Any],
    owner_packet:Mapping[str,Any]|None,*,as_of:datetime,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware trusted reviewer time required")
    if not isinstance(requirement,Mapping) or requirement.get("schema_version")!=REQUIREMENT:
        raise ValueError("original validated commercial requirement required")
    base={
        "schema_version":SCHEMA,"status":"PER_LEAD_OWNER_AUDIT_NOT_AVAILABLE",
        "mode":"OBSERVE","source_owner_observed_records":None,
        "source_owner_claimed_billable_not_verified":None,
        "source_owner_suppressed_duplicate_records":None,
        "source_owner_rejected_or_withdrawn_records":None,
        "exact_zip_scope_matching_possible":bool(requirement.get("source_entered_zip_codes")),
        "eligible_and_independently_authenticated_customer_leads":None,
        "real_reserved_leads":None,
        "original_consent_and_uniqueness_independently_authenticated":False,
        "original_owner_source_signature_authenticated":False,
        "tenant_company_and_offer_authentication_verified":False,
        "execution_authority":"none",
        "database_writes":False,"outbound_sent":False,
    }
    if owner_packet is None:
        return base
    p=owner_packet
    if (not isinstance(p,Mapping) or set(p)!={
            "schema_version","source_owner","mode","execution_authority",
            "requirement_revision_sha256","generated_at","records",
            "source_owner_message_authenticated","delivery_executed"}
            or p["schema_version"]!=OWNER_SCHEMA
            or p["source_owner"]!="existing_lead_supply_intelligence"
            or p["mode"]!="OBSERVE"
            or p["execution_authority"]!="none"
            or p["source_owner_message_authenticated"] is not False
            or p["delivery_executed"] is not False
            or p["requirement_revision_sha256"]!=requirement.get(
                "requirement_revision_sha256")):
        raise ValueError("unauthorized per-lead preview owner packet")
    ts=_time(p["generated_at"])
    now=as_of.astimezone(timezone.utc)
    if not timedelta(0)<=now-ts<=timedelta(hours=48):
        raise ValueError("source owner lead eligibility preview stale or future")
    rows=p["records"]
    if not isinstance(rows,list) or len(rows)>100:
        raise ValueError("bounded owner reported lead records required")
    leads=set();events=set()
    claimed=0;suppressed=0;rejected=0
    zip_allowed=set(requirement.get("source_entered_zip_codes",()))
    for row in rows:
        if not isinstance(row,Mapping) or set(row)!=ROW_KEYS:
            raise ValueError("typed original lead event preview required")
        for k in ("lead_ref_sha256","original_event_ref_sha256"):
            if not isinstance(row[k],str) or not SHA.fullmatch(row[k]):
                raise ValueError("opaque source identity required")
        if row["lead_ref_sha256"] in leads or row["original_event_ref_sha256"] in events:
            raise ValueError("duplicate original lead or provider event detected")
        leads.add(row["lead_ref_sha256"]);events.add(row["original_event_ref_sha256"])
        if (row["event_type"] not in EVENTS
                or row["classification"] not in KINDS
                or row["original_consent_proof_authenticated"] is not False
                or row["billable_customer_acceptance_verified"] is not False
                or row["source_event_delivery_authenticated"] is not False):
            raise ValueError("cannot self attest consent, payment or final lead delivery")
        when=_time(row["source_event_at"])
        if not timedelta(0)<=now-when<=timedelta(days=90):
            raise ValueError("source event age exceeds candidate window")
        zip_value=row["zip_code"]
        if not isinstance(zip_value,str) or not re.fullmatch(r"[A-Z0-9 ]{3,9}",zip_value):
            raise ValueError("original ZIP/postcode must be typed")
        if zip_allowed and zip_value not in zip_allowed:
            raise ValueError("original event outside exact user-approved ZIP scope")
        if row["classification"]=="owner_claimed_billable":
            claimed+=1
        elif row["classification"]=="duplicate_suppressed":
            suppressed+=1
        elif row["classification"] in ("rejected","withdrawn"):
            rejected+=1
    return {
        **base,
        "status":"SOURCE_OWNER_LEAD_PREVIEW_DEDUPED_NOT_AUTHENTICATED",
        "source_owner_observed_records":len(rows),
        "source_owner_claimed_billable_not_verified":claimed,
        "source_owner_suppressed_duplicate_records":suppressed,
        "source_owner_rejected_or_withdrawn_records":rejected,
        "source_revision_sha256":sha256(json.dumps(
            {"revision":p["requirement_revision_sha256"],
             "original_refs":sorted(leads),"original_events":sorted(events)},
            sort_keys=True,separators=(",",":")).encode()).hexdigest(),
    }
