"""Read-only original Lead Supply + Buyer Capacity + A2A owner readiness.

Counts are GLOBAL research snapshots, not tenant-specific available inventory.
Never convert selected prospect records or social buying-signal research to
qualified consented consumer leads or purchasing capacity.
"""
from __future__ import annotations
from datetime import datetime, timedelta,timezone
from pathlib import Path
from typing import Any,Mapping
import json
from empire_os.predictive_customer_value_demand import _time

SCHEMA="empire.predictive_revenue.lead_supply_buyer_readiness.v1"
SUPPLY="empire.leadgen_revenue_activation_queue.v1"
BUYER="empire.buyer_capacity_readiness.v1"
SCOUT="empire.buyer_acquisition_scout.v1"


def _count(x:Any,k:str)->int:
    if type(x) is not int or not 0<=x<=10_000_000:
        raise ValueError("source counter must be bounded integer "+k)
    return x


def _age(src:Mapping[str,Any],name:str,now:datetime)->float:
    timestamp=_time(src.get(name))
    delta=now-timestamp
    if not timedelta(0)<=delta<=timedelta(hours=48):
        raise ValueError("original owner epoch stale or future")
    return round(delta.total_seconds()/3600,3)


def review_original_lead_readiness(
    supply:Mapping[str,Any]|None,buyer:Mapping[str,Any]|None,
    scout:Mapping[str,Any]|None,*,as_of:datetime,
    industry:str,country:str,state:str,city:str,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("timezone aware clock required")
    if (not isinstance(industry,str) or not 3<=len(industry)<=50
            or not isinstance(country,str) or not isinstance(state,str)
            or not isinstance(city,str)):
        raise ValueError("source research must be scoped to a typed customer industry and market")
    now=as_of.astimezone(timezone.utc)
    base={
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"INSUFFICIENT_EVIDENCE",
        "source_lead_supply_status":"SOURCE_UNAVAILABLE_OR_UNVERIFIED",
        "source_buyer_capacity_status":"SOURCE_UNAVAILABLE_OR_UNVERIFIED",
        "source_buyer_scout_status":"SOURCE_UNAVAILABLE_OR_UNVERIFIED",
        "global_immediately_sellable_inventory":None,
        "research_target_industry":industry,
        "research_target_market_country":country,
        "research_target_market_state":state,
        "research_target_market_city":city,
        "source_target_industry_research_records_not_leads":None,
        "source_target_industry_bucket_present":False,
        "original_source_roofing_research_records_not_leads":None,
        "canonical_selected_records_not_accepted_consumer_leads":None,
        "canonical_research_waitlist_records":None,
        "buyer_identity_candidates_not_committed_buyers":None,
        "verified_global_buyer_capacity_count":None,
        "verified_target_market_eligible_leads":None,
        "verified_target_market_available_inventory":None,
        "available_to_commit_target_market_units":None,
        "verified_tampa_eligible_leads":None,
        "verified_tampa_available_inventory":None,
        "available_to_commit_tampa_units":None,
        "territory_match_proven":False,"lead_consent_qualification_proven":False,
        "buyer_terms_and_capacity_proven":False,
        "zero_source_sellable_records_proves_no_regional_demand":False,
        "prospect_records_are_billable_customer_enquiries":False,
        "authenticated_current_commercial_buyer_available":False,
        "owner_source_epochs_are_atomic":False,
        "consumer_leads_reserved_or_allocated":False,
        "database_writes":False,"outbound_sent":False,"execution_authority":"none",
    }
    try:
        if (not isinstance(supply,Mapping)
                or supply.get("schema_version")!=SUPPLY
                or supply.get("mode")!="READ_ONLY_PRIVATE_LEADGEN"
                or supply.get("execution_authority")!="none"
                or supply.get("canonical_empiredb_writes") is not False
                or supply.get("buyer_outreach_authorized") is not False
                or supply.get("prospect_insert_authorized") is not False):
            raise ValueError("supply owner authority")
        age=_age(supply,"generated_at",now)
        research=supply.get("observed_supply_by_vertical_not_buyer_mapped")
        if not isinstance(research,Mapping):
            raise ValueError("original market research buckets unavailable")
        sector_raw=research.get(industry)
        sector_count=(_count(sector_raw,industry+" research")
                      if sector_raw is not None else None)
        sell=_count(supply.get("immediately_sellable_inventory"),"sellable")
        selected=_count(supply.get("canonical_selected_inventory_records"),"selected")
        wait=_count(supply.get("canonical_capacity_waitlist_records"),"waitlist")
        _count(supply.get("qualified_buyers"),"qualified buyer aggregate")
        vcap=_count(supply.get("verified_buyer_capacity"),"capacity")
        if supply.get("territory_matching_performed") is not False:
            raise ValueError("source territory mapping altered")
        base.update(
            source_lead_supply_status="FRESH_RESEARCH_COUNTS_NOT_DELIVERABLE_INVENTORY",
            supply_source_age_hours=age,
            global_immediately_sellable_inventory=sell,
            source_target_industry_research_records_not_leads=sector_count,
            source_target_industry_bucket_present=sector_count is not None,
            original_source_roofing_research_records_not_leads=(
                sector_count if industry=="roofing" else None),
            canonical_selected_records_not_accepted_consumer_leads=selected,
            canonical_research_waitlist_records=wait,
            verified_global_buyer_capacity_count=vcap,
        )
    except (ValueError,TypeError):
        base["source_lead_supply_status"]="OWNER_SOURCE_STALE_OR_AUTHORITY_HOLD"
    try:
        if (not isinstance(buyer,Mapping)
                or buyer.get("schema_version")!=BUYER
                or buyer.get("mode")!="OBSERVE"
                or buyer.get("execution_authority")!="none"
                or buyer.get("allocation_executed") is not False
                or buyer.get("payment_action") is not False):
            raise ValueError("buyer source authority")
        age=_age(buyer,"observed_at",now)
        _count(buyer.get("buyers_seen"),"buyers observed")
        verified=_count(buyer.get("capacity_verified"),"verified capacity buyer count")
        terms=_count(buyer.get("terms_verified"),"verified commercial terms count")
        activated=_count(buyer.get("fully_activated"),"activated")
        if buyer.get("allocation_ready") is not False:
            raise ValueError("buyer original approval mismatch")
        base.update(
            source_buyer_capacity_status="FRESH_BUYER_RESEARCH_NO_ALLOCATABLE_CAPACITY",
            buyer_owner_age_hours=age,
            original_buyer_records_reviewed_not_approved=buyer["buyers_seen"],
            buyers_with_verified_capacity=verified,
            buyers_with_verified_terms=terms,
            fully_activated_buyer_count=activated,
        )
    except (ValueError,TypeError):
        base["source_buyer_capacity_status"]="OWNER_SOURCE_STALE_OR_AUTHORITY_HOLD"
    try:
        if (not isinstance(scout,Mapping)
                or scout.get("schema_version")!=SCOUT
                or scout.get("mode")!="OBSERVE"
                or scout.get("execution_authority")!="none"
                or scout.get("outbound_sent") is not False
                or scout.get("database_write_performed") is not False
                or scout.get("actual_revenue") is not False):
            raise ValueError("Scout source authority")
        age=_age(scout,"generated_at",now)
        candidates=_count(scout.get("candidate_count"),"scout")
        base.update(
            source_buyer_scout_status="FRESH_COMPANY_RESEARCH_NOT_CONFIRMED_BUYING_ROLE",
            scout_source_age_hours=age,
            buyer_identity_candidates_not_committed_buyers=candidates,
        )
    except (ValueError,TypeError):
        base["source_buyer_scout_status"]="OWNER_SOURCE_STALE_OR_AUTHORITY_HOLD"
    return base


def _read(root:Path,path:str)->Mapping[str,Any]|None:
    p=root/path
    try:
        if (p.is_symlink() or p.parent.is_symlink()
                or not p.is_file() or not 0<p.stat().st_size<=1_000_000):
            return None
        record=json.loads(p.read_text(encoding="utf-8"))
        return record if isinstance(record,Mapping) else None
    except (OSError,ValueError,UnicodeError):
        return None


def review_lead_readiness_runtime(
    root:str|Path,*,as_of:datetime,
    industry:str,country:str,state:str,city:str,
)->dict[str,Any]:
    path=Path(root).resolve()
    return review_original_lead_readiness(
        _read(path,"runtime/lead_supply/private_leadgen/research_queue_latest.json"),
        _read(path,"runtime/buyer_capacity_readiness/latest.json"),
        _read(path,"runtime/buyer_acquisition/scout_latest.json"),
        as_of=as_of,industry=industry,country=country,state=state,city=city,
    )
