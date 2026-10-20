"""Read-only direct code dependency impact, based on attested Graphify AST."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Iterable

SCHEMA = "empire.graphify.code_change_impact.v1"
_ALLOWED = frozenset(("calls","references","imports","imports_from","uses","inherits"))


def review_attested_code_impact(
    code_graph: Mapping[str, Any], *, changed_paths: Iterable[str],
    max_affected: int = 25,
) -> dict[str, Any]:
    """Report incoming extracted code references, never execute code."""
    if type(max_affected) is not int or not 1 <= max_affected <= 50:
        raise ValueError("invalid result bound")
    nodes = code_graph.get("nodes")
    edges = code_graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("invalid code graph")
    if len(nodes) > 200000 or len(edges) > 500000:
        raise ValueError("oversized code graph")
    wanted = tuple(dict.fromkeys(changed_paths))
    if not wanted or len(wanted) > 15:
        raise ValueError("1-15 changed code paths required")
    if any(
        not isinstance(f, str) or not f or len(f) > 512 or
        f.startswith("/") or "\\" in f or not f.endswith(".py") or
        any(seg in ("", ".", "..") for seg in f.split("/"))
        for f in wanted
    ):
        raise ValueError("invalid changed code path")

    by_id = {}
    by_file = defaultdict(set)
    for n in nodes:
        if not isinstance(n, Mapping) or n.get("domain") != "code":
            raise ValueError("non-code node")
        ident = n.get("id")
        if not isinstance(ident, str) or ident in by_id:
            raise ValueError("invalid node identity")
        by_id[ident] = n
        path = n.get("source_file")
        if isinstance(path, str) and path:
            by_file[path].add(ident)

    if any(path not in by_file for path in wanted):
        raise ValueError("changed code file not in attested graph")

    touched = defaultdict(set)
    for edge in edges:
        if not isinstance(edge, Mapping) or edge.get("domain") != "code":
            raise ValueError("non-code edge")
        source, target = edge.get("source"), edge.get("target")
        if source not in by_id or target not in by_id:
            raise ValueError("dangling code edge")
        relation = edge.get("relation")
        if relation not in _ALLOWED or edge.get("confidence") != "EXTRACTED":
            continue
        changed = by_id[target].get("source_file")
        dependent = by_id[source].get("source_file")
        if changed in wanted and dependent and dependent not in wanted:
            touched[dependent].add(relation)

    rows = [{
        "source_file": path,
        "extracted_relationships": sorted(relations),
        "status": "REVIEW_REQUIRED_NOT_PROVEN_RUNTIME_IMPACT",
    } for path, relations in touched.items()]
    rows.sort(key=lambda row: (-len(row["extracted_relationships"]), row["source_file"]))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "changed_paths": list(wanted),
        "affected_source_files": rows[:max_affected],
        "affected_source_count": min(max_affected, len(rows)),
        "results_truncated": len(rows) > max_affected,
        "known_test_file_candidates": sorted(
            row["source_file"] for row in rows[:max_affected]
            if row["source_file"].startswith("tests/")
        ),
        "runtime_impact_verified": False,
        "automatic_code_change_authorized": False,
        "commercial_impact_claimed": False,
    }
