"""Original permit and UK tender signals -> Predictive Revenue source/economics triage.

Consume EXISTING source-owner READ-ONLY REVIEW packets. Do not recollect,
retime, or merge US local permit counts with GB national tender notices.
No actual demand/profit, quote/contacts, contract awards or outreach inferred.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import re
from typing import Any,Mapping

from empire_os.permit_project_intelligence import SCHEMA as PERMIT_SCHEMA
from empire_os.uk_public_tender_observer import (
    SCHEMA as TENDER_SCHEMA, BASE as TENDER_SOURCE_BASE,
    DOCUMENTATION as TENDER_DOCUMENTATION,
)
from empire_os.source_intelligence import source_contract
from empire_os.predictive_customer_value_demand import _time

SCHEMA="empire.predictive_revenue.primary_project_procurement_signals.v1"
SHA=re.compile(r"^[a-f0-9]{64}$")
PROOF_REQUIRED=(
    "PRIMARY_SOURCE_SCOPE_AND_CANONICAL_GEO",
    "FIRST_PARTY_BUYER_ROLE_AND_ACCEPTED_PURCHASE_INTENT",
    "ELIGIBLE_SERVICE_CAPACITY_AND_APPROVED_PRICING_TERMS",
    "FORECAST_REGISTERED_BEFORE_COMMERCIAL_OUTCOME",
    "AUTHENTICATED_PAYMENT_REFUND_FULFILMENT_AND_COSTS",
)


def _none(source:str,reason:str)->dict[str,Any]:
    return {
        "source_owner":source,"status":reason,
        "research_observation_count":None,
        "source_revision_sha256":None,
        "actionable_current_business_count":None,
        "source_research_cards":[],
        "official_source_is_paying_buyer":False,
        "actual_revenue_or_margin_verified":False,
        "economic_forecast_calibrated":False,
    }


def _number(v:Any,name:str)->int:
    if type(v) is not int or not 0<=v<=1_000_000:
        raise ValueError("invalid "+name+" aggregate")
    return v


def review_existing_permit_owner(packet:Mapping[str,Any] | None,*,as_of:datetime)->dict[str,Any]:
    base=_none("existing_permit_project_intelligence_owner","PERMIT_OWNER_SOURCE_UNAVAILABLE")
    if packet is None:return base
    if (not isinstance(packet,Mapping)
            or packet.get("schema_version")!=PERMIT_SCHEMA
            or packet.get("mode")!="OBSERVE"
            or packet.get("execution_authority")!="none"
            or packet.get("automatic_sales_promotion") is not False
            or packet.get("buyer_matched") is not False
            or packet.get("recognised_revenue_proven") is not False
            or packet.get("payment_executed") is not False
            or packet.get("independent_cross_source_property_match_proven") is not False
            or packet.get("commercial_qualification_state")!="NOT_VERIFIED"
            or packet.get("source")!="runtime/acquisition/signal_inbox.json"
            or packet.get("outbound_sent") is not False):
        return dict(base,status="PERMIT_OWNER_AUTHORITY_OR_SCHEMA_HOLD")
    try:
        stamp=_time(packet.get("generated_at"))
    except ValueError:
        return dict(base,status="PERMIT_OWNER_SOURCE_CLOCK_HOLD")
    if not timedelta(0)<=as_of.astimezone(timezone.utc)-stamp<=timedelta(hours=8):
        return dict(base,status="PERMIT_OWNER_SOURCE_STALE_HOLD")
    c=packet.get("cohort")
    rows=packet.get("review_dossiers")
    digest=packet.get("total_retained_source_semantics_digest")
    if (not isinstance(c,Mapping) or not isinstance(rows,list) or len(rows)>5
            or type(packet.get("review_dossier_count")) is not int
            or len(rows)!=packet["review_dossier_count"]
            or (digest is not None and (not isinstance(digest,str) or not SHA.fullmatch(digest)))):
        return dict(base,status="PERMIT_OWNER_COUNTS_OR_REVISION_HOLD")
    try:
        loaded=_number(c.get("first_imported_last_24h"),"permit imported")
        recent=_number(c.get("recent_original_filing_or_issuance"),"permit recent")
        historical=_number(c.get("historical_project_source_only"),"permit historical")
        unknown=_number(c.get("untrusted_or_missing_date"),"permit unknown")
        official=_number(c.get("official_provenance_url_passed"),"permit provenance")
        if (loaded<recent+historical+unknown or loaded<official or
                c.get("newly_imported_does_not_mean_new_filing") is not True):
            raise ValueError("original chronology count disagreement")
        cards=[]
        for r in rows:
            if (not isinstance(r,Mapping)
                    or r.get("execution_authority")!="none"
                    or r.get("buyer_demand_proven") is not False
                    or r.get("realised_revenue_proven") is not False
                    or not isinstance(r.get("route"),Mapping)
                    or r["route"].get("sales_promotion_authorized") is not False):
                raise ValueError("untrusted selected permit dossier")
            state=r.get("date_truth_classification")
            if not isinstance(state,str) or len(state)>90:
                raise ValueError("permit date truth missing")
            if r.get("genuine_recent_project_event_observed") is not (
                state in ("RECENT_FILING_FOR_PROJECT_REVIEW","RECENT_ISSUANCE_FOR_PROJECT_REVIEW")
            ):
                raise ValueError("false event chronology claim")
            if r.get("genuine_recent_project_event_observed"):
                if r.get("source_evidence_url") is None:
                    raise ValueError("recent event lacks original official URL")
            cards.append({
                "original_date_truth_classification":state,
                "source_original_recent_project_event":r["genuine_recent_project_event_observed"],
                "source_original_recent_project_is_paying_customer":False,
                "permit_owner_and_permittee_independently_authenticated":False,
                "canonical_project_geo_attested_to_economic_twin":False,
                "research_action":"VERIFY_ORIGINAL_PROJECT_AND_SERVICE_SCOPE"
                    if r["genuine_recent_project_event_observed"]
                    else "NO_NEW_PROJECT_CLAIM_FROM_HISTORICAL_FILING",
                "outbound_allowed":False,
            })
    except (ValueError,TypeError):
        return dict(base,status="PERMIT_OWNER_COUNTER_OR_DOSSIER_HOLD")
    return dict(
        base,status="PERMIT_SOURCE_CHRONOLOGY_TRIAGED",
        research_observation_count=loaded,
        original_recent_filing_or_issuance_count=recent,
        historical_project_source_count=historical,
        original_date_untrusted_count=unknown,
        source_provenance_url_pass_count=official,
        source_revision_sha256=digest,
        latest_source_review_at=stamp.isoformat(),
        sampled_dossier_count=len(cards),source_research_cards=cards,
        # A permit issuance isn't the supplier's commission/purchase. No
        # serviceable/affordable volume can be determined from these counts.
        actionable_current_business_count=None,
        opportunity_country_scope="US",
        opportunity_metro_scope="NYC_ORIGINAL_SOURCE_ONLY",
        next_owner="existing_permit_property_and_buyer_evidence_owners",
        next_action="VERIFY_PROJECT_ROLES_SCOPE_GEOMETRY_AND_ACCEPTED_SERVICE_TERMS",
    )


def review_existing_uk_tender_owner(packet:Mapping[str,Any]|None,*,as_of:datetime)->dict[str,Any]:
    base=_none("existing_uk_public_tender_owner","TENDER_OWNER_SOURCE_UNAVAILABLE")
    if packet is None:return base
    if (not isinstance(packet,Mapping)
            or packet.get("schema_version")!=TENDER_SCHEMA
            or packet.get("mode")!="OBSERVE"
            or packet.get("execution_authority")!="none"
            or packet.get("publisher")!="Cabinet Office"
            or packet.get("documented_source")!=TENDER_SOURCE_BASE
            or packet.get("source_documentation")!=TENDER_DOCUMENTATION
            or packet.get("attribution_required")!="© Crown copyright and database right (OGL v3)"
            or packet.get("commercial_opportunity_kind")!="PUBLISHED_PROCUREMENT_SIGNAL_ONLY"
            or packet.get("outreach_or_bid_authorized") is not False
            or packet.get("actual_contract_or_revenue_proven") is not False
            or packet.get("existing_opportunity_or_crm_created") is not False
            or packet.get("payment_authorized") is not False
            or packet.get("global_open_tender_count_known") is not False):
        return dict(base,status="TENDER_OWNER_AUTHORITY_OR_SCHEMA_HOLD")
    contract=source_contract("gb_find_a_tender_ocds")
    if ("analytics" not in contract.allowed_uses
            or contract.country_code!="GB"
            or contract.production_status!="research"):
        return dict(base,status="TENDER_SOURCE_OWNER_RIGHTS_HOLD")
    try:
        stamp=_time(packet.get("generated_at"))
    except ValueError:
        return dict(base,status="TENDER_OWNER_SOURCE_CLOCK_HOLD")
    if not timedelta(0)<=as_of.astimezone(timezone.utc)-stamp<=timedelta(hours=48):
        return dict(base,status="TENDER_SOURCE_STALE_HOLD")
    rows=packet.get("source_observations")
    n=packet.get("record_count_in_bounded_page")
    statuses=packet.get("tender_status_counts_in_page")
    if (not isinstance(rows,list) or not isinstance(statuses,Mapping)
            or type(n) is not int or not 0<=n<=5 or len(rows)!=n
            or packet.get("sample_at_limit") is not (n==5)):
        return dict(base,status="TENDER_SOURCE_COUNT_HOLD")
    try:
        total=0
        for k,v in statuses.items():
            if not isinstance(k,str):
                raise ValueError("status key")
            total+=_number(v,"tender state")
        if total!=n:
            raise ValueError("source status count conflict")
        seen=set()
        cards=[]
        matches=0
        for r in rows:
            if (not isinstance(r,Mapping)
                    or r.get("source_category_truth")!="PUBLIC_PROCUREMENT_NOTICE"
                    or r.get("notice_is_contract_award") is not False
                    or r.get("buyer_acceptance_or_payment_verified") is not False
                    or type(r.get("future_submissions_deadline_evidenced")) is not bool):
                raise ValueError("tender source claim forged")
            for k in ("ocid_digest","release_digest","source_semantic_digest"):
                if not isinstance(r.get(k),str) or not SHA.fullmatch(r[k]):
                    raise ValueError("tender stable source revision required")
            identity=r["release_digest"]
            if identity in seen:
                raise ValueError("duplicated original release")
            seen.add(identity)
            stage=r.get("source_reported_tender_status")
            verticals=r.get("matched_verticals_from_cpv")
            if (not isinstance(stage,str) or stage not in (
                    "active","complete","cancelled","withdrawn","unsuccessful","UNKNOWN")
                    or not isinstance(verticals,list)
                    or len(verticals)>12
                    or any(x not in ("solar","roofing","hvac","dental") for x in verticals)):
                raise ValueError("invalid tender stage/vertical")
            if r["future_submissions_deadline_evidenced"] and stage!="active":
                raise ValueError("inactive tender cannot have current submission deadline")
            matches+=int(bool(verticals))
            cards.append({
                "original_release_revision_sha256":r["source_semantic_digest"],
                "original_tender_stage":stage,
                "original_cpv_niches":list(verticals),
                "future_submission_deadline_reported":r["future_submissions_deadline_evidenced"],
                "country_scope":"GB",
                "local_contract_performance_location_attested":False,
                "tender_publication_is_contract_award":False,
                "tender_value_or_budget_is_supplier_revenue":False,
                "respond_to_bid_authorized":False,
                "research_action":"REVIEW_ORIGINAL_NOTICE_ELIGIBILITY_AND_CAPACITY"
                    if stage=="active" and r["future_submissions_deadline_evidenced"] and verticals
                    else "READ_ONLY_PROCUREMENT_RESEARCH",
            })
    except (ValueError,TypeError):
        return dict(base,status="TENDER_OWNER_RELEASE_CONTRACT_HOLD")
    digest=sha256(json.dumps(
        sorted((r["release_digest"],r["source_semantic_digest"]) for r in rows),
        separators=(",",":"),allow_nan=False,
    ).encode()).hexdigest()
    return dict(
        base,status="UK_TENDER_SOURCE_STAGE_TRIAGED",
        research_observation_count=n,
        original_cpv_relevant_notice_count=matches,
        source_revision_sha256=digest,
        last_owner_observation_at=stamp.isoformat(),
        source_sample_limited_to_five_releases=True,
        opportunity_country_scope="GB",
        original_source_is_contract_award=False,
        tender_publication_is_verified_contract_revenue=False,
        source_research_cards=cards,
        next_owner="existing_uk_tender_procurement_commercial_owner",
        next_action="VERIFY_OFFICIAL_BID_ELIGIBILITY_CONTRACT_SCOPE_AND_REAL_COSTS",
    )


def build_primary_source_economic_review(
    permit:Mapping[str,Any] | None,
    tender:Mapping[str,Any] | None, *,
    as_of:datetime,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted decision clock required")
    p=review_existing_permit_owner(permit,as_of=as_of)
    t=review_existing_uk_tender_owner(tender,as_of=as_of)
    missing=[
        "REGISTERED_ORIGINAL_QUANT_FORECAST_AND_COHORT",
        "SOURCE_AUTHENTICATED_ISSUANCE_OR_CONTRACT_STAGE",
        "ACTUAL_BUYER_TERMS_DELIVERY_COST_CAPACITY_AND_REFUNDS",
        "INDEPENDENT_SETTLED_OUTCOME_GROSS_PROFIT",
    ]
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"PRIMARY_PROJECT_AND_PROCUREMENT_ECONOMIC_TRIAGE_REVIEWED",
        "source_owner_count":2,
        "sources":{"us_permit_project":p,"gb_public_procurement":t},
        "country_and_territory_source_scopes_are_joined":False,
        "external_source_is_first_party_customer_purchase":False,
        "tender_notice_is_guaranteed_sale":False,
        "historical_import_means_recent_building_demand":False,
        "aggregate_opportunity_market_size_inferred":False,
        "customer_revenue_or_profit_recognized":False,
        "business_playbook_actions_dispatched":False,
        "remaining_proof_gates":list(PROOF_REQUIRED)+missing,
        "next_owner":"existing_permit_tender_spatial_quant_and_finance_owners",
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
