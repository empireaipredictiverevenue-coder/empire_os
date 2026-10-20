"""Existing owner A2A / Lead Supply / Finance pickup for commercial requirements.

Original A2A research tickets are from fixed founder prompt profiles, NOT
generic agent acceptance of a new requirement. Source-owner snapshot counts
are not customer-specific commitments. This module never publishes to queues,
calls external models, reads private contacts, or re-authenticates signed work.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import re

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_commercial_requirements import SCHEMA as REQUIREMENT_SCHEMA
from empire_os.predictive_commercial_fulfilment import SCHEMA as PLAN_SCHEMA
from empire_os.predictive_commercial_supply_readiness import SCHEMA as SUPPLY_SCHEMA
from empire_os.enterprise_finance_evidence_readiness import SCHEMA as FINANCE_SCHEMA

SCHEMA="empire.predictive_revenue.existing_owner_research_pickup.v1"
A2A_SCHEMA="empire.a2a.targeted_owner_research_handoff.v1"
RECEIPT_SCHEMA="empire.a2a.owner_research_receipt_review.v1"
SAFE_SECTOR=re.compile(r"^[a-z][a-z0-9_]{2,48}$")
SAFE_REGION=re.compile(r"^[a-z0-9 ,.-]{2,90}$")
TICKET_REF=re.compile(r"^[0-9a-f]{24}$")
A2A_PATH="runtime/a2a_commercial_signal_mining/buyer_owner_research_handoffs_v1.json"
RECEIPT_PATH="runtime/a2a_commercial_signal_mining/owner_signed_receipts_review_v1.json"
OWNERS=(
    "a2a_commercial_signal_miner","buyer_scout","lead_supply_intelligence",
    "marketing_seo_campaigns","procurement_supply_intelligence","finance_os",
    "predictive_quant","predictive_cloud",
)
PROOFS={
    "a2a_commercial_signal_miner":"AUTHORITATIVE_SOURCE_AND_TARGET_MATCHED_RESEARCH_OWNER_REPLY",
    "buyer_scout":"CANONICAL_COMPANY_BUYING_ROLE_CAPACITY_AND_DEDUPE",
    "lead_supply_intelligence":"CONSENTED_UNIQUE_ORIGINAL_LEAD_ZIP_AND_EXCLUSIVITY",
    "marketing_seo_campaigns":"APPROVED_CHANNEL_ORIGINAL_CAC_BUDGET_AND_SOURCE_RIGHTS",
    "procurement_supply_intelligence":"MEASURED_PROJECT_BOM_COMPARABLE_QUOTE_AND_FREIGHT",
    "finance_os":"SIGNED_PRICE_PAYMENT_REFUNDS_LABOR_COST_AND_SETTLEMENT",
    "predictive_quant":"ORIGINAL_PROFIT_FORECAST_REGISTERED_BEFORE_REAL_OUTCOME",
    "predictive_cloud":"SOURCE_SCOPED_BUDGET_CAPACITY_DOWNRISK_AND_REAL_PROFIT",
}


def _observed_time(value:Any,now:datetime)->float:
    date=_time(value)
    diff=now-date
    if not timedelta(0)<=diff<=timedelta(hours=48):
        raise ValueError("owner report stale or dated in the future")
    return round(diff.total_seconds()/3600,3)


def _nonnegative(value:Any,name:str,max_val:int=100000)->int:
    if type(value) is not int or not 0<=value<=max_val:
        raise ValueError("bounded "+name+" required")
    return value


def review_existing_a2a_owner_research(
    requirement:Mapping[str,Any],
    report:Mapping[str,Any]|None,
    receipt_review:Mapping[str,Any]|None,*,as_of:datetime,
)->dict[str,Any]:
    """Review only summary/ticket IDs and exact sector+city/state; never raw buyer data."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("timezone-aware source custody required")
    if (not isinstance(requirement,Mapping)
            or requirement.get("schema_version")!=REQUIREMENT_SCHEMA):
        raise ValueError("original validated industry/market requirement required")
    now=as_of.astimezone(timezone.utc)
    industry=requirement.get("industry")
    state=requirement.get("state")
    city=requirement.get("city")
    if (not isinstance(industry,str) or not SAFE_SECTOR.fullmatch(industry)
            or not isinstance(state,str) or not 2<=len(state)<=8
            or not isinstance(city,str) or not 2<=len(city)<=70):
        raise ValueError("exact typed original requirement sector and region required")
    source_region=(city+", "+state).casefold()
    base={
        "schema_version":A2A_SCHEMA,
        "reviewed_original_requirement_revision_sha256":requirement["requirement_revision_sha256"],
        "reviewed_industry":industry,
        "reviewed_city_region":source_region,
        "status":"ORIGINAL_A2A_OWNER_RESEARCH_UNAVAILABLE",
        "mode":"OBSERVE",
        "source_existing_profiles_count":None,
        "source_prepared_review_tickets_count":None,
        "source_matching_exact_sector_city_region_tickets_count":None,
        "source_matching_prepared_ticket_ids":[],
        "source_matching_review_owners":[],
        "original_a2a_source_fresh":False,
        "owner_source_reported_match_is_our_requirement_acknowledgement":False,
        "original_owner_dispatch_receipt":None,
        "original_owner_authenticated_reply_count":None,
        "owner_trust_store_ready":False,
        "source_authenticated_buyer_or_customer_order":False,
        "source_owner_buyer_contacts_exposed":False,
        "outbound_authorized":False,"database_writes":False,
        "execution_authority":"none",
    }
    if report is None:
        return base
    if (not isinstance(report,Mapping)
            or report.get("schema_version")!=A2A_SCHEMA
            or report.get("mode")!="OBSERVE"
            or report.get("execution_authority")!="NONE"
            or report.get("owner_queue_published") is not False
            or report.get("owner_response_received") is not False
            or any(type(report.get(k)) is not int or report[k]!=0 for k in (
                "tasks_dispatched","messages_sent","buyer_record_writes",
                "externally_verified_new_buyers"))):
        raise ValueError("A2A original owner report must remain research-only")
    try:
        age=_observed_time(report.get("generated_at"),now)
    except (ValueError,TypeError):
        return {**base,"status":"ORIGINAL_A2A_OWNER_RESEARCH_STALE_HOLD"}
    profiles=_nonnegative(report.get("profiles_reviewed"),"original profile count",10)
    rows=report.get("handoff_tickets")
    if not isinstance(rows,list) or len(rows)>20:
        raise ValueError("bounded original A2A ticket rows required")
    count=_nonnegative(report.get("prepared_handoff_ticket_count"),"A2A count",20)
    if len(rows)!=count:
        raise ValueError("original A2A ticket count mismatch")
    seen=set()
    matching=[]
    for ticket in rows:
        if not isinstance(ticket,Mapping):
            raise ValueError("original A2A ticket item required")
        ident=ticket.get("ticket_id")
        if (not isinstance(ident,str) or not TICKET_REF.fullmatch(ident)
                or ident in seen):
            raise ValueError("duplicate or invalid original A2A ticket identity")
        seen.add(ident)
        if (ticket.get("state")!="PREPARED_NOT_DELIVERED"
                or ticket.get("review_owner") not in ("buyer_scout","community_intent")
                or ticket.get("may_send_messages") is not False
                or ticket.get("may_write_canonical_crm") is not False
                or ticket.get("may_call_external_api") is not False
                or ticket.get("owner_approval_required") is not True):
            raise ValueError("A2A report ticket cannot self-escalate authority")
        niche,metro=ticket.get("sector"),ticket.get("market")
        if (not isinstance(niche,str) or not SAFE_SECTOR.fullmatch(niche)
                or not isinstance(metro,str) or not SAFE_REGION.fullmatch(metro)):
            raise ValueError("A2A original reported target invalid")
        if niche.casefold()==industry.casefold() and metro.casefold()==source_region:
            matching.append((ident,ticket["review_owner"]))
    base.update(
        source_existing_profiles_count=profiles,
        source_prepared_review_tickets_count=count,
        source_matching_exact_sector_city_region_tickets_count=len(matching),
        source_matching_prepared_ticket_ids=sorted(t for t,_ in matching),
        source_matching_review_owners=sorted({owner for _,owner in matching}),
        original_a2a_source_fresh=True,
        original_a2a_report_age_hours=age,
        status=("EXISTING_A2A_PROFILE_RESEARCH_ONLY_NO_CUSTOMER_ACK"
                if matching else
                "NO_EXACT_PREEXISTING_A2A_SECTOR_CITY_REGION_PROFILE"),
    )
    if receipt_review is None:
        return {**base,"original_owner_receipt_state":"ORIGINAL_RECEIPT_REPORT_UNAVAILABLE"}
    receipt=receipt_review
    if (not isinstance(receipt,Mapping)
            or receipt.get("schema_version")!=RECEIPT_SCHEMA
            or receipt.get("mode")!="OBSERVE"
            or receipt.get("execution_authority")!="NONE"
            or type(receipt.get("owner_task_dispatches_by_this_protocol")) is not int
            or receipt.get("owner_task_dispatches_by_this_protocol")!=0
            or receipt.get("outbound_authority") is not False
            or receipt.get("money_movement_authority") is not False
            or receipt.get("buyer_identity_verified_by_this_protocol") is not False
            or receipt.get("buyer_qualified_by_this_protocol") is not False
            or receipt.get("purchase_intent_verified_by_this_protocol") is not False):
        raise ValueError("A2A receipt packet may not claim unauthorized buyer truth")
    receipts=_nonnegative(receipt.get("authenticated_owner_replies"),"authenticated owner replies",10000)
    dispatched=_nonnegative(receipt.get("prepared_research_requests"),"prepared requests",10000)
    if dispatched!=count:
        raise ValueError("owner receipt review not aligned to original owner tickets")
    store=receipt.get("owner_public_keys_configured")
    if not isinstance(store,list) or len(store)>100:
        raise ValueError("owner trust key inventory must be bounded")
    if receipts>0 or len(store)>0:
        # Source owner can authenticate receipts, but this consumer has not
        # independently verified the sender's key, signature, audience or
        # linkage to its original requirement. Do not promote receipt claims.
        return {
            **base,
            "original_owner_receipt_state":"OWNER_REPORTED_RECEIPTS_NEED_INDEPENDENT_KEY_READBACK",
            "original_owner_authenticated_reply_count":receipts,
            "owner_trust_store_ready":False,
        }
    return {
        **base,
        "original_owner_receipt_state":"NO_AUTHENTICATED_OWNER_REPLY_OR_KEYS",
        "original_owner_authenticated_reply_count":0,
    }


def review_department_owner_pickup(
    requirement:Mapping[str,Any],plan:Mapping[str,Any],
    supply:Mapping[str,Any],finance:Mapping[str,Any],
    a2a:Mapping[str,Any],
)->dict[str,Any]:
    """Dependency ordered owner review; no campaign/procurement/Quant execution."""
    if (not isinstance(requirement,Mapping) or requirement.get("schema_version")!=REQUIREMENT_SCHEMA
            or requirement.get("status")!="COMMERCIAL_REQUIREMENT_INCOMPLETE"
            or not isinstance(plan,Mapping) or plan.get("schema_version")!=PLAN_SCHEMA
            or plan.get("execution_authority")!="none"
            or plan.get("original_requirement_revision_sha256")!=requirement.get("requirement_revision_sha256")
            or not isinstance(supply,Mapping) or supply.get("schema_version")!=SUPPLY_SCHEMA
            or supply.get("execution_authority")!="none"
            or not isinstance(finance,Mapping) or finance.get("schema_version")!=FINANCE_SCHEMA
            or finance.get("execution_authority")!="none"
            or not isinstance(a2a,Mapping) or a2a.get("schema_version")!=A2A_SCHEMA
            or a2a.get("execution_authority")!="none"
            or a2a.get("reviewed_original_requirement_revision_sha256")!=
                requirement.get("requirement_revision_sha256")
            or a2a.get("reviewed_industry")!=requirement.get("industry")
            or a2a.get("reviewed_city_region")!=
                (requirement["city"]+", "+requirement["state"]).casefold()):
        raise ValueError("same original custody and read-only review contracts required")
    tickets=plan.get("owner_handoffs_prepared_not_dispatched")
    if not isinstance(tickets,list) or len(tickets)!=len(OWNERS):
        raise ValueError("original full owner handoff list required")
    original={}
    for ticket in tickets:
        if not isinstance(ticket,Mapping):
            raise ValueError("invalid prepared department ticket")
        owner=ticket.get("owner")
        if (owner not in OWNERS or owner in original
                or ticket.get("source_requirement_revision_sha256")!=
                requirement["requirement_revision_sha256"]
                or ticket.get("status")!="PREPARED_NOT_DELIVERED"
                or ticket.get("execution_authority")!="none"
                or ticket.get("task_dispatched") is not False
                or ticket.get("owner_acknowledgement_receipt") is not None):
            raise ValueError("invalid/duplicated or falsely accepted owner handoff")
        original[owner]=ticket
    if set(original)!=set(OWNERS):
        raise ValueError("missing expected original specialist owner")
    if any(supply.get(k)!=requirement[v] for k,v in (
        ("research_target_industry","industry"),
        ("research_target_market_country","country"),
        ("research_target_market_state","state"),
        ("research_target_market_city","city"),
    )):
        raise ValueError("buyer and Lead Supply research cannot be joined across markets")
    source_quality={
        "a2a":a2a["status"],
        "lead_supply":supply.get("source_lead_supply_status"),
        "buyer_capacity":supply.get("source_buyer_capacity_status"),
        "buyer_scout":supply.get("source_buyer_scout_status"),
        "finance":finance.get("status"),
    }
    source_holds={
        "a2a_commercial_signal_miner":a2a["status"],
        "buyer_scout":supply.get("source_buyer_scout_status"),
        "lead_supply_intelligence":supply.get("source_lead_supply_status"),
        "marketing_seo_campaigns":"CUSTOMER_CONSENT_BUDGET_AND_UNIT_CAC_UNVERIFIED",
        "procurement_supply_intelligence":"PROJECT_SCOPE_AND_SUPPLIER_QUOTES_UNVERIFIED",
        "finance_os":finance.get("status"),
        "predictive_quant":"ORIGINAL_PROFIT_FORECAST_AND_ACTUAL_COHORT_NOT_REGISTERED",
        "predictive_cloud":"NO_AUDITED_COST_CAPACITY_PROFIT_FORECAST_TO_OPTIMIZE",
    }
    order=[]
    for rank,owner in enumerate(OWNERS,1):
        procurement_not_applicable=(
            owner=="procurement_supply_intelligence"
            and requirement.get("physical_material_procurement_applicable") is False
        )
        candidate=original[owner]
        order.append({
            "priority":rank,
            "owner":owner,
            "original_draft_idempotency_key":candidate["idempotency_key"],
            "original_source_state":source_holds[owner],
            "operational_state":(
                "NO_PHYSICAL_MATERIAL_RFQ_REQUIRED"
                if procurement_not_applicable else
                "AWAITING_EXISTING_OWNER_ACCEPTANCE_AND_EVIDENCE"),
            "owner_required_original_proof":(
                "NOT_APPLICABLE" if procurement_not_applicable else PROOFS[owner]),
            "review_prepared_not_dispatched":not procurement_not_applicable,
            "previous_ticket_already_delivered":False,
            "original_cryptographic_owner_acknowledgement":None,
            "live_service_execution_eligible":False,
        })
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"COMMERCIAL_CROSS_OWNER_RESEARCH_PLAN_BLOCKED_PENDING_EVIDENCE",
        "original_requirement_revision_sha256":requirement["requirement_revision_sha256"],
        "scope":{"industry":requirement["industry"],"country":requirement["country"],
                 "state":requirement["state"],"city":requirement["city"]},
        "source_owner_statuses":source_quality,
        "owner_required_action_queue":order,
        "existing_a2a_matching_research_tickets_not_customer_acks":a2a.get(
            "source_matching_exact_sector_city_region_tickets_count"),
        "finance_independent_evidence_gaps_remaining":finance.get(
            "required_proofs_not_admitted_count"),
        "lead_supply_global_sellable_count_not_market_inventory":supply.get(
            "global_immediately_sellable_inventory"),
        "original_market_eligible_lead_inventory":None,
        "original_customer_contract_verified":False,
        "original_owner_requirements_accepted":False,
        "verified_profit_forecast_error":None,
        "crm_lead_reservations":0,
        "handoff_draft_count":len(order),
        "owner_handoffs_dispatched":0,
        "procurement_orders_placed":0,
        "commercial_revenue_recognized_minor":None,
        "network_or_external_api_calls":False,
        "source_owner_modules_modified":False,
        "canonical_database_read":False,"database_writes":False,
        "outbound_sent":False,"execution_authority":"none",
    }


def _read_owner_json(root:Path,rel:str)->Mapping[str,Any]|None:
    p=root/rel
    try:
        # No symlink redirection to foreign files and no unbounded reads.
        if p.is_symlink() or p.parent.is_symlink() or not p.is_file():
            return None
        stat=p.stat()
        if not 0<stat.st_size<=120000:
            return None
        o=json.loads(p.read_text(encoding="utf-8"))
        return o if isinstance(o,Mapping) else None
    except (OSError,ValueError,UnicodeError):
        return None


def read_existing_a2a_owner_reports(
    root:str|Path,*,requirement:Mapping[str,Any],as_of:datetime,
)->dict[str,Any]:
    location=Path(root).resolve()
    return review_existing_a2a_owner_research(
        requirement,
        _read_owner_json(location,A2A_PATH),
        _read_owner_json(location,RECEIPT_PATH),
        as_of=as_of,
    )
