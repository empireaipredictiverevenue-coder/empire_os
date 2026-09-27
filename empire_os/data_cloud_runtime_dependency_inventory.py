"""Bounded runtime table dependency inventory for EmpireDB cutover readiness.

Discovers canonical public table names from the existing plain-SQL data dump,
then scans runtime source for high-confidence table access patterns. It reports
only runtime references and highlights those outside the verified EmpireDB
40-table core.

Read-only: no database access, no writes, no cutover authority.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

from empire_os.data_cloud_shadow_copy import SHADOW_TABLES


COPY_RE = re.compile(
    r'^COPY\s+(?:"public"|public)\.(?:"((?:[^"]|"")*)"|([A-Za-z_][A-Za-z0-9_]*))\s*\('
)

ACCESS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "gateway_method",
        re.compile(
            r"""\b(?:select|query|count|insert|upsert|insert_ignore_conflicts|update|delete)\s*\(\s*["']([A-Za-z_][A-Za-z0-9_]*)["']"""
        ),
    ),
    (
        "client_from",
        re.compile(r"""\.from\s*\(\s*["']([A-Za-z_][A-Za-z0-9_]*)["']"""),
    ),
    (
        "postgrest_path",
        re.compile(r"""/rest/v1/([A-Za-z_][A-Za-z0-9_]*)"""),
    ),
    (
        "public_sql",
        re.compile(
            r"""\b(?:FROM|JOIN|INTO|UPDATE)\s+public\.["']?([A-Za-z_][A-Za-z0-9_]*)["']?""",
            re.IGNORECASE,
        ),
    ),
)

RUNTIME_ROOTS = ("empire_os", "apps", "scripts", "systemd", "infra")
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sh", ".service", ".timer", ".sql",
}
EXCLUDED_PARTS = {
    ".git", ".venv", "node_modules", "__pycache__", "tests", "test",
    "docs", "migrations", "recovery", "toop", "runtime", ".next",
}


def discover_source_tables(dump_path: Path) -> set[str]:
    tables: set[str] = set()
    with dump_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = COPY_RE.match(line)
            if not match:
                continue
            name = match.group(1) or match.group(2)
            tables.add(name.replace('""', '"'))
    if not tables:
        raise RuntimeError(f"no public COPY tables found in {dump_path}")
    return tables


def iter_runtime_files(repo_root: Path) -> Iterable[Path]:
    for root_name in RUNTIME_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in EXCLUDED_PARTS for part in file_path.parts):
                continue
            if file_path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            yield file_path


def scan_runtime(
    repo_root: Path,
    source_tables: set[str],
) -> dict[str, list[dict[str, object]]]:
    hits: dict[str, list[dict[str, object]]] = {}
    for file_path in iter_runtime_files(repo_root):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = str(file_path.relative_to(repo_root))
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in ACCESS_PATTERNS:
                for match in pattern.finditer(line):
                    table = match.group(1)
                    if table not in source_tables:
                        continue
                    hits.setdefault(table, []).append({
                        "file": relative,
                        "line": line_number,
                        "kind": kind,
                        "excerpt": line.strip()[:240],
                    })
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dump-path",
        default="runtime/data_cloud/supabase_public_data.sql",
    )
    parser.add_argument(
        "--output-path",
        default="runtime/data_cloud/runtime_dependency_inventory_latest.json",
    )
    args = parser.parse_args()

    repo_root = Path.cwd()
    dump_path = repo_root / args.dump_path
    if not dump_path.is_file():
        raise RuntimeError(f"canonical source dump missing: {dump_path}")

    source_tables = discover_source_tables(dump_path)
    migrated = {item.name for item in SHADOW_TABLES}
    hits = scan_runtime(repo_root, source_tables)

    runtime_tables = sorted(hits)
    unmigrated = sorted(set(runtime_tables) - migrated)
    migrated_runtime = sorted(set(runtime_tables) & migrated)

    report = {
        "schema_version": "empire.runtime-dependency-inventory.v1",
        "read_only": True,
        "production_cutover_authority": False,
        "source_public_tables_discovered": len(source_tables),
        "verified_core_tables": len(migrated),
        "runtime_referenced_tables": len(runtime_tables),
        "migrated_runtime_tables": migrated_runtime,
        "unmigrated_runtime_tables": unmigrated,
        "unmigrated_runtime_count": len(unmigrated),
        "hits": {table: hits[table] for table in runtime_tables},
    }

    output = repo_root / args.output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "source_public_tables_discovered": len(source_tables),
        "verified_core_tables": len(migrated),
        "runtime_referenced_tables": len(runtime_tables),
        "unmigrated_runtime_count": len(unmigrated),
        "unmigrated_runtime_tables": unmigrated,
        "read_only": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
