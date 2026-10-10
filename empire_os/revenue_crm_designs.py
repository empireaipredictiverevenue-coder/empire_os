"""Canonical, server-side validation of non-executable Revenue CRM journey designs.

Never trust the browser JSON validator, header-provided tenant, or designer export.
No message address, consent, prospect data, payable event or channel delivery
authority may be persisted inside a design.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID, uuid4

from empire_os.revenue_crm_journeys import journey_blueprint

SCHEMA = "empire.revenue_crm_visual_draft.v1"
GRAPH_SCHEMA = "empire.revenue_crm_omnichannel_graph.v1"
MAX_NODES, MAX_EDGES = 28, 60
IDENT = re.compile(r"^[a-z][a-z0-9_-]{1,48}$")
EMAIL_LIKE = re.compile(r"[^\s@]+@[^\s@]+")
CHANNEL_ACTION_WORDS = re.compile(
    r"\b(send|deliver|subscribe|charge|call|publish|execute|activate|message)\b",
    re.IGNORECASE,
)


class UnsafeJourneyDesign(ValueError):
    """Unknown, unsafe or cross-tenant design content."""


def canonical_tenant(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise UnsafeJourneyDesign("canonical tenant UUID required") from None


def _keys(record: Any, allowed: set[str], required: set[str]) -> None:
    if not isinstance(record, dict) or set(record) != allowed or not required <= set(record):
        raise UnsafeJourneyDesign("unknown or missing journey fields")


def _label(value: Any) -> bool:
    return (
        isinstance(value, str) and 1 <= len(value) <= 64 and value.strip() == value
        and bool(value) and not EMAIL_LIKE.search(value)
        and "://" not in value and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
    )


def _validate_dag(ids: set[str], edges: list[dict[str, Any]]) -> None:
    graph: dict[str, list[str]] = {name: [] for name in ids}
    for edge in edges:
        graph[edge["from"]].append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise UnsafeJourneyDesign("journey cycles are not allowed")
        if node in visited:
            return
        visiting.add(node)
        for child in graph[node]:
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in ids:
        visit(node)


def validate_journey_draft(value: Any) -> dict[str, Any]:
    """Produce a bounded, canonical design; reject hidden authority and data.

    Required blueprint paths must stay present, and no custom path from the
    first to final stage may skip a mandatory intermediate gate.
    """
    if not isinstance(value, dict):
        raise UnsafeJourneyDesign("journey design object required")
    # Bounded encoding before walking content, including nested/unknown fields.
    try:
        raw = json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=True)
    except (TypeError, ValueError):
        raise UnsafeJourneyDesign("non-JSON journey rejected") from None
    if len(raw) > 65536:
        raise UnsafeJourneyDesign("journey exceeds 64 KB")
    _keys(value, {
        "schema_version", "state", "execution_authority", "tenant_data_included",
        "server_persistence", "parent_blueprint_schema", "revision",
        "name", "nodes", "edges",
    }, set())
    if (
        value["schema_version"] != SCHEMA or value["state"] != "DESIGN_ONLY"
        or value["execution_authority"] != "none"
        or value["tenant_data_included"] is not False
        or value["server_persistence"] is not False
        or value["parent_blueprint_schema"] != GRAPH_SCHEMA
        or type(value["revision"]) is not int
        or not 1 <= value["revision"] <= 1000000
        or not _label(value["name"])
    ):
        raise UnsafeJourneyDesign("journey design authority invalid")
    nodes, edges = value["nodes"], value["edges"]
    original = journey_blueprint()
    mandatory = {n["id"]: n for n in original["nodes"]}
    if (
        not isinstance(nodes, list) or not len(mandatory) <= len(nodes) <= MAX_NODES
        or not isinstance(edges, list) or not len(original["edges"]) <= len(edges) <= MAX_EDGES
    ):
        raise UnsafeJourneyDesign("journey size invalid")
    seen: set[str] = set()
    valid_nodes: list[dict[str, Any]] = []
    for n in nodes:
        _keys(n, {"id", "type", "label", "x", "y", "locked"}, set())
        rid = n["id"]
        if (
            not isinstance(rid, str) or IDENT.fullmatch(rid) is None
            or rid in seen or not _label(n["label"])
            or type(n["x"]) is not int or type(n["y"]) is not int
            or not 0 <= n["x"] <= 1400 or not 0 <= n["y"] <= 1100
            or type(n["locked"]) is not bool
        ):
            raise UnsafeJourneyDesign("unbound, unsafe or duplicated journey step")
        seen.add(rid)
        if rid in mandatory:
            old = mandatory[rid]
            if n["type"] != old["type"] or n["label"] != old["label"] or n["locked"] is not True:
                raise UnsafeJourneyDesign("mandatory security gate tampered")
        elif not rid.startswith("custom_") or n["type"] not in ("review", "decision") or n["locked"] is not False:
            raise UnsafeJourneyDesign("unsupported custom step")
        elif CHANNEL_ACTION_WORDS.search(n["label"]):
            raise UnsafeJourneyDesign("executable instruction in design label")
        valid_nodes.append({k: n[k] for k in ("id", "type", "label", "x", "y", "locked")})
    if not set(mandatory) <= seen:
        raise UnsafeJourneyDesign("mandatory journey steps omitted")

    required_pairs = {(edge["from"], edge["to"]) for edge in original["edges"]}
    pairs: set[tuple[str, str]] = set()
    valid_edges: list[dict[str, Any]] = []
    for e in edges:
        _keys(e, {"from", "to", "condition", "locked"}, set())
        if (
            not isinstance(e["from"], str) or not isinstance(e["to"], str)
            or e["from"] not in seen or e["to"] not in seen
            or e["from"] == e["to"]
            or e["condition"] != "evidence_review_only"
            or type(e["locked"]) is not bool
        ):
            raise UnsafeJourneyDesign("unsafe or orphan journey connection")
        pair = (e["from"], e["to"])
        if pair in pairs or (e["locked"] and pair not in required_pairs):
            raise UnsafeJourneyDesign("duplicate or forged journey connection")
        pairs.add(pair)
        valid_edges.append({k: e[k] for k in ("from", "to", "condition", "locked")})
    if not all(
        any(e["from"] == start and e["to"] == end and e["locked"] for e in valid_edges)
        for start, end in required_pairs
    ):
        raise UnsafeJourneyDesign("mandatory review gates disconnected")
    _validate_dag(seen, valid_edges)

    required = [n["id"] for n in original["nodes"]]
    first, last = required[0], required[-1]
    for excluded in required[1:-1]:
        reachable = {first}
        queue = [first]
        while queue:
            source = queue.pop()
            for e in valid_edges:
                target = e["to"]
                if e["from"] == source and target != excluded and target not in reachable:
                    reachable.add(target)
                    queue.append(target)
        if last in reachable:
            raise UnsafeJourneyDesign("journey bypasses mandatory compliance gate")
    return {
        "schema_version": SCHEMA, "state": "DESIGN_ONLY",
        "execution_authority": "none", "tenant_data_included": False,
        "server_persistence": False, "parent_blueprint_schema": GRAPH_SCHEMA,
        "revision": value["revision"], "name": value["name"],
        "nodes": valid_nodes, "edges": valid_edges,
    }


def design_sha256(value: Mapping[str, Any]) -> str:
    checked = validate_journey_draft(value)
    raw = json.dumps(checked, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidatedDesignRevision:
    tenant_id: str
    design_id: str
    revision: int
    sha256: str
    payload: dict[str, Any]
    mode: str = "DESIGN_ONLY"
    execution_authority: str = "none"
    outbound_authorized: bool = False
    payment_authorized: bool = False


def prepare_design_revision(
    value: Any, *, authenticated_tenant_id: str,
    design_id: str | None = None, prior_revision: int | None = None,
) -> ValidatedDesignRevision:
    """Prepare one proposed canonical revision, without DB writes.

    Only a server-authenticated tenant ID may be passed. Never take tenant
    identity from the design payload or a client HTTP tenant header.
    """
    tenant = canonical_tenant(authenticated_tenant_id)
    try:
        did = str(UUID(design_id)) if design_id is not None else str(uuid4())
    except (TypeError, ValueError, AttributeError):
        raise UnsafeJourneyDesign("canonical design ID required") from None
    if prior_revision is not None and (
        type(prior_revision) is not int or prior_revision < 1
        or prior_revision >= 1000000
    ):
        raise UnsafeJourneyDesign("invalid expected revision")
    checked = validate_journey_draft(value)
    # Browser revision is a local editing counter, not an authorised EmpireDB
    # version. The server derives the canonical revision from the expected
    # prior DB row and verifies it atomically against the actual latest row.
    canonical_revision = 1 if prior_revision is None else prior_revision + 1
    checked["revision"] = canonical_revision
    return ValidatedDesignRevision(
        tenant_id=tenant, design_id=did, revision=canonical_revision,
        sha256=design_sha256(checked), payload=checked,
    )
