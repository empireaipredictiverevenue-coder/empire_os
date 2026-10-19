"""Predictive customer value outcome readiness from existing *aggregate* owners.

Reads no private commercial records, customer identifiers or seller events.
No cross-pipeline cohort join or inference of verified payment from catalogue
counts, bookings, public intent or staged model probabilities.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
import json

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_customer_value_commerce_evidence import OWNER

SCHEMA="empire.predictive.customer_value_outcome_readiness.v1"
SOURCES={
    "intelligence":("runtime/predictive_intelligence/latest.json","empire.predictive_intelligence.v1","generated_at"),
    "capacity":("runtime/buyer_capacity_readiness/latest.json","empire.buyer_capacity_readiness.v1","observed_at"),
}
MAX_BYTES=3_000_000


def _hold(reason: str) -> dict[str,Any]:
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"CANONICAL_AGGREGATE_SOURCE_HOLD",
        "hold_code":reason,
        "predictive_source_outcome_count":None,
        "probability_ready_product_count":None,
        "canonical_catalog_products_not_proven_sales":None,
        "canonical_capacity_terms_verified_count":None,
        "original_prediction_registry_enabled_verified":False,
        "registered_prospective_value_pilot_count":None,
        "authenticated_product_app_service_purchases":None,
        "authenticated_customer_value_measurements":None,
        "model_outcome_calibration_authorized":False,
        "customer_revenue_or_savings_verified_by_this_check":False,
        "next_owner":"existing_predictive_scientific_quant_and_commerce_owners",
        "next_action":"RESTORE_AGGREGATE_SOURCE_CUSTODY",
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }


def review_customer_value_outcome_readiness(
    sources: Mapping[str, Mapping[str,Any]], *, as_of:datetime,
) -> dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware research snapshot clock required")
    if not isinstance(sources,Mapping) or set(sources)!=set(SOURCES):
        return _hold("EXACT_EXISTING_AGGREGATE_OWNERS_REQUIRED")
    now=as_of.astimezone(timezone.utc)
    for name,(_,schema,clock) in SOURCES.items():
        src=sources[name]
        if (not isinstance(src,Mapping)
                or src.get("schema_version")!=schema
                or src.get("mode")!="OBSERVE"
                or src.get("execution_authority")!="none"):
            return _hold("UNTRUSTED_"+name.upper()+"_SNAPSHOT")
        try:
            observed=_time(src.get(clock))
        except ValueError:
            return _hold("INVALID_"+name.upper()+"_TIMESTAMP")
        if not timedelta(0)<=now-observed<=timedelta(hours=8):
            return _hold("STALE_"+name.upper()+"_SNAPSHOT")
    quant=sources["intelligence"]
    buyer=sources["capacity"]
    keys=[
        (quant,"source_outcome_count"),(quant,"probability_ready_product_count"),
        (quant,"verified_catalog_product_count"),(buyer,"buyers_seen"),
        (buyer,"terms_verified"),(buyer,"capacity_verified"),(buyer,"fully_activated")
    ]
    if any(type(src.get(key)) is not int or not 0<=src[key]<=100000
           for src,key in keys):
        return _hold("INCONSISTENT_OWNER_OBSERVATION_COUNTS")
    if (quant["probability_ready_product_count"]>quant["verified_catalog_product_count"]
            or buyer["fully_activated"]>buyer["buyers_seen"]
            or buyer["terms_verified"]>buyer["buyers_seen"]
            or buyer["capacity_verified"]>buyer["buyers_seen"]):
        return _hold("OWNER_COUNTERS_CONTRADICT_ORIGINAL_POPULATION")
    if (quant.get("model_weight_mutation") is not False
            or quant.get("unverified_pipeline_state_used_as_outcome") is not False
            or buyer.get("payment_action") is not False
            or buyer.get("revenue_recognition") is not False):
        return _hold("OWNER_REPORTS_UNSUPPORTED_COMMERCIAL_AUTHORITY")
    blockers=[]
    if quant["source_outcome_count"]==0:
        blockers.append("NO_SOURCE_OUTCOMES_IN_PREDICTIVE_SNAPSHOT")
    if quant["probability_ready_product_count"]==0:
        blockers.append("NO_PROBABILITY_READY_PRODUCT_MODELS")
    if buyer["terms_verified"]==0:
        blockers.append("NO_BUYER_TERMS_VERIFIED_IN_CAPACITY_SNAPSHOT")
    if buyer["capacity_verified"]==0:
        blockers.append("NO_BUYER_CAPACITY_VERIFIED_IN_CAPACITY_SNAPSHOT")
    blockers.extend((
        "REAL_PRODUCT_APP_SERVICE_OWNER_RECEIPTS_NOT_CONNECTED_TO_THIS_BRIDGE",
        "ORIGINAL_PROSPECTIVE_REGISTRY_AND_MODEL_ATTESTATION_NOT_PROVEN",
        "CUSTOMER_VALUE_BASELINE_CONTROL_AND_CONSENT_NOT_AUTHENTICATED",
    ))
    return {
        **_hold("NONE"),
        "status":"CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED",
        "hold_code":None,
        "predictive_source_outcome_count":quant["source_outcome_count"],
        "probability_ready_product_count":quant["probability_ready_product_count"],
        "canonical_catalog_products_not_proven_sales":quant["verified_catalog_product_count"],
        "buyer_inventory_records_not_authenticated_purchasers":buyer["buyers_seen"],
        "canonical_capacity_terms_verified_count":buyer["terms_verified"],
        "canonical_capacity_verified_count":buyer["capacity_verified"],
        "canonical_fully_activated_buyer_count":buyer["fully_activated"],
        "source_owner_observations_are_not_atomic":True,
        "source_outcome_count_is_exhaustive_sales_count":False,
        "owner_receipt_sources_to_integrate":dict(OWNER),
        "remaining_evidence_gates":blockers,
        "next_action":"CONNECT_AUTHORITATIVE_OWNER_PURCHASE_AND_CUSTOMER_VALUE_RECEIPTS_THEN_REGISTER_ORIGINAL_FORECAST",
    }


def review_customer_value_outcome_readiness_runtime(
    repo_root:str | Path, *,as_of:datetime,
) -> dict[str,Any]:
    root=Path(repo_root).resolve()
    collected={}
    for name,(rel,_schema,_clock) in SOURCES.items():
        p=root / rel
        try:
            if ((root/"runtime").is_symlink() or p.parent.is_symlink()
                    or p.is_symlink() or not p.is_file()
                    or not 0<p.stat().st_size<=MAX_BYTES):
                return _hold("UNAVAILABLE_"+name.upper()+"_SOURCE")
            row=json.loads(p.read_text(encoding="utf-8"))
        except (OSError,UnicodeError,ValueError):
            return _hold("UNREADABLE_"+name.upper()+"_SOURCE")
        collected[name]=row
    return review_customer_value_outcome_readiness(collected,as_of=as_of)
