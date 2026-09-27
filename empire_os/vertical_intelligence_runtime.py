"""Read-only vertical intelligence runtime projections.

Property may reuse observed Permit and Natural Physical evidence.
Private Capital stays UNKNOWN until canonical sponsor/portfolio/add-on evidence
is explicitly materialized into a refreshed snapshot.

No projection creates pricing, terms, outreach, investment claims or revenue.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from empire_os.permit_intelligence_runtime import build_permit_intelligence_runtime
from empire_os.spatial_physical_runtime import build_spatial_physical_runtime


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_property_intelligence_runtime(repo_root: Path) -> dict[str, Any]:
    permit = build_permit_intelligence_runtime(repo_root)
    physical = build_spatial_physical_runtime(repo_root)

    permit_count = int(permit.get("signal_count") or 0)
    resolved_permits = int(permit.get("resolved_count") or 0)

    raw_physical = physical.get("physical_observations")
    physical_count = raw_physical if isinstance(raw_physical, int) else 0

    raw_volumetric = physical.get("volumetric_observations")
    volumetric_count = raw_volumetric if isinstance(raw_volumetric, int) else 0

    evidence_count = permit_count + physical_count + volumetric_count
    evidence_available = evidence_count > 0

    return {
        "schema_version": "empire.property-intelligence-runtime.v1",
        "mode": "OBSERVE",
        "node_key": "property",
        "product_key": "property_intelligence_monitor",
        "evidence_state": (
            "EVIDENCE_AVAILABLE" if evidence_available else "UNKNOWN"
        ),
        "permit_signal_count": permit_count,
        "resolved_permit_count": resolved_permits,
        "physical_observation_count": (
            raw_physical if isinstance(raw_physical, int) else None
        ),
        "volumetric_observation_count": (
            raw_volumetric if isinstance(raw_volumetric, int) else None
        ),
        "evidence_count": evidence_count,
        "latest_permit_seen_at": permit.get("latest_seen_at"),
        "permit_sources": permit.get("by_source") or {},
        "permit_markets": permit.get("by_metro") or {},
        "physical_source_state": physical.get("source_state") or {},
        "opportunity_count": None,
        "pricing_observed": False,
        "binding_terms_ready": False,
        "actual_revenue": False,
        "execution_authority": "none",
        "unknown_stays_unknown": True,
    }


def build_private_capital_intelligence_runtime(
    repo_root: Path,
) -> dict[str, Any]:
    path = (
        repo_root
        / "runtime"
        / "vertical_intelligence"
        / "private_capital_latest.json"
    )
    snapshot = _read_json(path)

    canonical_signals = snapshot.get("canonical_signal_count")
    canonical_facts = snapshot.get("canonical_fact_count")
    segment_memberships = snapshot.get("segment_membership_count")

    observed_counts = [
        value
        for value in (
            canonical_signals,
            canonical_facts,
            segment_memberships,
        )
        if isinstance(value, int)
    ]
    evidence_count = sum(observed_counts) if observed_counts else 0
    evidence_available = evidence_count > 0

    return {
        "schema_version": "empire.private-capital-runtime.v1",
        "mode": "OBSERVE",
        "node_key": "private_capital",
        "product_key": "private_capital_intelligence",
        "evidence_state": (
            "EVIDENCE_AVAILABLE" if evidence_available else "UNKNOWN"
        ),
        "snapshot_available": bool(snapshot),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "canonical_signal_count": (
            canonical_signals if isinstance(canonical_signals, int) else None
        ),
        "canonical_fact_count": (
            canonical_facts if isinstance(canonical_facts, int) else None
        ),
        "segment_membership_count": (
            segment_memberships
            if isinstance(segment_memberships, int)
            else None
        ),
        "evidence_count": evidence_count if snapshot else None,
        "latest_observed_at": snapshot.get("latest_observed_at"),
        "opportunity_count": None,
        "deal_intent_observed": False,
        "pricing_observed": False,
        "binding_terms_ready": False,
        "actual_revenue": False,
        "execution_authority": "none",
        "unknown_stays_unknown": True,
    }
