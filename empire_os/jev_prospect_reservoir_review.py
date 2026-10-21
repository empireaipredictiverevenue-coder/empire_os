"""Jev executive prospect-reservoir reconciliation across original aggregates.

A historic EmpireDB 32,899-row prospect snapshot is not a live, uniquely
qualified, contactable lead inventory. Do not join permit recovery, leads
runtime or market-window counts without original per-ID provenance. Never
emit contact details or infer buyer/consent/revenue from counts.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping

SCHEMA="empire.jev.prospect_reservoir_review.v1"
MAX_AGE=timedelta(hours=4)


def _table(rows:Any,name:str)->Mapping[str,Any]:
    if not isinstance(rows,list):
        raise ValueError("historical table audit missing")
    found=[x for x in rows if isinstance(x,Mapping) and x.get("table")==name]
    if len(found)!=1:
        raise ValueError("historical prospect table not uniquely identified")
    return found[0]


def _bounded_count(value:Any)->int:
    if type(value) is not int or not 0<=value<=10_000_000:
        raise ValueError("source inventory count invalid")
    return value


def _source_clock(value:Any,now:datetime)->bool:
    try:
        stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
        return (stamp.utcoffset() is not None
                and timedelta(0)<=now-stamp.astimezone(timezone.utc)<=MAX_AGE)
    except (TypeError,ValueError,AttributeError,OverflowError):
        return False


def audit_jev_prospect_reservoir(
    *, historic_verified:Mapping[str,Any],
    historic_dual_read:Mapping[str,Any],
    leads_runtime:Mapping[str,Any]|None,
    legacy_permit:Mapping[str,Any]|None,
    current_markets:Mapping[str,Any]|None,
    as_of:datetime,
)->dict[str,Any]:
    if (not isinstance(as_of,datetime) or as_of.utcoffset() is None):
        raise ValueError("timezone-aware audit required")
    now=as_of.astimezone(timezone.utc)
    if (not isinstance(historic_verified,Mapping)
        or historic_verified.get("schema_version")!="empire.shadow-independent-verify.v1"
        or historic_verified.get("verified") is not True
        or historic_verified.get("read_only") is not True
        or historic_verified.get("canonical_backend_unchanged") is not True
        or historic_verified.get("production_cutover_authority") is not False
        or not isinstance(historic_dual_read,Mapping)
        or historic_dual_read.get("schema_version")!="empire.dual-read-compare.v1"
        or historic_dual_read.get("all_equal") is not True
        or historic_dual_read.get("identity_drift_tables")!=0
        or historic_dual_read.get("dual_write_enabled") is not False
        or historic_dual_read.get("read_only") is not True
        or historic_dual_read.get("production_cutover_authority") is not False):
        raise ValueError("historical EmpireDB count lacks independent verified source")
    original=_table(historic_verified.get("tables"),"prospects")
    comparison=_table(historic_dual_read.get("tables"),"prospects")
    count=_bounded_count(original.get("source_rows"))
    if (count!=_bounded_count(original.get("target_rows"))
        or count!=_bounded_count(comparison.get("source_rows"))
        or count!=_bounded_count(comparison.get("target_rows"))
        or original.get("verified") is not True
        or comparison.get("equal") is not True
        or any(not isinstance(row.get(key),str) or
               len(row[key])!=64 or any(c not in "0123456789abcdef" for c in row[key])
               for row in (original,comparison)
               for key in ("source_pk_sha256","target_pk_sha256"))
        or len({original["source_pk_sha256"],original["target_pk_sha256"],
                comparison["source_pk_sha256"],comparison["target_pk_sha256"]})!=1):
        raise ValueError("historical source and target IDs do not reconcile")
    # The original DB-restore audit does not carry an authenticated live clock.
    # It cannot establish current prospect cardinality, freshness or source rights.
    result={
        "schema_version":SCHEMA,
        "status":"HISTORIC_PROSPECT_RESERVOIR_VERIFIED_CURRENT_ELIGIBILITY_UNKNOWN",
        "mode":"OBSERVE",
        "historical_empiredb_prospect_count":count,
        "historical_distinct_id_set_matched_between_snapshots":True,
        "historical_recovery_is_not_live_buyer_or_lead_proof":True,
        "current_empiredb_prospect_count":None,
        "current_empiredb_reservoir_refresh_verified":False,
        "full_reservoir_commercial_rights_verified":False,
        "existing_leads_control_status":"MISSING_OR_UNTRUSTED",
        "existing_leads_control_rows":None,
        "existing_leads_unique_ids":None,
        "lead_status_converted_unverified_count":None,
        "lead_outcome_linked_count_not_paid_revenue":None,
        "lead_duplicate_email_row_observations":None,
        "lead_duplicate_phone_row_observations":None,
        "permit_recovery_status":"MISSING_OR_UNTRUSTED",
        "permit_recovery_local_rows":None,
        "permit_current_verified_project_only":None,
        "permit_current_verified_owner_identified":None,
        "permit_scan_complete":False,
        "recent_market_aggregate_status":"MISSING_OR_UNTRUSTED",
        "recent_market_window_days":None,
        "recent_market_segment_count":None,
        "recent_market_observed_acquisition_total":None,
        "overlap_between_sources_proven":False,
        "counting_populations_additive":False,
        "bulk_qualified_or_contactable_lead_total_proven":False,
        "individual_consent_and_suppression_cleared":False,
        "qualified_records_for_mass_jev_inference":0,
        "automatic_outreach_authorized":False,
        "buyers_or_money_verified":False,
        "canonical_crm_rows_mutated":0,
        "database_writes":False,
        "execution_authority":"none",
    }
    if isinstance(leads_runtime,Mapping):
        data=leads_runtime
        if (data.get("schema_version")=="empire-leads-runtime-control-v2"
            and data.get("mode")=="OBSERVE" and data.get("lane")=="leads"
            and data.get("status")=="VERIFIED_RUNTIME"
            and _source_clock(data.get("generated_at"),now)
            and isinstance(data.get("governance"),Mapping)
            and all(data["governance"].get(k) is False for k in (
                "action_authority_granted","db_write","lead_mutation","outbound"))
            and data.get("canonical_id_primary_key") is True):
            total=_bounded_count(data.get("lead_count"))
            unique=_bounded_count(data.get("canonical_id_distinct_count"))
            unverified_status=_bounded_count(data.get("status_converted_count"))
            linked=_bounded_count(data.get("real_conversion_count"))
            duplicates=_bounded_count(data.get("duplicate_email_row_count"))
            phone=_bounded_count(data.get("duplicate_phone_row_count"))
            if (unique<=total and unverified_status<=total
                and linked<=total and duplicates<=total and phone<=total):
                result.update({
                    "existing_leads_control_status":"CURRENT_AGGREGATE_OBSERVED_NOT_RESERVOIR_JOINED",
                    "existing_leads_control_rows":total,
                    "existing_leads_unique_ids":unique,
                    "lead_status_converted_unverified_count":unverified_status,
                    "lead_outcome_linked_count_not_paid_revenue":linked,
                    "lead_duplicate_email_row_observations":duplicates,
                    "lead_duplicate_phone_row_observations":phone,
                })
    if isinstance(legacy_permit,Mapping):
        row=legacy_permit
        if (row.get("schema_version")=="empire.legacy-permit-inventory.v1"
            and row.get("mode")=="OBSERVE"
            and row.get("canonical_database_write_performed") is False
            and row.get("canonical_promotion_performed") is False
            and row.get("outbound_sent") is False
            and row.get("actual_revenue") is False):
            total=_bounded_count(row.get("unique_inventory_records"))
            owner=_bounded_count(row.get("verified_current_owner_identified"))
            project=_bounded_count(row.get("verified_current_project_only"))
            valid=_bounded_count(row.get("verified_current_inventory"))
            if owner+project==valid and valid<=total:
                result.update({
                    "permit_recovery_status":"LOCAL_LEGACY_PERMIT_INVENTORY_NOT_LEAD_POOL",
                    "permit_recovery_local_rows":total,
                    "permit_current_verified_project_only":project,
                    "permit_current_verified_owner_identified":owner,
                    "permit_scan_complete":row.get("full_scan_complete") is True,
                })
    if isinstance(current_markets,Mapping):
        x=current_markets
        markets=x.get("markets")
        if (x.get("schema_version")=="empire.market_sweep_revenue_gps.v1"
            and x.get("mode")=="OBSERVE"
            and x.get("execution_authority")=="none"
            and x.get("buyer_intent_inferred") is False
            and x.get("commercial_intent_inferred") is False
            and x.get("revenue_inferred") is False
            and _source_clock(x.get("generated_at"),now)
            and isinstance(markets,list) and len(markets)<=100
            and type(x.get("window_days")) is int
            and 1<=x["window_days"]<=365):
            try:
                recent=sum(_bounded_count(m.get("prospect_count"))
                           for m in markets if isinstance(m,Mapping))
                if len([m for m in markets if isinstance(m,Mapping)])!=len(markets):
                    raise ValueError("untrusted market row")
            except ValueError:
                pass
            else:
                result.update({
                    "recent_market_aggregate_status":"RESTRICTED_TIME_WINDOW_RESEARCH_ONLY",
                    "recent_market_window_days":x["window_days"],
                    "recent_market_segment_count":len(markets),
                    "recent_market_observed_acquisition_total":recent,
                })
    result["priority_review_tasks"]=[
        "VERIFY_CURRENT_CANONICAL_PROSPECT_COUNT_WITH_RESTRICTED_DB_READER",
        "CLASSIFY_ORIGINAL_ROW_ORIGINS_AND_PERMITTED_PURPOSES",
        "AUDIT_DUPLICATES_AND_CANONICAL_IDENTITY_CROSS_SOURCE",
        "VALIDATE_RECENT_INDEPENDENT_BUSINESS_AND_DEMAND_EVIDENCE",
        "REVIEW_BUYER_CAPACITY_TERMS_DELIVERY_AND_CONSENT_SUPPRESSION",
    ]
    return result
