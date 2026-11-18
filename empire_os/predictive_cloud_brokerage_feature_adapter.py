"""Predictive Fabric's existing research-only brokerage feature adapter.

Consumes the original Brokerage -> Cloud nine-dataset research intake.
Revalidates each content-addressed object and source-owner receipt before
building typed, strictly non-predictive segmentation observations. This is
NOT a new forecast model, customer data reader, sales engine, or tenant API.

The original Predictive Fabric production bridge is the integration owner;
the immutable pinned model runner and authenticated forecast admission gates
remain unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from empire_os.data_brokerage_enterprise_feed import SOURCES
from empire_os.data_brokerage_enterprise_packaging import VIEWS
from empire_os.predictive_cloud_brokerage_research import (
    INDEX_PATH, SCHEMA as INDEX_SCHEMA, _atomic_secure, _read_receipt,
    _decode_csv, _read_source_bytes, _segments,
    read_internal_brokerage_rows,
)
from empire_os.predictive_cloud_fabric import (
    ExecutionAuthority, FabricCapability,
    PredictiveCloudFabricContext, TenantContextSource,
)

SCHEMA = "empire.predictive_cloud.brokerage_research_features.v1"
FEATURE_PATH = INDEX_PATH.parent / "research_features_latest.json"
CAPABILITY = FabricCapability(
    name="original_brokerage_private_research",
    allowed_actions=frozenset({"read:brokerage_research"}),
)
OBSERVE = "EMPIRE_INTERNAL_RESEARCH_OBSERVE"
MAX_FEATURE_SEGMENTS = 200


def _require_internal_context(context: PredictiveCloudFabricContext) -> None:
    if (type(context) is not PredictiveCloudFabricContext
            or context.authority is not ExecutionAuthority.OBSERVE
            or context.tenant_source is not TenantContextSource.NONE
            or context.tenant_id is not None
            or context.approved_gates
            or context.account_id is not None
            or context.buyer_id is not None
            or context.lead_id is not None
            or context.conversation_id is not None
            or not CAPABILITY.allows("read:brokerage_research", context=context)):
        raise PermissionError("PREDICTIVE_CLOUD_SYSTEM_OBSERVE_CONTEXT_REQUIRED")


def _canonical_feature_content(index: dict[str, Any],
                               verified: list[dict[str, Any]]) -> dict[str, Any]:
    segment_rows: list[dict] = []
    datasets: list[dict] = []
    for item in verified:
        datasets.append({
            "dataset_id": item["dataset_id"],
            "kind": item["kind"],
            "source_id": item["source_id"],
            "publisher": item["publisher"],
            "source_snapshot_sha256": item["source_snapshot_sha256"],
            "verified_data_sha256": item["sha256"],
            "observed_rows": item["rows"],
            "row_scope": item["research_scope"],
            "source_sample_not_full_population":
                item["sample_not_complete_population"],
            "observation_only": True,
            "verified_customer_demand": None,
            "commercial_licensing_cleared": False,
        })
        if item["kind"] == "derived_research_view":
            for part in item["segments"]:
                segment_rows.append({
                    "dataset_id": item["dataset_id"],
                    "source_id": item["source_id"],
                    "dimension": part["dimension"],
                    "segment_value": part["value"],
                    "observed_count": part["observed_sample_count"],
                    "metric": part["metric"],
                    "source_snapshot_sha256": item["source_snapshot_sha256"],
                    "derived_view_sha256": item["sha256"],
                    "observation_only": True,
                    "independent_buyer_demand_verified": False,
                    "commercial_forecast_input_admitted": False,
                })
    return {
        "dataset_count": len(datasets),
        "original_dataset_count": len([r for r in datasets if r["kind"] == "original_source"]),
        "derived_view_count": len([r for r in datasets if r["kind"] == "derived_research_view"]),
        "original_source_rows": sum(r["observed_rows"] for r in datasets if r["kind"] == "original_source"),
        "derived_view_rows": sum(r["observed_rows"] for r in datasets if r["kind"] == "derived_research_view"),
        "segments": sorted(segment_rows, key=lambda r: (
            r["dataset_id"], r["dimension"], r["segment_value"])),
        "datasets": sorted(datasets, key=lambda r: r["dataset_id"]),
        "source_and_derived_rows_additive": False,
        "measured_customer_conversion_probability": None,
        "confirmed_direct_buyer_demand": None,
        "verified_realized_revenue": None,
        "production_model_input_admitted": False,
        "model_training_authorized": False,
        "tenant_exposure_authorized": False,
        "public_analytics_api_authorized": False,
        "outbound_authorized": False,
        "research_only": True,
        "execution_authority": "none",
    }


def _verify_index_and_build(root: Path, *, now: datetime) -> dict[str, Any]:
    index = _read_receipt(root / INDEX_PATH, INDEX_SCHEMA)
    if (index.get("status") != "VERIFIED_BROKERAGE_RESEARCH_INPUTS_INTERNAL"
            or index.get("tenant_exposure_authorized") is not False
            or index.get("source_redistribution_authorized") is not False
            or index.get("customer_downloads_authorized") is not False
            or index.get("production_training_samples_admitted") != 0
            or index.get("execution_authority") != "none"):
        raise ValueError("PREDICTIVE_CLOUD_BROKERAGE_RESEARCH_INDEX_HELD")
    data = index.get("dataset_records")
    if (not isinstance(data, list) or len(data) != len(SOURCES) + len(VIEWS)):
        raise ValueError("BROKERAGE_RESEARCH_INVENTORY_INCOMPLETE")
    keys = [r.get("dataset_id") for r in data if isinstance(r, dict)]
    if set(keys) != set(SOURCES) | set(VIEWS) or len(keys) != len(data):
        raise ValueError("BROKERAGE_RESEARCH_SOURCE_INVENTORY_MISMATCH")
    checked: list[dict] = []
    for item in data:
        if (item.get("kind") not in ("original_source", "derived_research_view")
                or type(item.get("rows")) is not int
                or not 1 <= item["rows"] <= 100_000
                or item.get("source_evidence_digest_verified") is not True
                or item.get("tenant_exposure_allowed") is not False
                or item.get("commercial_feature_admission") != "RESEARCH_ONLY"
                or not isinstance(item.get("segments"), list)):
            raise ValueError("BROKERAGE_RESEARCH_OBJECT_SCHEMA_OR_AUTHORITY_HELD")
        ident = item["dataset_id"]
        if ((ident in SOURCES and (item["kind"] != "original_source"
                                   or item["source_id"] != ident
                                   or item["segments"]))
                or (ident in VIEWS and (item["kind"] != "derived_research_view"
                                        or item["source_id"] != VIEWS[ident]["source_id"]))):
            raise ValueError("BROKERAGE_RESEARCH_OBJECT_OWNER_MISMATCH")
        # Reuses the original Cloud's private row reader (no direct source
        # bypass). It validates source freshness, SHA256, original receipts,
        # encoded schema and each materialized row count.
        sample = read_internal_brokerage_rows(
            root, ident, limit=1, now=now,
            system_research_context=OBSERVE,
        )
        if (sample["dataset_sha256"] != item["sha256"]
                or sample["source_sha256"] != item["source_snapshot_sha256"]
                or sample["matched_rows_in_current_snapshot"] != item["rows"]
                or sample["research_only"] is not True
                or sample["training_authorized"] is not False):
            raise ValueError("BROKERAGE_RESEARCH_SOURCE_REVALIDATION_HOLD")
        if len(item["segments"]) > MAX_FEATURE_SEGMENTS:
            raise ValueError("BROKERAGE_RESEARCH_SEGMENT_COUNT_HELD")
        if ident in VIEWS:
            # The original Broker generated these segments. Independently
            # recompute them from the SHA-verified actual Cloud CSV to reject
            # forged, stale or statistically altered private index segments.
            p = root / INDEX_PATH.parent / "objects" / item["object_id"]
            raw = _read_source_bytes(p, item["sha256"])
            actual_rows = _decode_csv(raw, VIEWS[ident]["columns"], item["rows"])
            if _segments(ident, actual_rows) != item["segments"]:
                raise ValueError("BROKERAGE_RESEARCH_SEGMENT_RECOMPUTE_MISMATCH")
        for segment in item["segments"]:
            if (not isinstance(segment, dict)
                    or segment.get("not_independently_verified_customer_demand") is not True
                    or segment.get("commercial_forecast_input_admitted") is not False
                    or type(segment.get("observed_sample_count")) is not int
                    or not 0 <= segment["observed_sample_count"] <= 100_000
                    or not isinstance(segment.get("value"), str)
                    or not 0 < len(segment["value"]) <= 200
                    or not isinstance(segment.get("dimension"), str)
                    or not 0 < len(segment["dimension"]) <= 80
                    or not isinstance(segment.get("metric"), str)):
                raise ValueError("BROKERAGE_RESEARCH_SEGMENT_NOT_TRUSTED")
        checked.append(item)
    if not (len([x for x in checked if x["kind"] == "original_source"]) == 5
            and len([x for x in checked if x["kind"] == "derived_research_view"]) == 4):
        raise ValueError("BROKERAGE_RESEARCH_DATASET_COUNT_HOLD")
    return _canonical_feature_content(index, checked)


def _digest(doc: dict) -> str:
    return sha256(json.dumps(doc, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def build_internal_brokerage_features(root: str | Path, *,
                                    now: datetime | None = None) -> dict[str, Any]:
    """Rebuild verified provenance-bound observations; no production prediction."""
    current = now or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.utcoffset() is None:
        raise ValueError("AWARE_RESEARCH_OBSERVATION_CLOCK_REQUIRED")
    return _verify_index_and_build(Path(root).resolve(),
                                   now=current.astimezone(timezone.utc))


def refresh_internal_brokerage_features(root: str | Path, *,
                                       now: datetime | None = None,
                                       allow_noncanonical: bool = False) -> dict:
    """Existing brokerage owner only; idempotent, private, no new scheduler."""
    base = Path(root).resolve()
    if base != Path("/srv/empire_os") and not allow_noncanonical:
        return {"status": "NONCANONICAL_PRIVATE_RESEARCH_OWNER_HELD",
                "feature_segments": 0, "model_training_authorized": False}
    instant = now or datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.utcoffset() is None:
        raise ValueError("AWARE_RESEARCH_OBSERVATION_CLOCK_REQUIRED")
    validated = build_internal_brokerage_features(base, now=instant)
    semantic_hash = _digest(validated)
    path = base / FEATURE_PATH
    if path.is_file() and not path.is_symlink():
        old = _read_receipt(path, SCHEMA)
        if old.get("content_sha256") == semantic_hash:
            # No new data; preserve provenance and original generated_at.
            if old.get("features") == validated:
                return {
                    "status": "VERIFIED_UNCHANGED_CLOUD_RESEARCH_FEATURES",
                    "feature_segments": len(validated["segments"]),
                    "sources_verified": validated["original_dataset_count"],
                    "derived_views_verified": validated["derived_view_count"],
                    "feature_writes": 0,
                    "model_training_authorized": False,
                    "execution_authority": "none",
                }
    payload = {
        "schema": SCHEMA,
        "status": "VERIFIED_INTERNAL_CLOUD_RESEARCH_FEATURES",
        "generated_at": instant.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "source": str(INDEX_PATH),
        "content_sha256": semantic_hash,
        "features": validated,
        "tenant_exposure_authorized": False,
        "production_training_samples_admitted": 0,
        "execution_authority": "none",
    }
    _atomic_secure(path, (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode())
    return {
        "status": payload["status"],
        "feature_segments": len(validated["segments"]),
        "sources_verified": validated["original_dataset_count"],
        "derived_views_verified": validated["derived_view_count"],
        "feature_writes": 1,
        "model_training_authorized": False,
        "execution_authority": "none",
    }


class BrokerageResearchFabricAdapter:
    """Implements the existing FabricAdapter interface, no new fabric owner."""

    @property
    def adapter_name(self) -> str:
        return "original_data_brokerage_research_observation"

    def read_observations(self, *, root: str | Path,
                          context: PredictiveCloudFabricContext,
                          now: datetime | None = None,
                          dataset_id: str | None = None) -> dict:
        _require_internal_context(context)
        base = Path(root).resolve()
        if dataset_id is not None and dataset_id not in set(SOURCES) | set(VIEWS):
            raise ValueError("UNKNOWN_BROKERAGE_RESEARCH_SCOPE")
        source = _read_receipt(base / FEATURE_PATH, SCHEMA)
        if (source.get("status") != "VERIFIED_INTERNAL_CLOUD_RESEARCH_FEATURES"
                or source.get("tenant_exposure_authorized") is not False
                or source.get("production_training_samples_admitted") != 0
                or source.get("execution_authority") != "none"
                or not isinstance(source.get("features"), dict)):
            raise ValueError("RESEARCH_FEATURE_MANIFEST_AUTHORITY_HELD")
        observed = build_internal_brokerage_features(base, now=now)
        if (_digest(observed) != source.get("content_sha256")
                or observed != source.get("features")):
            raise ValueError("RESEARCH_FEATURE_SOURCE_DRIFT_OR_INJECTION")
        segments = observed["segments"]
        datasets = observed["datasets"]
        if dataset_id is not None:
            segments = [p for p in segments if p["dataset_id"] == dataset_id]
            datasets = [p for p in datasets if p["dataset_id"] == dataset_id]
        return {
            "status": "VERIFIED_BROKERAGE_INTERNAL_RESEARCH_OBSERVATIONS",
            "dataset_id": dataset_id,
            "feature_segments": segments,
            "dataset_summaries": datasets,
            "feature_segment_count": len(segments),
            "source_version_fingerprint": source["content_sha256"],
            "commercial_conversion_probability": None,
            "customer_revenue": None,
            "model_training_authorized": False,
            "production_forecast_authorized": False,
            "tenant_exposure_authorized": False,
            "buyer_outreach_authorized": False,
            "execution_authority": "none",
        }
