"""Read-only Founder projection for Empire Intelligence Nodes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from empire_os.intelligence_nodes import NODES


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
        row["runtime_evidence"] = {
            "observed_sources": list(matched),
            "current_source_match": bool(matched),
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
