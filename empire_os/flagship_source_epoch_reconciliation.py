"""Aggregate, read-only source-epoch diagnostic for the EXISTING Opportunity Factory.

Uses canonical scientific pathway validators. It identifies which producer
snapshot is out of sync, without exporting opportunity keys or bypassing the
exact four-source join. An epoch mismatch is NEVER a buyer or Quant forecast.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.revenue_evidence_pathways import (
    SOURCES, MAX_SKEW, PathwayEvidenceHold, _read, _validate,
    review_evidence_pathways,
)

SCHEMA = "empire.flagship.source_epoch_reconciliation.v1"
_STAGES = ("radar", "intake", "router", "quant")
_SAFE_HOLDS = frozenset((
    "source_snapshot_skew_hold", "cross_stage_identity_join_mismatch",
    "quant_decision_source_contract_invalid",
    "quant_factory_readiness_contradiction",
    "unavailable_quant_packet_has_prediction_reference",
    "invalid_quant_missing_evidence", "unknown_quant_factor",
    "missing_quant_factors_not_explained", "available_quant_packet_with_missing_factors",
    "router_count_mismatch", "invalid_factory_blocker_rows",
    "blocker_join_mismatch", "untrusted_routing_authority",
    "invalid_normalized_signal_inventory", "invalid_normalized_score",
    "unverified_revenue_or_buyer_claim", "invalid_route",
))
_OWNER = "existing_opportunity_factory_owner"


def _base() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "status": "SOURCE_UNAVAILABLE",
        "mode": "OBSERVE",
        "source_counts": {stage: None for stage in _STAGES},
        "source_ages_seconds": {stage: None for stage in _STAGES},
        "source_time_skew_seconds": None,
        "radar_missing_from_downstream_counts": {stage: None for stage in _STAGES[1:]},
        "downstream_without_radar_counts": {stage: None for stage in _STAGES[1:]},
        "downstream_three_stage_identities_agree": None,
        "join_result": "NOT_PROVEN",
        "canonical_pathway_reason": None,
        "next_owner": _OWNER,
        "next_action": "RESTORE_CANONICAL_SOURCE_AVAILABILITY",
        "first_party_buyer_verified": False,
        "conversion_probability_verified": False,
        "full_population_calibration_verified": False,
        "forecast_issued": False,
        "commercial_activity_performed": False,
        "database_writes": False,
        "outbound_sent": False,
        "funds_moved": False,
        "execution_authority": "none",
    }


def review_source_epoch_reconciliation(
    sources: Mapping[str, Mapping[str, Any]], *, as_of: datetime
) -> dict[str, Any]:
    """Check all four independently validated point-in-time source snapshots."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware snapshot clock required")
    if not isinstance(sources, Mapping) or set(sources) != set(_STAGES):
        raise ValueError("exact existing four source snapshots required")
    now = as_of.astimezone(timezone.utc)
    indexes = {}
    timestamps = {}
    result = _base()
    for stage in _STAGES:
        rows, stamp = _validate(sources[stage], stage, now)
        indexes[stage] = set(rows)
        timestamps[stage] = stamp
    skew = max(timestamps.values()) - min(timestamps.values())
    radar = indexes["radar"]
    deficits = {stage: len(radar - indexes[stage]) for stage in _STAGES[1:]}
    extras = {stage: len(indexes[stage] - radar) for stage in _STAGES[1:]}
    downstream_agree = len({frozenset(indexes[stage]) for stage in _STAGES[1:]}) == 1
    report = dict(
        result,
        source_counts={stage: len(indexes[stage]) for stage in _STAGES},
        source_ages_seconds={
            stage: int((now - timestamps[stage]).total_seconds())
            for stage in _STAGES
        },
        source_time_skew_seconds=int(skew.total_seconds()),
        radar_missing_from_downstream_counts=deficits,
        downstream_without_radar_counts=extras,
        downstream_three_stage_identities_agree=downstream_agree,
    )
    if skew > MAX_SKEW:
        return dict(report, status="EPOCH_SKEW_HOLD",
                    next_action="REVIEW_UPSTREAM_SOURCE_EPOCH_SKEW")
    if all(not deficits[k] and not extras[k] for k in deficits):
        try:
            canonical = review_evidence_pathways(sources, as_of=now, limit=1)
        except (PathwayEvidenceHold, ValueError, TypeError, KeyError) as exc:
            reason = str(exc) if isinstance(exc, PathwayEvidenceHold) else "UNCLASSIFIED_SOURCE_HOLD"
            return dict(report, status="CANONICAL_EVIDENCE_CONTRACT_HOLD",
                        canonical_pathway_reason=(
                            reason if reason in _SAFE_HOLDS else "UNCLASSIFIED_SOURCE_HOLD"
                        ),
                        next_action="RESTORE_EXISTING_CANONICAL_PATHWAY_CONTRACT")
        if canonical.get("status") != "EVIDENCE_PATHWAY_REVIEW_READY":
            raise ValueError("canonical pathway reported unsupported authority")
        return dict(report, status="FOUR_STAGE_SOURCE_IDENTITIES_ALIGNED",
                    join_result="CANONICAL_PATHWAY_REVIEW_READY",
                    next_action="RESUME_EXISTING_FIRST_PARTY_BUYER_EVIDENCE_REVIEW")
    if (downstream_agree
            and all(deficits[stage] > 0 for stage in deficits)
            and not any(extras.values())):
        return dict(report, status="RADAR_AHEAD_OF_FACTORY_STAGES",
                    next_action="REGENERATE_EXISTING_INTAKE_ROUTER_QUANT_FROM_CURRENT_RADAR")
    return dict(report, status="MULTI_STAGE_IDENTITY_DRIFT",
                next_action="RECONCILE_CANONICAL_SOURCE_IDENTITIES_WITH_OWNER")


def review_source_epoch_reconciliation_runtime(
    repo_root: str | Path, *, as_of: datetime
) -> dict[str, Any]:
    """Read-only source inspection. Files/DB/producers are never modified."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware snapshot clock required")
    root = Path(repo_root).resolve()
    try:
        sources = {name: _read(root, name) for name in _STAGES}
        return review_source_epoch_reconciliation(sources, as_of=as_of)
    except (PathwayEvidenceHold, ValueError, TypeError, KeyError):
        return _base()
