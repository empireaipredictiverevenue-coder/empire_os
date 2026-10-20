"""Read-only Graphify adapter for EmpireOS code and buyer-demand evidence.

Two graph namespaces; no database access, outbound actions, forecasts, or
production authority. Graphify indexes code; existing BuyerDemandGraph remains
the only commercial graph validator. This module does not install a new agent.
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
import hmac
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.buyer_demand_graph import (
    BuyerDemandGraph, BuyerDemandGraphNode, BuyerDemandGraphEdge,
    build_buyer_demand_graph,
)

SCHEMA_VERSION = "empire.graphify.dual_bridge.v1"
MAX_NODES = 200_000
MAX_EDGES = 500_000
MAX_QUERY_RESULTS = 40
CONFIDENCE = frozenset({"EXTRACTED", "INFERRED", "AMBIGUOUS", "UNKNOWN"})
MODE = "OBSERVE"


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]


def _private_digest(value: str, key: bytes, domain: str) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("private graph requires owner-provided 32+ byte pseudonymization key")
    return hmac.digest(key, (domain + chr(0) + value).encode("utf-8"), "sha256").hex()


def _allowed_categories(categories) -> frozenset[str]:
    if isinstance(categories, str):
        raise ValueError("categories must be explicit reviewed labels")
    values = frozenset(categories)
    if len(values) > 100 or any(not isinstance(v, str) or not v or len(v) > 100 for v in values):
        raise ValueError("invalid approved commercial category labels")
    return values


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"invalid {field}")
    return value.strip()


def _rows(payload: Mapping[str, Any], key: str, limit: int) -> list[dict[str, Any]]:
    rows = payload.get(key, [])
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError(f"invalid or oversized {key}")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"invalid {key} entry")
    return rows


def import_graphify_code(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Import Graphify's node/edge JSON without promoting inferred links to fact."""
    if not isinstance(payload, dict):
        raise ValueError("invalid Graphify payload")
    rows = _rows(payload, "nodes", MAX_NODES)
    relations = _rows(payload, "edges", MAX_EDGES)
    nodes: list[dict[str, Any]] = []
    ids: set[str] = set()
    for item in rows:
        original = _text(item.get("id"), "Graphify node id")
        if original in ids:
            raise ValueError("duplicate code node")
        ids.add(original)
        nodes.append({
            "id": f"code:{original}",
            "label": _text(item.get("label", original), "Graphify label"),
            "type": str(item.get("type", item.get("file_type", "unknown")))[:64],
            "domain": "code",
            "source_file": str(item.get("source_file", ""))[:1024],
            "source_location": str(item.get("source_location", ""))[:128],
            "origin": str(item.get("_origin", item.get("origin", "unknown")))[:64],
        })
    edges: list[dict[str, Any]] = []
    for item in relations:
        source = _text(item.get("source"), "Graphify source")
        target = _text(item.get("target"), "Graphify target")
        if source not in ids or target not in ids:
            raise ValueError("Graphify edge references missing code node")
        relation = _text(item.get("relation"), "Graphify relation")
        confidence = item.get("confidence", "UNKNOWN")
        if confidence not in CONFIDENCE:
            raise ValueError("unsupported Graphify confidence")
        edges.append({
            "id": f"code:{_digest(source + '|' + target + '|' + relation + '|' + str(len(edges)))}",
            "source": f"code:{source}",
            "target": f"code:{target}",
            "relation": relation,
            "confidence": confidence,
            "domain": "code",
            "source_file": str(item.get("source_file", ""))[:1024],
            "source_location": str(item.get("source_location", ""))[:128],
        })
    return {"nodes": nodes, "edges": edges}


def project_buyer_demand(
    graph: BuyerDemandGraph, *, privacy_key: bytes,
    approved_category_labels: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Project validated, evidence-referenced buyer demand without leaking labels.

    No raw buyer identity, source URL, email, or evidence ref is copied.
    Stable hashes permit reconciliation by the owner with the original graph.
    A reference alone does not prove buyer authentication or actual capacity.
    """
    if not isinstance(graph, BuyerDemandGraph):
        raise TypeError("expected validated BuyerDemandGraph")
    _private_digest("key-check", privacy_key, "graphify.key.validation")
    approved = _allowed_categories(approved_category_labels)
    if graph.mode != MODE or graph.execution_authority != "none":
        raise ValueError("buyer graph must be OBSERVE with no execution authority")
    if graph.inferred_edge_count != 0 or graph.outbound_enabled or graph.crawler_scheduling_enabled:
        raise ValueError("buyer graph must be explicit and non-executing")
    # Revalidate even dataclass instances: callers can instantiate them directly.
    rebuilt = build_buyer_demand_graph(
        nodes=[BuyerDemandGraphNode(**row) for row in graph.nodes],
        edges=[BuyerDemandGraphEdge(**row) for row in graph.edges],
    )
    if graph != rebuilt:
        raise ValueError("buyer graph counts or content inconsistent with validated evidence")
    node_ids: dict[str, str] = {}
    nodes = []
    for item in graph.nodes:
        node_id = _text(item.get("node_id"), "buyer node id")
        node_ids[node_id] = f"revenue:{_private_digest(node_id, privacy_key, 'node')}"
        evidence = item.get("evidence_refs") or []
        if not evidence:
            raise ValueError("commercial node missing evidence")
        nodes.append({
            "id": node_ids[node_id],
            "label": item["label"] if item["node_type"] in {"PRODUCT", "MARKET"} and item["label"] in approved else item["node_type"],  # allowlisted public taxonomy only
            "type": item["node_type"].lower(),
            "domain": "revenue",
            "evidence_fingerprints": [_private_digest(_text(ref, "evidence ref"), privacy_key, "evidence") for ref in evidence],
            "verification_status": "EVIDENCE_REFERENCED_NOT_AUTHENTICATED",
        })
    edges = []
    for item in graph.edges:
        source = node_ids.get(item["source_node_id"])
        target = node_ids.get(item["target_node_id"])
        if source is None or target is None:
            raise ValueError("commercial edge missing node")
        evidence = item.get("evidence_refs") or []
        if not evidence:
            raise ValueError("commercial edge missing evidence")
        edges.append({
            "id": f"revenue:{_private_digest(item['edge_id'], privacy_key, 'edge')}",
            "source": source,
            "target": target,
            "relation": item["relation"],
            "confidence": "EXTRACTED",  # explicit edge, NOT authenticated buyer truth
            "verification_status": "EVIDENCE_REFERENCED_NOT_AUTHENTICATED",
            "domain": "revenue",
            "observed_at": item["observed_at"],
            "evidence_fingerprints": [_private_digest(_text(ref, "evidence ref"), privacy_key, "evidence") for ref in evidence],
            "capacity_remaining": item.get("capacity_remaining"),
            "demand_units": item.get("demand_units"),  # None remains unknown
        })
    return {"nodes": nodes, "edges": edges, "unknown_demand_quantity_count": graph.unknown_demand_quantity_count}


def assemble_dual_graph(
    *, code_payload: Mapping[str, Any],
    buyer_graph: BuyerDemandGraph,
    privacy_key: bytes,
    approved_category_labels: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Compose isolated code and revenue namespaces; never infer cross-domain edges."""
    code = import_graphify_code(code_payload)
    revenue = project_buyer_demand(
        buyer_graph, privacy_key=privacy_key,
        approved_category_labels=approved_category_labels,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "execution_authority": "none",
        "commercial_authority": "none",
        "buyer_identity_authenticated": False,
        "no_cross_domain_inferences": True,
        "node_count": len(code["nodes"]) + len(revenue["nodes"]),
        "edge_count": len(code["edges"]) + len(revenue["edges"]),
        "unknown_demand_quantity_count": revenue["unknown_demand_quantity_count"],
        "domains": {"code": len(code["nodes"]), "revenue": len(revenue["nodes"])},
        "nodes": code["nodes"] + revenue["nodes"],
        "edges": code["edges"] + revenue["edges"],
    }


def query_evidence(
    graph: Mapping[str, Any], *, focus: str, max_hops: int = 1,
    max_nodes: int = 12,
) -> dict[str, Any]:
    """Bounded local retrieval for an ASTRA context consumer; no side effects."""
    term = _text(focus, "focus").lower()
    if not 0 <= max_hops <= 3 or not 1 <= max_nodes <= MAX_QUERY_RESULTS:
        raise ValueError("invalid query bounds")
    nodes = _rows(graph, "nodes", MAX_NODES)
    edges = _rows(graph, "edges", MAX_EDGES)
    by_id = {node.get("id"): node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("duplicate graph nodes")
    seeds = [
        node["id"] for node in nodes
        if term in str(node.get("id", "")).lower()
        or term in str(node.get("label", "")).lower()
        or term in str(node.get("source_file", "")).lower()
    ][:max_nodes]
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        a, b = edge.get("source"), edge.get("target")
        if a not in by_id or b not in by_id:
            raise ValueError("dangling graph edge")
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    selected: set[str] = set()
    q = deque((seed, 0) for seed in seeds)
    while q and len(selected) < max_nodes:
        nid, depth = q.popleft()
        if nid in selected:
            continue
        selected.add(nid)
        if depth < max_hops:
            for neighbor in sorted(adjacency.get(nid, ())):
                if neighbor not in selected:
                    q.append((neighbor, depth + 1))
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "execution_authority": "none",
        "focus": focus,
        "nodes": [by_id[nid] for nid in sorted(selected)],
        "edges": [
            edge for edge in edges
            if edge["source"] in selected and edge["target"] in selected
        ],
        "no_matching_evidence": not bool(selected),
        "forecast_produced": False,
        "outreach_enabled": False,
    }


def load_graphify_code(path: str | Path) -> dict[str, Any]:
    """Only read an explicit local Graphify export. Never scan production."""
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 50_000_000:
        raise ValueError("missing or unsafe Graphify graph file")
    with p.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    return import_graphify_code(payload)


def build_astra_graph_packet(
    *, code_graph_path: str | Path, buyer_graph: BuyerDemandGraph,
    focus: str, privacy_key: bytes,
    approved_category_labels: frozenset[str] = frozenset(),
    max_nodes: int = 12,
) -> dict[str, Any]:
    """Stable read-only handoff for the existing ASTRA orchestration owner.

    A caller must supply an already-validated in-memory BuyerDemandGraph.
    No internal EmpireDB query or live route is created here.
    """
    path = Path(code_graph_path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 50_000_000:
        raise ValueError("unsafe Graphify path")
    raw = json.loads(path.read_text(encoding="utf-8"))
    joined = assemble_dual_graph(
        code_payload=raw, buyer_graph=buyer_graph, privacy_key=privacy_key,
        approved_category_labels=approved_category_labels,
    )
    context = query_evidence(joined, focus=focus, max_nodes=max_nodes)
    return {
        "adapter": SCHEMA_VERSION,
        "consumer": "ASTRA_EXISTING_OWNER",
        "mode": MODE,
        "execution_authority": "none",
        "context": context,
        "truth_policy": {
            "code_inferences_are_not_verified": True,
            "buyer_evidence_is_not_authentication": True,
            "unknown_demand_is_not_zero": True,
            "forecasting_delegated_to_existing_owner": True,
        },
        "proposed_next_step": "EXISTING_OWNER_REVIEW_CONTEXT",
    }
