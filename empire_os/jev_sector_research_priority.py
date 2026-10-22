"""Jev research prioritisation over audited historical sector aggregates.

It does not join prospects, identify people, infer buyers from permits, or
treat a configured Buyer Scout record as payable capacity. Canonical Research,
Buyer Scout, CRM and economic-memory owners retain all execution authority.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping
import re

from empire_os.executive_buyer_capacity_review import review_buyer_capacity
from empire_os.jev_large_prospect_dump_reader import KNOWN_NICHES
from empire_os.typed_decision_provider import TypedDecisionRequest, review_typed_decision_result

SCHEMA="empire.jev.sector_research_priority.v1"
ARCHIVE_SCHEMA="empire.jev.large_prospect_copy_stream.v1"
GPS_SCHEMA="empire.market_sweep_revenue_gps.v1"
MAX_GPS_AGE=timedelta(hours=4)
MAX_ROWS=80
MAX_SHADOW=2
MODEL_LABELS=(
    "VERIFY_ORIGINAL_SOURCE","CHECK_RECENT_DEMAND",
    "VERIFY_BUYER_CAPACITY","REMAP_TAXONOMY","HOLD",
)
REGULATED=frozenset({
    "auto_insurance","debt_relief","debt_consolidation",
    "business_loan_broker","medical_claims","mental_health_clinic",
    "addiction_treatment_center","home_health_agency","assisted_living",
    "medicare_advantage_agent",
})


def _bounded_count(x:Any,maximum:int=2_000_000)->int:
    if type(x) is not int or not 0<=x<=maximum:
        raise ValueError("unexpected sector aggregate count")
    return x


def _source_date(value:Any,now:datetime)->bool:
    if not isinstance(value,str):
        return False
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        return (parsed.utcoffset() is not None and
                timedelta(0)<=now-parsed.astimezone(timezone.utc)<=MAX_GPS_AGE)
    except (ValueError,OverflowError):
        return False


def _validate_archive(archive:Mapping[str,Any])->dict[str,int]:
    if (not isinstance(archive,Mapping)
        or archive.get("schema_version")!=ARCHIVE_SCHEMA
        or archive.get("status")!="HISTORIC_PROSPECT_COPY_IDENTITY_MATCH_REVIEW_ONLY"
        or archive.get("source_kind")!="OFFLINE_POSTGRESQL_COPY_DATA_DUMP"
        or archive.get("historical_independent_id_set_match") is not True
        or archive.get("historical_digest_track_limit_reached") is not False
        or archive.get("source_read_is_not_current_live_database_count") is not True
        or archive.get("all_source_rows_in_memory") is not False
        or archive.get("source_contacts_or_names_exported") is not False
        or archive.get("deduplicated_person_or_business_count_verified") is not False
        or archive.get("source_rights_and_individual_consent_verified") is not False
        or archive.get("model_records_processed")!=0
        or archive.get("commercial_leads_authorized")!=0
        or archive.get("outreach_sent")!=0
        or archive.get("database_writes") is not False
        or archive.get("execution_authority")!="none"):
        raise ValueError("original archive cannot confer commercial authority")
    count=_bounded_count(archive.get("source_counted_copy_rows"),10_000_000)
    buckets=archive.get("niche_aggregate_counts")
    if (not isinstance(buckets,dict) or not 1<=len(buckets)<=MAX_ROWS
        or any(not isinstance(k,str) or
               k not in KNOWN_NICHES|{"other_or_unmapped","other_or_suppressed"}
               for k in buckets)):
        raise ValueError("unexpected original archive taxonomy")
    if sum(_bounded_count(v,10_000_000) for v in buckets.values())!=count:
        raise ValueError("archive taxonomy does not reconcile original rows")
    if not isinstance(archive.get("source_file_sha256"),str) or not re.fullmatch(r"[a-f0-9]{64}",archive["source_file_sha256"]):
        raise ValueError("source archive digest unavailable")
    return buckets


def _validate_gps(gps:Any,now:datetime)->tuple[dict[str,int],bool]:
    if gps is None:
        return {},False
    if (not isinstance(gps,Mapping)
        or gps.get("schema_version")!=GPS_SCHEMA
        or gps.get("mode")!="OBSERVE"
        or gps.get("execution_authority")!="none"
        or gps.get("buyer_intent_inferred") is not False
        or gps.get("commercial_intent_inferred") is not False
        or gps.get("revenue_inferred") is not False
        or gps.get("outreach_enabled") is not False):
        raise ValueError("untrusted market GPS claims")
    if not _source_date(gps.get("generated_at"),now):
        return {},False
    rows=gps.get("markets")
    if not isinstance(rows,list) or len(rows)>200:
        raise ValueError("unbounded GPS segment inventory")
    counts=Counter()
    for row in rows:
        if (not isinstance(row,Mapping)
            or row.get("execution_authority")!="none"
            or row.get("buyer_intent_inferred") is not False
            or row.get("commercial_intent_inferred") is not False
            or row.get("revenue_inferred") is not False):
            raise ValueError("untrusted original market segment")
        niche=row.get("niche")
        amount=_bounded_count(row.get("prospect_count"),1_000_000)
        # Discard unknown keys; never allow arbitrary segment names to
        # appear as a model taxonomy, outreach category or public label.
        if niche in KNOWN_NICHES:
            counts[niche]+=amount
    return dict(counts),True


def prioritize_sector_research(
    archive:Mapping[str,Any], *, buyer_capacity:Mapping[str,Any]|None,
    market_gps:Mapping[str,Any]|None, as_of:datetime,
    provider:Any=None, max_shadow_calls:int=0,
)->dict[str,Any]:
    if (not isinstance(as_of,datetime) or as_of.utcoffset() is None):
        raise ValueError("timezone-aware source-review time required")
    if (type(max_shadow_calls) is not int or not 0<=max_shadow_calls<=MAX_SHADOW
        or (max_shadow_calls and
            (provider is None or not callable(getattr(provider,"evaluate",None))))):
        raise ValueError("bounded explicit local model budget required")
    now=as_of.astimezone(timezone.utc)
    niches=_validate_archive(archive)
    gps_counts,gps_current=_validate_gps(market_gps,now)
    buyer=review_buyer_capacity(buyer_capacity,as_of=now)
    if (buyer["execution_authority"]!="none"
        or buyer["specific_buybox_verified"] is not False
        or buyer["lead_delivery_authorized"] is not False
        or buyer["payment_execution"] is not False):
        raise ValueError("buyer reader granted commercial authority")
    rows=[]
    for niche,count in niches.items():
        if niche.startswith("other_"):
            lane="REMAP_TAXONOMY"
        elif niche in REGULATED:
            lane="REGULATED_SOURCE_RIGHTS_REVIEW"
        elif gps_current and gps_counts.get(niche,0)>0 and count>=1000:
            lane="CORROBORATE_RECENT_ORIGINAL_DEMAND"
        elif count>=1000:
            lane="VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS"
        else:
            lane="BACKGROUND_RIGHTS_REVIEW"
        next_task=({
            "REMAP_TAXONOMY":"CLASSIFY_MISSING_BUSINESS_CATEGORY",
            "REGULATED_SOURCE_RIGHTS_REVIEW":"VERIFY_INDUSTRY_AND_DATA_USAGE_RESTRICTIONS",
            "CORROBORATE_RECENT_ORIGINAL_DEMAND":"INSPECT_INDEPENDENT_RECENT_PROCUREMENT_EVIDENCE",
            "VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS":"VERIFY_CURRENT_SOURCE_AND_LICENSED_BUSINESS_IDENTITY",
            "BACKGROUND_RIGHTS_REVIEW":"CHECK_ORIGINAL_SOURCE_AND_REUSE_RIGHTS",
        })[lane]
        rows.append({
            "niche":niche,
            "historical_prospect_rows":count,
            "recent_gps_observed_acquisitions_not_buyer_demand":(
                gps_counts.get(niche,0) if gps_current else None),
            "research_lane":lane,
            "next_research_task":next_task,
            "scope":"HISTORICAL_SECTOR_AGGREGATE",
            "individual_qualified_leads":0,
            "current_contactable_records_verified":False,
            "specific_buyer_buybox_verified":False,
            "local_model_suggestion":None,
            "shadow_status":"NOT_CALLED",
            "auto_contact_authority":False,
        })
    order={
        "CORROBORATE_RECENT_ORIGINAL_DEMAND":0,
        "VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS":1,
        "REGULATED_SOURCE_RIGHTS_REVIEW":2,
        "BACKGROUND_RIGHTS_REVIEW":3,
        "REMAP_TAXONOMY":4,
    }
    rows.sort(key=lambda x:(order[x["research_lane"]],
                            -x["historical_prospect_rows"],x["niche"]))
    attempts=0
    # All evidence rows are validated before the optional local model call.
    for row in rows:
        if attempts>=max_shadow_calls:
            break
        if row["research_lane"] not in (
            "CORROBORATE_RECENT_ORIGINAL_DEMAND",
            "VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS",
        ):
            continue
        attempts+=1
        request=TypedDecisionRequest(
            task_key="sector_research_priority",
            decision_schema_ref=SCHEMA,
            state_ref="sector:"+row["niche"],
            state={
                "niche":row["niche"],
                "historic_record_count":row["historical_prospect_rows"],
                "recent_gps_observations":row["recent_gps_observed_acquisitions_not_buyer_demand"] or 0,
                "recent_gps_snapshot_current":gps_current,
                "current_prospect_identity_verified":False,
                "buyer_buybox_verified":False,
                "rights_verified":False,
            },
            allowed_labels=MODEL_LABELS,
            risk_class="medium",
            instructions=(
                "Suggest one internal evidence review lane only. Historical "
                "inventory volume and market GPS activity are not customer "
                "demand, verified identity, contact rights or payable capacity."
            ),
        )
        try:
            result=provider.evaluate(request)
            checked=review_typed_decision_result(
                request=request,result=result,confidence_threshold=.8)
            if (result.shadow_only is not True
                or result.execution_authority!="none"
                or result.provider_key not in ("laya_http","laya")
                or not isfinite(result.latency_ms)):
                raise ValueError("not an authorised local shadow model")
            row["local_model_suggestion"]=result.label
            row["shadow_status"]=(
                "ESCALATE_SHADOW_TO_REVIEW" if checked["requires_escalation"]
                else "SHADOW_SUGGESTION_REVIEW_ONLY")
            row["model_reported_latency_ms"]=result.latency_ms
        except Exception:
            row["shadow_status"]="SHADOW_UNAVAILABLE_HELD"
    owners={
        "CORROBORATE_RECENT_ORIGINAL_DEMAND":(
            "existing_research_and_intent_brain",
            "independently_verified_recent_procurement_source_and_original_context"),
        "VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS":(
            "existing_data_quality_and_research",
            "restricted_current_cohort_rights_and_canonical_business_provenance"),
        "REGULATED_SOURCE_RIGHTS_REVIEW":(
            "existing_editorial_and_compliance_reviewer",
            "documented_industry_rules_and_permissioned_use_evidence"),
        "BACKGROUND_RIGHTS_REVIEW":(
            "existing_research_source_intelligence",
            "source_custody_and_dated_original_rights_review"),
        "REMAP_TAXONOMY":(
            "existing_prospect_data_quality_owner",
            "original_sector_taxonomy_and_low_frequency_classification_audit"),
    }
    review_packets=[]
    for lane in order:
        members=[r for r in rows if r["research_lane"]==lane]
        if not members:
            continue
        owner,needed=owners[lane]
        review_packets.append({
            "lane":lane,
            "existing_owner":owner,
            "source_niche_count":len(members),
            "historical_rows_needing_research":sum(
                r["historical_prospect_rows"] for r in members),
            "required_independent_evidence":needed,
            "tenant_identity_verified":False,
            "real_buyer_demand_verified":False,
            "payable_buyer_capacity_verified":False,
            "dispatch_authorized":False,
            "crm_or_outbound_authority":False,
        })
    return {
        "schema_version":SCHEMA,
        "status":"AUDITED_HISTORICAL_SECTOR_RESEARCH_QUEUE_ONLY",
        "mode":"OBSERVE",
        "historical_archive_rows":archive["source_counted_copy_rows"],
        "historical_record_count_is_not_current_prospect_count":True,
        "archive_id_set_matched":True,
        "sector_count":len(rows),
        "market_gps_snapshot_current":gps_current,
        "current_market_observations_are_not_buyer_intent":True,
        "buyer_capacity_source_status":buyer["status"],
        "specific_buyer_capacity_verified":False,
        "sector_research_rows":rows,
        "research_lane_counts":dict(sorted(Counter(r["research_lane"] for r in rows).items())),
        "existing_owner_review_packets":review_packets,
        "local_shadow_attempts":attempts,
        "personal_records_exported":0,
        "prospects_scored_individually":0,
        "verified_contactable_leads":0,
        "automatic_research_dispatch":False,
        "outreach_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }
