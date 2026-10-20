"""Curated Graphify source attestation and code-graph drift gate.

Explicit Python allowlist only. No repository crawling, production databases,
timers, model API, autonomous execution, or external network activity.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from empire_os.graphify_dual_bridge import (
    build_astra_graph_packet, import_graphify_code,
)

SCHEMA = "empire.graphify.code_snapshot.v1"
MAX_FILES = 64
MAX_SOURCE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 16_000_000


def _hash(payload: Any) -> str:
    return sha256(json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _names(names: Sequence[str]) -> tuple[str, ...]:
    if isinstance(names, (str, bytes)) or not 1 <= len(names) <= MAX_FILES:
        raise ValueError("explicit curated source allowlist required")
    cleaned = []
    for name in names:
        if not isinstance(name, str) or len(name) > 500:
            raise ValueError("invalid source name")
        p = PurePosixPath(name)
        if (p.is_absolute() or name != p.as_posix() or ".." in p.parts or
                "." in p.parts or not name.endswith(".py") or
                any(part.startswith(".") for part in p.parts)):
            raise ValueError("unsafe curated source name")
        cleaned.append(name)
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("duplicate curated source")
    return tuple(sorted(cleaned))


def capture_curated_sources(source_root: str | Path, *, files: Sequence[str]) -> dict[str, Any]:
    """Pre/post extraction fingerprint for a copy of explicit code-only sources."""
    root = Path(source_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("unsafe source root")
    root = root.resolve(strict=True)
    names = _names(files)
    rows = []
    total = 0
    for name in names:
        current = root
        for part in PurePosixPath(name).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("symlink inside source allowlist")
        if not current.is_file() or not current.resolve().is_relative_to(root):
            raise ValueError("source missing or outside root")
        size = current.stat().st_size
        if size > MAX_SOURCE_BYTES:
            raise ValueError("oversized curated source")
        data = current.read_bytes()
        if len(data) != size:
            raise ValueError("source changed during read")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("curated source set too large")
        rows.append({"file": name, "sha256": sha256(data).hexdigest(), "bytes": size})
    result = {
        "schema_version": SCHEMA,
        "source_file_count": len(rows),
        "source_bytes": total,
        "source_files": rows,
    }
    result["source_manifest_sha256"] = _hash(result)
    return result


def finalize_code_snapshot(
    graphify_export: Mapping[str, Any], *, pre_extraction_sources: Mapping[str, Any],
    source_root: str | Path,
) -> dict[str, Any]:
    """Fail if source bytes changed between pre- and post-extraction snapshots."""
    if not isinstance(pre_extraction_sources, Mapping):
        raise ValueError("missing pre-extraction source manifest")
    original = pre_extraction_sources.get("source_files", [])
    if not isinstance(original, list):
        raise ValueError("invalid pre-extraction source manifest")
    names = [r["file"] for r in original if isinstance(r, dict) and "file" in r]
    current = capture_curated_sources(source_root, files=names)
    if current != pre_extraction_sources:
        raise ValueError("source drift during or after Graphify extraction")
    imported = import_graphify_code(graphify_export)
    allowed = set(names)
    seen = {row["source_file"] for row in imported["nodes"] if row.get("source_file")}
    if seen != allowed:
        raise ValueError("Graphify source files differ from explicit allowlist")
    for edge in imported["edges"]:
        if edge.get("source_file") and edge["source_file"] not in allowed:
            raise ValueError("unexpected Graphify edge source file")
    # Edge sequence IDs change with traversal order. Fingerprint semantics
    # and multiplicities instead, so independent equivalent scans reconcile.
    relations = Counter(
        json.dumps({
            k: edge.get(k) for k in (
                "source", "target", "relation", "confidence",
                "source_file", "source_location",
            )
        }, sort_keys=True, separators=(",", ":"))
        for edge in imported["edges"]
    )
    result = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "source_manifest": current,
        "node_count": len(imported["nodes"]),
        "edge_count": len(imported["edges"]),
        "node_ids": sorted(node["id"] for node in imported["nodes"]),
        "relation_occurrences": [[key, count] for key, count in sorted(relations.items())],
        "graph_sha256": _hash({
            "nodes": sorted(imported["nodes"], key=lambda row: row["id"]),
            "relation_occurrences": [[key, count] for key, count in sorted(relations.items())],
        }),
    }
    result["snapshot_sha256"] = _hash(result)
    return result


def assert_snapshot_current(
    snapshot: Mapping[str, Any], *, source_root: str | Path,
    graphify_export: Mapping[str, Any] | None = None,
) -> None:
    """Block stale ASTRA graph context; optional export verifies extraction."""
    if not isinstance(snapshot, Mapping) or snapshot.get("schema_version") != SCHEMA:
        raise ValueError("invalid code snapshot")
    original = snapshot.get("source_manifest")
    if not isinstance(original, dict) or not isinstance(original.get("source_files"), list):
        raise ValueError("source manifest missing")
    expected = original.get("source_manifest_sha256")
    without_digest = dict(original)
    without_digest.pop("source_manifest_sha256", None)
    if expected != _hash(without_digest):
        raise ValueError("tampered source manifest")
    if snapshot.get("snapshot_sha256") != _hash({
        k: v for k, v in snapshot.items() if k != "snapshot_sha256"
    }):
        raise ValueError("tampered code snapshot")
    current = capture_curated_sources(
        source_root, files=[row["file"] for row in original["source_files"]],
    )
    if current != original:
        raise ValueError("stale Graphify source snapshot")
    if graphify_export is not None:
        check = finalize_code_snapshot(
            graphify_export, pre_extraction_sources=original,
            source_root=source_root,
        )
        if check != snapshot:
            raise ValueError("Graphify export differs from attested snapshot")


def compare_code_snapshots(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic, bounded summary for owner review; no automatic decisions."""
    for snap in (before, after):
        if (not isinstance(snap, Mapping) or snap.get("schema_version") != SCHEMA or
                snap.get("snapshot_sha256") != _hash({
                    k: v for k, v in snap.items() if k != "snapshot_sha256"
                })):
            raise ValueError("untrusted Graphify snapshot")
    a = {r["file"]: r["sha256"] for r in before["source_manifest"]["source_files"]}
    b = {r["file"]: r["sha256"] for r in after["source_manifest"]["source_files"]}
    before_rel = dict(before["relation_occurrences"])
    after_rel = dict(after["relation_occurrences"])
    added = sum(max(0, after_rel.get(k, 0) - before_rel.get(k, 0)) for k in after_rel)
    removed = sum(max(0, before_rel.get(k, 0) - after_rel.get(k, 0)) for k in before_rel)
    return {
        "mode": "OBSERVE",
        "execution_authority": "none",
        "before_snapshot_sha256": before["snapshot_sha256"],
        "after_snapshot_sha256": after["snapshot_sha256"],
        "added_files": sorted(set(b) - set(a)),
        "removed_files": sorted(set(a) - set(b)),
        "changed_files": sorted(k for k in set(a) & set(b) if a[k] != b[k]),
        "added_relation_occurrences": added,
        "removed_relation_occurrences": removed,
        "owner_review_required": before["snapshot_sha256"] != after["snapshot_sha256"],
    }


def build_attested_astra_packet(
    *, graphify_export_path: str | Path, snapshot: Mapping[str, Any],
    source_root: str | Path, buyer_graph, focus: str,
    privacy_key: bytes, approved_category_labels: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Existing-owner opt-in: reject stale graph, then return read-only context."""
    path = Path(graphify_export_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 50_000_000:
        raise ValueError("unsafe Graphify export path")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert_snapshot_current(snapshot, source_root=source_root, graphify_export=raw)
    result = build_astra_graph_packet(
        code_graph_path=path, buyer_graph=buyer_graph, focus=focus,
        privacy_key=privacy_key, approved_category_labels=approved_category_labels,
    )
    result["code_snapshot_sha256"] = snapshot["snapshot_sha256"]
    result["code_freshness_verified"] = True
    return result
