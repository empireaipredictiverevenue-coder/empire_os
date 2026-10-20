"""Read-only health check for the current, genuine EmpireOS code AST graph."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

from empire_os.graphify_code_snapshot import assert_snapshot_current
from empire_os.graphify_dual_bridge import import_graphify_code
from empire_os.coder.graphify_relevance import rank_attested_code_paths

GRAPH = "runtime/graphify/attested_coder_20261020/graphify-out/graph.json"
MANIFEST = "runtime/graphify/attested_coder_manifest_20261020.json"
SYMBOLS = ("ContextBuilder", "CoderTaskWorker", "LocalJobQueue",
           "GraphifyContextSource")


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 50_000_000:
        raise ValueError("unsafe private graph input")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid private graph format")
    return data


def review(root: Path) -> dict:
    root = root.resolve(strict=True)
    graph = read_json(root / GRAPH)
    manifest = read_json(root / MANIFEST)
    sources = manifest.get("source_manifest", {}).get("source_files")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 64:
        raise ValueError("invalid source manifest")
    changed = []
    for row in sources:
        rel = row.get("file") if isinstance(row, dict) else None
        if not isinstance(rel, str) or len(rel) > 500:
            raise ValueError("invalid source name")
        p = PurePosixPath(rel)
        if (p.is_absolute() or p.as_posix() != rel or
                not rel.endswith(".py") or
                any(part in ("", ".", "..") for part in p.parts)):
            raise ValueError("unsafe source name")
        file = root
        unsafe = False
        for part in p.parts:
            file = file / part
            unsafe |= file.is_symlink()
        if unsafe or not file.is_file():
            changed.append({"path": rel, "state": "MISSING_OR_UNSAFE"})
            continue
        payload = file.read_bytes()
        if (len(payload) != row.get("bytes") or
                sha256(payload).hexdigest() != row.get("sha256")):
            changed.append({"path": rel, "state": "SOURCE_DIGEST_CHANGED"})
    current = False
    if not changed:
        try:
            assert_snapshot_current(manifest, source_root=root, graphify_export=graph)
            current = True
        except (ValueError, KeyError, TypeError):
            pass
    return build_report(graph, sources, changed, current)


def build_report(graph: dict, sources: list, changed: list, current: bool) -> dict:
    symbols = []
    count_nodes = None
    count_edges = None
    if current:
        code = import_graphify_code(graph)
        count_nodes, count_edges = len(code["nodes"]), len(code["edges"])
        for name in SYMBOLS:
            ranked = rank_attested_code_paths(code, terms=(name,), max_files=1)
            symbols.append({
                "symbol": name,
                "exact_symbol_found": bool(
                    ranked and ranked[0]["reason"] == "EXACT_SYMBOL"
                ),
            })
    return {
        "schema_version": "empire.graphify.code_graph_health.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "status": (
            "SOURCE_DRIFT" if changed else
            "CURRENT_ATTESTED_CODE" if current else "INVALID_GRAPH_OR_MANIFEST"
        ),
        "indexed_source_count": len(sources),
        "unchanged_source_count": len(sources) - len(changed),
        "changed_source_files": changed,
        "code_graph_nodes": count_nodes,
        "code_graph_edges": count_edges,
        "real_code_symbol_coverage": symbols,
        "refresh_required_before_code_context": not current,
        "customer_records_read": False,
        "worker_restarted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
