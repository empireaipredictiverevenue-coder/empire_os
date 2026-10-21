"""Deterministic temporal feature intake for Predictive Intelligence.

Pure research-only preparation. Caller records are NOT authenticated by
supplying a tenant_id, source name, fingerprint, timestamp or SHA. No labels,
forecasts, source rows, IDs or commercial authority are exported. A late
backfill may be observed at review time but never joins an earlier decision.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from uuid import UUID

SCHEMA = "empire.predictive_intelligence.temporal_feature_review.v1"
MAX_ROWS = 500
ALLOWED_KINDS = frozenset((
    "crm_stage", "buyer_capacity", "source_demand",
    "commercial_terms", "service_event", "pricing_evidence",
))


class TemporalEvidenceHold(ValueError):
    """Input must fail closed; no raw source identifiers in exceptions."""


def _time(value: Any) -> datetime:
    if type(value) is not str or not 10 <= len(value) <= 64:
        raise TemporalEvidenceHold("timezone-aware source clock required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            raise ValueError("timezone absent")
        return stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise TemporalEvidenceHold("invalid original source clock") from None


def _uuid(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, TypeError):
        return False


def _candidate(item: Any, tenant_id: str, now: datetime) -> dict[str, Any]:
    if type(item) is not dict or set(item) != {
        "tenant_id", "source_kind", "source_ref", "revision",
        "observed_at", "first_available_at", "ingested_at",
        "evidence_sha256",
    }:
        raise TemporalEvidenceHold("invalid temporal evidence envelope")
    if (item["tenant_id"] != tenant_id
            or item["source_kind"] not in ALLOWED_KINDS
            or type(item["source_ref"]) is not str
            or not 1 <= len(item["source_ref"]) <= 160
            or type(item["revision"]) is not int
            or not 1 <= item["revision"] <= 1_000_000
            or type(item["evidence_sha256"]) is not str
            or len(item["evidence_sha256"]) != 64
            or any(x not in "0123456789abcdef"
                   for x in item["evidence_sha256"])):
        raise TemporalEvidenceHold("invalid tenant/source/revision evidence")
    observed = _time(item["observed_at"])
    available = _time(item["first_available_at"])
    ingested = _time(item["ingested_at"])
    if (observed > available or available > ingested or
            ingested > now):
        raise TemporalEvidenceHold("source clock order invalid or future")
    return {
        "tenant_id": tenant_id,
        "source_kind": item["source_kind"],
        "source_ref": item["source_ref"],
        "revision": item["revision"],
        "observed_at": observed.isoformat(),
        "first_available_at": available.isoformat(),
        "ingested_at": ingested.isoformat(),
        "evidence_sha256": item["evidence_sha256"],
    }


def review_point_in_time_features(
    rows: Sequence[Mapping[str, Any]], *,
    tenant_id: str, decision_at: str, review_at: str,
) -> dict[str, Any]:
    """Return a privacy-safe as-of fingerprint, never customer forecasting.

    At decision time a row is usable only after its *first availability* AND
    ingestion; event/observed time by itself is insufficient. A later
    correction cannot retroactively become a historical feature.
    """
    if not _uuid(tenant_id):
        raise TemporalEvidenceHold("canonical tenant required")
    decision = _time(decision_at)
    now = _time(review_at)
    if decision > now or type(rows) not in (list, tuple) or len(rows) > MAX_ROWS:
        raise TemporalEvidenceHold("bounded historical review required")

    known: set[tuple[str, str, int]] = set()
    per_source: dict[tuple[str, str], dict[str, Any]] = {}
    withheld = 0
    excluded_future_events = 0
    for item in rows:
        entry = _candidate(item, tenant_id, now)
        key = (entry["source_kind"], entry["source_ref"], entry["revision"])
        if key in known:
            raise TemporalEvidenceHold("duplicate immutable evidence revision")
        known.add(key)
        # A later-arriving event/backfill is never included in old features.
        if (_time(entry["first_available_at"]) > decision or
                _time(entry["ingested_at"]) > decision):
            withheld += 1
            if _time(entry["observed_at"]) > decision:
                excluded_future_events += 1
            continue
        pair = key[:2]
        earlier = per_source.get(pair)
        if earlier is None or (
            entry["revision"], entry["ingested_at"]
        ) > (earlier["revision"], earlier["ingested_at"]):
            per_source[pair] = entry

    # The digest is repeatable independent of incoming row order, but it does
    # NOT sign or authenticate the caller-supplied source records.
    included = sorted(
        per_source.values(),
        key=lambda item: (item["source_kind"], item["source_ref"]),
    )
    manifest = {
        "schema_version": SCHEMA,
        "tenant_id": tenant_id,
        "decision_at": decision.isoformat(),
        "features": included,
    }
    digest = sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    counts = {key: 0 for key in sorted(ALLOWED_KINDS)}
    for item in included:
        counts[item["source_kind"]] += 1
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "TEMPORALLY_CONSISTENT_RESEARCH_ONLY",
        "source_records_reviewed": len(rows),
        "source_revisions_withheld_after_decision": withheld,
        "future_event_records_excluded": excluded_future_events,
        "distinct_sources_available_as_of": len(included),
        "source_kind_counts_as_of": counts,
        "feature_manifest_sha256": digest,
        "decision_at": decision.isoformat(),
        "review_at": now.isoformat(),
        "as_of_replay_deterministic": True,
        "source_issuer_authenticated_by_input": False,
        "independent_source_custody_verified": False,
        "original_forecast_issued": False,
        "real_customer_outcome_verified": False,
        "eligible_for_scientific_training": False,
        "customer_prediction_authorized": False,
        "raw_customer_records_exposed": False,
        "database_writes": False,
        "execution_authority": "none",
    }
