"""Deterministic, evidence-grounded ranking of current Graphify CODE links.

No embedding calls, heuristically invented business data, raw prompts or
counterparty records. A hit is a code match or a 1-hop extracted relation,
never a forecast and never a proof that a code edit is safe.
"""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Mapping, Iterable

MAX_TERMS = 8
MAX_NODES = 200_000
MAX_EDGES = 500_000
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,127}")
_LINE = re.compile(r"^L([1-9][0-9]{0,7})$")
_ALLOWED_RELATIONS = frozenset({
    "calls", "contains", "imports", "imports_from", "references",
    "method", "uses", "inherits",
})


def _name_tokens(text: str) -> frozenset[str]:
    return frozenset(item.lower() for item in _TOKEN.findall(text)[:64])


def _valid_path(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 512:
        return False
    return (
        value.startswith("empire_os/") or value.startswith("scripts/")
        or value.startswith("tests/") or value.startswith("apps/")
        or value.startswith("docs/")
        or ("/" in value and not value.startswith("/"))
    ) and not any(p in {"", ".", ".."} for p in value.split("/"))


def rank_attested_code_paths(
    graph: Mapping[str, Any], *, terms: Iterable[str],
    max_files: int = 5,
) -> tuple[dict[str, Any], ...]:
    """Rank attested-code source paths using direct symbols and graph edges.

    Input should be the code-only result of import_graphify_code from a
    freshness-attested source. No buyer namespace is ever considered.
    Output contains only file paths and parser line references, not prompts.
    """
    if type(max_files) is not int or not 1 <= max_files <= 5:
        raise ValueError("invalid max_files")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if (not isinstance(nodes, list) or len(nodes) > MAX_NODES
            or not isinstance(edges, list) or len(edges) > MAX_EDGES):
        raise ValueError("invalid code graph")
    clean_terms: list[str] = []
    for term in terms:
        if not isinstance(term, str):
            continue
        value = term.strip().lower()
        if 2 <= len(value) <= 128 and value not in clean_terms:
            clean_terms.append(value)
        if len(clean_terms) >= MAX_TERMS:
            break
    if not clean_terms:
        return ()
    indexed: dict[str, Mapping[str, Any]] = {}
    seeds: dict[str, tuple[int, str]] = {}
    for node in nodes:
        if not isinstance(node, Mapping) or node.get("domain") != "code":
            raise ValueError("non-code domain in code relevance graph")
        nid = node.get("id")
        if not isinstance(nid, str) or nid in indexed:
            raise ValueError("duplicate or invalid code node")
        indexed[nid] = node
        label = str(node.get("label", "")).lower()
        path = str(node.get("source_file", "")).lower()
        exact_terms = _name_tokens(label)
        best = (0, "")
        for term in clean_terms:
            if label == term:
                candidate = (120, "EXACT_SYMBOL")
            elif term in exact_terms:
                candidate = (96, "SYMBOL_TOKEN")
            elif term in label:
                candidate = (75, "PARTIAL_SYMBOL")
            elif term in path:
                candidate = (60, "SOURCE_PATH")
            else:
                candidate = (0, "")
            if candidate[0] > best[0]:
                best = candidate
        if best[0]:
            seeds[nid] = best
    if not seeds:
        return ()
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in edges:
        if not isinstance(e, Mapping) or e.get("domain") != "code":
            raise ValueError("non-code edge in code relevance graph")
        a = e.get("source")
        b = e.get("target")
        if a not in indexed or b not in indexed:
            raise ValueError("dangling graph relationship")
        rel = e.get("relation")
        if e.get("confidence") != "EXTRACTED" or rel not in _ALLOWED_RELATIONS:
            continue
        adj[a].append((b, rel))
        adj[b].append((a, rel))
    matches: dict[str, dict[str, Any]] = {}

    def add(nid: str, score: int, reason: str, relation: str | None = None) -> None:
        node = indexed[nid]
        path = node.get("source_file")
        if not _valid_path(path):
            return
        source_location = node.get("source_location", "")
        if not isinstance(source_location, str) or not _LINE.fullmatch(source_location):
            source_location = ""
        hit = matches.get(path)
        value = {
            "source_file": path, "source_location": source_location,
            "relevance_score": score, "reason": reason,
            "relationship": relation,
        }
        if hit is None or (score, -len(path)) > (
                hit["relevance_score"], -len(hit["source_file"])):
            matches[path] = value

    for nid, (score, reason) in seeds.items():
        add(nid, score, reason)
        for linked_id, rel in adj.get(nid, ()):
            # Neighbours are context, not matches or proof. A direct
            # symbol always outranks a related file.
            add(linked_id, min(score // 2, 48), "EXTRACTED_RELATIONSHIP", rel)
    ordered = sorted(
        matches.values(),
        key=lambda x: (-x["relevance_score"], x["source_file"],
                       x["source_location"], x["reason"]),
    )
    return tuple(ordered[:max_files])
