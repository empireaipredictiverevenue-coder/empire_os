"""Read-only Founder projection for Empire Intelligence Nodes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from empire_os.intelligence_nodes import NODES
from empire_os.spatial_physical_runtime import build_spatial_physical_runtime
from empire_os.vertical_intelligence_runtime import (
    build_private_capital_intelligence_runtime,
    build_property_intelligence_runtime,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_intelligence_nodes_projection(repo_root: Path) -> dict[str, Any]:
    runtime = repo_root / "runtime"
    source_health = _read_json(runtime / "source_health" / "latest.json")
    acquisition = _read_json(runtime / "acquisition" / "latest.json")
    spatial_physical = build_spatial_physical_runtime(repo_root)
    property_runtime = build_property_intelligence_runtime(repo_root)
    private_capital_runtime = build_private_capital_intelligence_runtime(
        repo_root
    )
    observed_sources = tuple(dict.fromkeys(
        value for value in (
            str(source_health.get("source") or "").strip(),
            str(acquisition.get("source") or "").strip(),
        )
        if value
    ))

    nodes = []
    for node in NODES:
        matched = tuple(
            source for source in observed_sources if source in node.sensors
        )
        row = node.as_dict()
        observation_count = None
        evidence_state = None
        if node.key == "natural_physical":
            observation_count = spatial_physical.get("physical_observations")
            if isinstance(observation_count, int) and observation_count > 0:
                matched = tuple(dict.fromkeys((*matched, "storm_signals")))
                evidence_state = "physical_evidence_observed"
            else:
                evidence_state = "physical_evidence_unknown"
        elif node.key == "volumetric":
            observation_count = spatial_physical.get("volumetric_observations")
            evidence_state = (
                "volumetric_evidence_observed"
                if isinstance(observation_count, int) and observation_count > 0
                else "no_real_3d_evidence_observed"
            )
        elif node.key == "property":
            observation_count = property_runtime.get("evidence_count")
            evidence_state = property_runtime.get("evidence_state")
            permit_sources = property_runtime.get("permit_sources")
            if isinstance(permit_sources, dict):
                matched = tuple(dict.fromkeys((
                    *matched,
                    *(
                        str(key)
                        for key, value in permit_sources.items()
                        if int(value or 0) > 0
                    ),
                )))
            if (
                isinstance(property_runtime.get("physical_observation_count"), int)
                and property_runtime["physical_observation_count"] > 0
            ):
                matched = tuple(dict.fromkeys((*matched, "natural_physical")))
        elif node.key == "private_capital":
            observation_count = private_capital_runtime.get("evidence_count")
            evidence_state = private_capital_runtime.get("evidence_state")
            if evidence_state == "EVIDENCE_AVAILABLE":
                matched = tuple(dict.fromkeys((*matched, "canonical_private_capital")))

        row["runtime_evidence"] = {
            "observed_sources": list(matched),
            "current_source_match": bool(matched),
            "observation_count": observation_count,
            "evidence_state": evidence_state,
            "opportunity_count": None,
            "revenue_cents": None,
            "realized_gp_cents": None,
            "counts_unknown": True,
        }
        nodes.append(row)

    return {
        "schema_version": "empire.founder_intelligence_nodes.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "node_count": len(nodes),
        "current_observed_sources": list(observed_sources),
        "nodes": nodes,
    }


def get_intelligence_node_projection(
    repo_root: Path,
    key: str,
) -> dict[str, Any] | None:
    normalized = str(key or "").strip().lower()
    payload = build_intelligence_nodes_projection(repo_root)
    return next(
        (row for row in payload["nodes"] if row["key"] == normalized),
        None,
    )
