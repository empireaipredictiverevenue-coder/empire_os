"""Read-only reply lineage and producer compatibility for Predictive territories.

Uses the original restricted market/lineage aggregate; a reply's outbound
intent pointer or positive self-classification proves neither first-party
buyer consent nor an accepted buybox. Never promote this to paid demand or
Quant calibration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from hashlib import sha256
import json

from empire_os.predictive_market_evidence_binding import (
    SCHEMA as TERRITORY_SCHEMA, SOURCE_SCHEMA,
    review_revenue_gps_territory_evidence_runtime,
    review_revenue_gps_territory_evidence,
)
from empire_os.predictive_customer_value_demand import _time

SCHEMA="empire.predictive_revenue.restricted_reply_lineage_handoff.v1"
PRODUCER_SCHEMA="empire.predictive_revenue.market_producer_compatibility.v1"
LINEAGE_SCHEMA="empire.market_gps_restricted_reply_lineage.v1"
EXPECTED_WINDOW=90
MAX_BYTES=3_000_000
SOURCE_REL="runtime/market_sweeps/revenue_gps_latest.json"
CODE_REL="empire_os/market_sweep_revenue_gps.py"
COUNT_FIELDS=(
    "reply_records_observed","reply_records_with_intent_pointer",
    "reply_records_matched_to_intent","reply_records_matched_to_prospect",
    "reply_records_missing_intent_pointer",
    "reply_records_with_unmatched_intent",
    "reply_records_with_unmatched_prospect",
    "positive_classification_records_unverified",
)
NEGATIVE_FLAGS=(
    "original_provider_message_id_checked",
    "canonical_contact_identity_verified",
    "provider_thread_binding_verified",
    "tenant_binding_verified",
    "buyer_intent_verified",
    "commercial_demand_inferred",
)


def _hold(reason:str)->dict[str,Any]:
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"RESTRICTED_REPLY_PROVENANCE_HOLD",
        "hold_code":reason,
        "original_territory_revision_sha256":None,
        "reply_lineage_window_days":None,
        "territory_research_window_days":None,
        "source_reported_lineage_counts":None,
        "canonical_provider_message_authenticated":False,
        "direct_buying_role_authenticated":False,
        "tenant_and_buyer_contact_authenticated":False,
        "individual_market_reply_attribution_proven":False,
        "independent_committed_buyer_count":None,
        "paid_order_count":None,
        "original_quant_forecast_registered":False,
        "calibration_training_allowed":False,
        "outbound_allowed":False,
        "database_writes":False,"execution_authority":"none",
    }


def review_restricted_reply_lineage(
    source:Mapping[str,Any],territory:Mapping[str,Any], *,
    as_of:datetime,
)->dict[str,Any]:
    """Cohort-safe validation without attributing 90-day replies to a 7-day metro."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware lineage-review clock required")
    if (not isinstance(source,Mapping)
            or source.get("schema_version")!=SOURCE_SCHEMA
            or source.get("restricted_source_scope")!="RESTRICTED_AGGREGATES_ONLY"
            or source.get("mode")!="OBSERVE"
            or source.get("execution_authority")!="none"
            or source.get("inbound_reply_authenticity_verified") is not False
            or source.get("raw_reply_records_are_commercial_proof") is not False):
        return _hold("UNTRUSTED_RESTRICTED_REPLIES_OR_SOURCE")
    if (not isinstance(territory,Mapping)
            or territory.get("schema_version")!=TERRITORY_SCHEMA
            or territory.get("status")!="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY"
            or territory.get("execution_authority")!="none"):
        return _hold("UNREADY_OR_STALE_TERRITORY_EVIDENCE")
    try:
        source_at=_time(source.get("generated_at"))
        territory_at=_time(territory.get("source_generated_at"))
    except ValueError:
        return _hold("INCONSISTENT_SOURCE_EPOCHS")
    if source_at!=territory_at or source_at>as_of.astimezone(timezone.utc):
        return _hold("INCONSISTENT_SOURCE_EPOCHS")
    original=review_revenue_gps_territory_evidence(source,as_of=as_of)
    if (original.get("status")!="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY"
            or original.get("source_revision_fingerprint")
               !=territory.get("source_revision_fingerprint")
            or original.get("territory_research_cards")
               !=territory.get("territory_research_cards")):
        return _hold("TERRITORY_REVISION_OR_CONTENT_DRIFT")
    lineage=source.get("restricted_reply_lineage")
    if (not isinstance(lineage,Mapping)
            or lineage.get("schema")!=LINEAGE_SCHEMA
            or lineage.get("execution_authority")!="none"
            or lineage.get("read_only_aggregate") is not True
            or any(lineage.get(flag) is not False for flag in NEGATIVE_FLAGS)):
        return _hold("UNTRUSTED_OR_MISSING_PROVIDER_LINEAGE")
    window=lineage.get("window_days")
    source_window=source.get("window_days")
    if (type(window) is not int or window!=EXPECTED_WINDOW
            or type(source_window) is not int or not 1<=source_window<=31
            or source_window!=territory.get("territory_research_cards",[{}])[0].get("source_window_days")):
        return _hold("INCOMPATIBLE_SOURCE_OBSERVATION_WINDOWS")
    if any(type(lineage.get(k)) is not int or not 0<=lineage[k]<=10000000
           for k in COUNT_FIELDS):
        return _hold("INVALID_REPLY_LINEAGE_COUNTERS")
    total,pointed,intent,prospect,missing,unmatched_i,unmatched_p,positive=(
        lineage[key] for key in COUNT_FIELDS
    )
    if not (prospect<=intent<=pointed<=total
            and missing==total-pointed
            and unmatched_i==pointed-intent
            and unmatched_p==intent-prospect
            and positive<=total):
        return _hold("CONTRADICTORY_PROVIDER_REPLY_LINEAGE")
    if (type(source.get("unverified_reply_records_present")) is not int
            or type(source.get("unverified_positive_classifications_present")) is not int
            or source["unverified_reply_records_present"]!=0
            or source["unverified_positive_classifications_present"]!=0):
        return _hold("UNVERIFIED_MARKET_REPLIES_OR_CLASSIFICATIONS_PRESENT")
    if (territory.get("reported_commercial_demand_market_count")!=0
            or any(
                card.get("source_reported_commercial_replies_not_authenticated")!=0
                or card.get("source_reported_commercial_terms_not_accepted")!=0
                or card.get("source_reported_payment_event_count_not_independently_authenticated")!=0
                for card in territory.get("territory_research_cards",())
            )):
        # This adapter is scoped to the currently restricted research-only
        # materializer, not authenticated paid source-event cohorts.
        return _hold("RESTRICTED_MARKET_HAD_UNEXPECTED_COMMERCIAL_CLAIM")
    missing_proof=[
        "PROVIDER_MESSAGE_ID_NOT_AUTHENTICATED",
        "PROVIDER_THREAD_NOT_AUTHENTICATED",
        "ORIGINAL_CONTACT_ID_NOT_AUTHENTICATED",
        "TENANT_BINDING_NOT_AUTHENTICATED",
        "BUYING_ROLE_TERMS_AND_CAPACITY_NOT_AUTHENTICATED",
        "REPLIES_NOT_ATTRIBUTED_TO_EXACT_TERRITORY_AND_WINDOW",
        "NO_PURCHASE_REFUND_SETTLEMENT_ORIGINAL_FORECAST_LINK",
    ]
    return {
        **_hold("NONE"),
        "status":"RESTRICTED_REPLY_PROVENANCE_RESEARCH_ONLY",
        "hold_code":None,
        "original_territory_revision_sha256":territory["source_revision_fingerprint"],
        "reply_lineage_window_days":window,
        "territory_research_window_days":source_window,
        "source_reported_lineage_counts":{
            "reply_records_observed":total,
            "reply_records_with_intent_pointer":pointed,
            "reply_records_matched_to_intent":intent,
            "reply_records_matched_to_prospect":prospect,
            "reply_records_missing_intent_pointer":missing,
            "reply_records_with_unmatched_intent":unmatched_i,
            "reply_records_with_unmatched_prospect":unmatched_p,
            "positive_classification_records_unverified":positive,
        },
        "reply_lineage_count_is_a_proven_unique_buyer_count":False,
        "reply_lineage_can_be_mapped_to_territory_research":False,
        "matched_outbound_intent_is_authenticated_buyer_intent":False,
        "research_owner_evidence_requests":missing_proof,
        "next_owner":"existing_buyer_source_message_contact_and_tenant_verifier",
        "next_action":"AUTHENTICATE_PROVIDER_REPLY_LINEAGE_AND_FIRST_PARTY_BUYING_ROLE",
    }


def review_restricted_reply_lineage_runtime(
    repo_root:str|Path, *, as_of:datetime,
)->dict[str,Any]:
    root=Path(repo_root).resolve()
    p=root/SOURCE_REL
    try:
        if ((root/"runtime").is_symlink() or p.parent.is_symlink()
                or p.is_symlink() or not p.is_file()
                or not 0<p.stat().st_size<=MAX_BYTES):
            return _hold("SOURCE_SNAPSHOT_UNAVAILABLE")
        source=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        return _hold("SOURCE_SNAPSHOT_UNREADABLE")
    territory=review_revenue_gps_territory_evidence_runtime(root,as_of=as_of)
    return review_restricted_reply_lineage(source,territory,as_of=as_of)


def _producer_status(original_root:str|Path)->dict[str,Any] | None:
    root=Path(original_root).resolve()
    p=root/CODE_REL
    try:
        if (p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=500000):
            return None
        content=p.read_text(encoding="utf-8")
    except (OSError,UnicodeError):
        return None
    return {
        "digest":sha256(content.encode()).hexdigest(),
        "deprecated_rpc_dependency_present":"get_market_sweep_revenue_gps(" in content,
        "restricted_market_query_imported":"market_gps_restricted_reader" in content,
        "restricted_market_query_called":"RESTRICTED_MARKET_QUERY" in content,
        "read_only_transaction_explicit":"SET TRANSACTION READ ONLY" in content,
        "reply_lineage_query_called":"REPLY_LINEAGE_QUERY" in content,
        "source_scope_and_lineage_projected":all(
            marker in content
            for marker in ("restricted_source_scope","restricted_reply_lineage",
                           "unverified_positive_classifications_present")
        ),
    }


def review_market_gps_merge_compatibility(
    feature_root:str|Path, production_root:str|Path,
)->dict[str,Any]:
    """Static compatibility audit; no SQL, role change, git merge or source edit."""
    feature=_producer_status(feature_root)
    prod=_producer_status(production_root)
    if feature is None or prod is None:
        return {
            "schema_version":PRODUCER_SCHEMA,"status":"SOURCE_CODE_UNAVAILABLE",
            "merge_source_producer_authorized":False,
            "execution_authority":"none","database_writes":False,
        }
    required=(
        "restricted_market_query_imported","restricted_market_query_called",
        "read_only_transaction_explicit","reply_lineage_query_called",
        "source_scope_and_lineage_projected",
    )
    prod_safe=(not prod["deprecated_rpc_dependency_present"]
               and all(prod[key] for key in required))
    feature_safe=(not feature["deprecated_rpc_dependency_present"]
                  and all(feature[key] for key in required))
    compatible=prod_safe and feature_safe
    blockers=[]
    if not prod_safe:
        blockers.append("PRODUCTION_RESTRICTED_MARKET_PRODUCER_POLICY_NOT_RECOGNIZED")
    if not feature_safe:
        blockers.append("FEATURE_MARKET_PRODUCER_MUST_NOT_REPLACE_RESTRICTED_PRODUCTION_SOURCE")
    if feature["digest"]!=prod["digest"]:
        blockers.append("SOURCE_OWNER_RECONCILE_PRODUCER_CODE_REVISION_BEFORE_MERGE")
    return {
        "schema_version":PRODUCER_SCHEMA,
        "mode":"OBSERVE",
        "status":"SOURCE_OWNER_MERGE_REVIEW_REQUIRED"
            if blockers else "STATIC_SOURCE_COMPATIBILITY_REVIEWED",
        "production_source_uses_restricted_read_only_query":prod_safe,
        "feature_producer_uses_production_restricted_contract":feature_safe,
        "exact_producer_code_revision_equal":feature["digest"]==prod["digest"],
        "production_source_sha256":prod["digest"],
        "feature_source_sha256":feature["digest"],
        "blockers":blockers,
        "merge_source_producer_authorized":False,
        "source_owner_writes_performed":False,
        "database_writes":False,
        "execution_authority":"none",
    }
