"""Original NWS source evidence -> existing PRIME source observatory.

Consumes the already-approved NWS/offline universal-custody review *contract*
without fetching, writing, scheduling, predicting, identifying customers or
activating economic signals. This is a read model, not another data warehouse.
No input source's HTTPS claims, buyer flags or tenant IDs establish authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Any

from empire_os.nws_official_source_provenance import SCHEMA as NWS_SCHEMA
from empire_os.universal_source_custody_review import SCHEMA as CUSTODY_SCHEMA

SCHEMA = "empire.predictive_cloud.official_source_observatory.v1"
MAX_REVIEWED = 80
MAX_REJECTIONS = 100
MAX_SOURCE_AGE_SECONDS = 86400


def _stamp(value: Any) -> datetime:
    if type(value) is str:
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("source timestamp invalid") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("source timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _bool_false(obj: Mapping[str, Any], fields: tuple[str, ...]) -> None:
    if any(obj.get(field) is not False for field in fields):
        raise ValueError("official source review cannot assert economic or execution authority")


def _not_connected() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "official_source": "noaa_nws",
        "status": "NOT_CONNECTED",
        "source_references_reviewed": None,
        "rejected_observations": None,
        "freshness": "UNKNOWN",
        "transport_observed_reported": False,
        "source_custody_independently_verified": False,
        "canonical_entity_or_tenant_verified": False,
        "economic_signal_admitted": False,
        "qualifying_commercial_opportunities": None,
        "buyer_intent_verified": False,
        "property_damage_verified": False,
        "revenue_verified": False,
        "source_observations_added_to_prime_scenarios": 0,
        "source_observations_promoted_to_opportunities": 0,
        "execution_authority": "none",
        "blockers": ["OFFICIAL_SOURCE_REVIEW_NOT_CONNECTED"],
    }


def review_official_source_for_prime(
    *, nws_review: Mapping[str, Any] | None, as_of: datetime,
) -> dict[str, Any]:
    """Counts only actual *review rows*, never calls them customers or leads.

    Caller-provided review objects are structurally validated but are not
    independently signed source receipts. Even a real official GET cannot
    prove geographic entity links or commercial causality.
    """
    now = _stamp(as_of)
    if nws_review is None:
        return _not_connected()
    if not isinstance(nws_review, Mapping):
        raise ValueError("original NWS review mapping required")
    if (nws_review.get("schema_version") != NWS_SCHEMA
            or nws_review.get("mode") != "OBSERVE"
            or nws_review.get("execution_authority") != "none"):
        raise ValueError("original NWS OBSERVE authority required")
    _bool_false(nws_review, (
        "canonical_source_registry_verified",
        "canonical_entity_tenant_binding_verified",
        "buyer_intent_verified",
        "property_damage_verified",
        "economic_signal_eligible",
        "recognized_revenue",
        "crm_written",
        "redis_written",
        "database_written",
        "notifications_sent",
        "outbound_sent",
    ))
    if nws_review.get("gpu_spend_cents") != 0 or type(nws_review.get("transport_observed")) is not bool:
        raise ValueError("NWS transport or zero-budget proof missing")
    if nws_review.get("source_adapter") != "existing_storm_predictor_and_spatial_physical_adapters":
        raise ValueError("original storm evidence adapter required")
    custody = nws_review.get("universal_custody_review")
    if not isinstance(custody, Mapping):
        raise ValueError("universal custody review required")
    if (custody.get("schema_version") != CUSTODY_SCHEMA
            or custody.get("mode") != "OBSERVE"
            or custody.get("execution_authority") != "none"):
        raise ValueError("original universal custody review required")
    _bool_false(custody, (
        "raw_provider_events_persisted", "redis_stream_written",
        "empiredb_tables_created", "empiredb_write",
        "vector_embeddings_created", "source_connections_activated",
        "new_revenue_pipeline_created", "crm_prospects_created",
        "buyers_verified", "payment_processing_enabled",
    ))
    if custody.get("recognized_revenue_cents") is not None or custody.get("gpu_spend_cents") != 0:
        raise ValueError("universal source review must not grant money authority")
    reviewed = custody.get("reviewed_sources")
    rejected = custody.get("rejections")
    shape_rejected = nws_review.get("shape_rejections")
    if (type(reviewed) is not list or len(reviewed) > MAX_REVIEWED
            or type(rejected) is not list or len(rejected) > MAX_REJECTIONS
            or type(shape_rejected) is not list or len(shape_rejected) > MAX_REJECTIONS):
        raise ValueError("bounded exact source/rejection arrays required")
    if (type(custody.get("source_count_structurally_reviewed")) is not int
            or custody["source_count_structurally_reviewed"] != len(reviewed)
            or type(custody.get("source_count_rejected")) is not int
            or custody["source_count_rejected"] != len(rejected)):
        raise ValueError("source count mismatch")
    if custody.get("category_counts") != ({"ENVIRONMENT": len(reviewed)} if reviewed else {}):
        raise ValueError("source niche count mismatch")
    generated = _stamp(custody.get("as_of"))
    if generated > now:
        raise ValueError("future source review")
    ids = set()
    for item in reviewed:
        if not isinstance(item, Mapping):
            raise ValueError("bounded NWS source evidence row required")
        fingerprint = item.get("evidence_fingerprint")
        if type(fingerprint) is not str or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("stable source reference fingerprint required")
        if fingerprint in ids:
            raise ValueError("duplicate official source reference")
        ids.add(fingerprint)
        if (item.get("provider") != "noaa_nws"
                or item.get("source_host") != "api.weather.gov"
                or item.get("category") != "ENVIRONMENT"
                or item.get("event_kind") != "WEATHER_ALERT"
                or item.get("stage") != "SOURCE_REFERENCE_REVIEW_ONLY"
                or item.get("access_status") != "OFFICIAL_API_POLICY_REVIEW"):
            raise ValueError("only original bounded NWS review rows allowed")
        for field in ("licensed_for_downstream_use",
                      "independent_source_verified",
                      "canonical_entity_resolved", "buyer_intent_verified",
                      "revenue_verified", "economic_signal_eligible",
                      "canonical_source_registry_verified",
                      "canonical_entity_tenant_binding_verified"):
            if item.get(field) is not False:
                raise ValueError("untrusted source row cannot promote authority")
        if item.get("commercial_authority") != "none" or item.get(
                "existing_storm_evidence_adapter_used") is not True:
            raise ValueError("original storm source review with no authority required")
        blockers = item.get("blockers")
        if (not isinstance(blockers, list)
                or "SOURCE_CUSTODY_NOT_INDEPENDENTLY_VERIFIED" not in blockers
                or "NOT_A_VERIFIED_BUYING_SIGNAL" not in blockers
                or "NOT_A_VERIFIED_REVENUE_EVENT" not in blockers):
            raise ValueError("source review missing hold markers")
        published = _stamp(item.get("published_at"))
        observed = _stamp(item.get("observed_at"))
        if published > observed or observed > generated:
            raise ValueError("chronology conflict in source reference")
    age_s = (now - generated).total_seconds()
    freshness = "STALE" if age_s > MAX_SOURCE_AGE_SECONDS else "RECENT_REVIEW_UNATTESTED"
    status = "STALE_SOURCE_REVIEW" if age_s > MAX_SOURCE_AGE_SECONDS else (
        "STRUCTURALLY_REVIEWED_NO_ECONOMIC_AUTHORITY" if reviewed
        else "REVIEWED_NO_CURRENT_SOURCE_RECORDS"
    )
    summary = _not_connected()
    summary.update({
        "status": status,
        "source_references_reviewed": len(reviewed),
        "rejected_observations": len(rejected) + len(shape_rejected),
        "freshness": freshness,
        "transport_observed_reported": nws_review["transport_observed"],
        "blockers": [
            "SOURCE_CUSTODY_AND_DATA_RIGHTS_NOT_INDEPENDENTLY_VERIFIED",
            "CANONICAL_SOURCE_ENTITY_TENANT_CAUSAL_LINK_UNPROVEN",
            "OFFICIAL_WEATHER_ALERT_IS_NOT_A_COMMERCIAL_SIGNAL",
            "VERIFIED_OUTCOMES_REQUIRED_BEFORE_ANY_REVENUE_FORECAST",
        ] + (["SOURCE_REVIEW_STALE"] if age_s > MAX_SOURCE_AGE_SECONDS else []),
    })
    return summary
