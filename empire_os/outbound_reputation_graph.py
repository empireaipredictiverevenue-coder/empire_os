"""Dependency graph for deliverability blast-radius analysis."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Iterable, Mapping


def build_dependency_graph(edges: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        upstream = str(edge.get("upstream") or "").strip()
        downstream = str(edge.get("downstream") or "").strip()
        if upstream and downstream:
            graph[upstream].add(downstream)
    return dict(graph)


def blast_radius(
    graph: Mapping[str, set[str]],
    failed_nodes: Iterable[str],
) -> dict[str, Any]:
    """Return all dependent assets reachable from unhealthy infrastructure nodes."""

    queue = deque(str(node) for node in failed_nodes if str(node))
    seen: set[str] = set(queue)
    impacted: set[str] = set()

    while queue:
        node = queue.popleft()
        for child in graph.get(node, set()):
            if child not in seen:
                seen.add(child)
                impacted.add(child)
                queue.append(child)

    return {
        "failed_nodes": sorted(set(str(node) for node in failed_nodes if str(node))),
        "impacted_nodes": sorted(impacted),
        "impact_count": len(impacted),
    }
