"""Semantic Supabase -> EmpireDB schema comparator.

Read-only. Compares column structure/defaults, RLS state, constraints and
indexes while ignoring object names and ordering. No DDL or cutover authority.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import psycopg

from empire_os.data_cloud_shadow_copy import SHADOW_TABLES, validate_manifest
from empire_os.data_cloud_schema_semantic import SQL as TARGET_SQL


def _compact_expr(value: Any) -> Any:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    text = text.replace("public.", "")
    return text


def _default(value: Any) -> Any:
    text = _compact_expr(value)
    if text is None:
        return None
    if re.fullmatch(r"NULL(?:::[A-Za-z0-9_\[\] ]+)?", text, flags=re.I):
        return None
    return text


def _constraint_key(item: dict[str, Any]) -> str | None:
    # PostgreSQL 18 catalogs NOT NULL constraints (contype='n') separately;
    # canonical Supabase is PostgreSQL 17 where they are represented only via
    # pg_attribute/information_schema. Column nullability is compared elsewhere.
    if item.get("type") == "n":
        return None
    clean = {
        "type": item.get("type"),
        "columns": list(item.get("columns") or []),
        "ref_table": (
            str(item.get("ref_table")).removeprefix("public.")
            if item.get("ref_table") is not None else None
        ),
        "ref_columns": list(item.get("ref_columns") or []),
        "delete_action": item.get("delete_action"),
        "update_action": item.get("update_action"),
        "expr": _compact_expr(item.get("expr")),
    }
    return json.dumps(clean, sort_keys=True, separators=(",", ":"))


def _index_key(item: dict[str, Any]) -> str:
    clean = {
        "unique": bool(item.get("unique")),
        "primary": bool(item.get("primary")),
        "keys": [_compact_expr(v) for v in (item.get("keys") or [])],
        "predicate": _compact_expr(item.get("predicate")),
    }
    return json.dumps(clean, sort_keys=True, separators=(",", ":"))


def _multiset(items: Iterable[dict[str, Any]], key_fn) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        key = key_fn(item)
        if key is None:
            continue
        result[key] = result.get(key, 0) + 1
    return result


def _delta(left: dict[str, int], right: dict[str, int]) -> list[str]:
    out: list[str] = []
    for key, count in left.items():
        missing = count - right.get(key, 0)
        out.extend([key] * max(0, missing))
    return out


def _column_diff(source: list[dict[str, Any]], target: list[dict[str, Any]]) -> dict[str, Any]:
    src = {x["name"]: x for x in source}
    dst = {x["name"]: x for x in target}
    missing = sorted(set(src) - set(dst))
    extra = sorted(set(dst) - set(src))
    structure: list[dict[str, Any]] = []
    defaults: list[dict[str, Any]] = []
    fields = ("ordinal", "udt", "nullable", "char_max", "precision", "scale")
    for name in sorted(set(src) & set(dst)):
        changed = {
            field: {"source": src[name].get(field), "target": dst[name].get(field)}
            for field in fields
            if src[name].get(field) != dst[name].get(field)
        }
        if changed:
            structure.append({"column": name, "differences": changed})
        sdef, ddef = _default(src[name].get("default")), _default(dst[name].get("default"))
        if sdef != ddef:
            defaults.append({"column": name, "source": sdef, "target": ddef})
    return {
        "missing_columns": missing,
        "extra_columns": extra,
        "structure_differences": structure,
        "default_differences": defaults,
    }


def _load_source(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "empire.canonical-supabase-schema.v1":
        raise RuntimeError("unexpected canonical schema snapshot version")
    return dict(payload["tables"])


def _target(dsn: str) -> dict[str, Any]:
    validate_manifest()
    names = sorted(item.name for item in SHADOW_TABLES)
    with psycopg.connect(
        dsn, connect_timeout=5, application_name="empire-schema-semantic-compare"
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        rows = connection.execute(TARGET_SQL, (names,)).fetchall()
    return {
        row[0]: {
            "rls_enabled": bool(row[1]),
            "rls_forced": bool(row[2]),
            "columns": row[3],
            "constraints": row[4],
            "indexes": row[5],
        }
        for row in rows
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-path",
        default="empire_os/data_cloud_canonical_schema.json",
    )
    parser.add_argument(
        "--output-path",
        default="runtime/data_cloud/schema_semantic_compare_latest.json",
    )
    args = parser.parse_args()

    dsn = os.environ.get("EMPIREDB_DSN")
    if not dsn:
        raise RuntimeError("EMPIREDB_DSN is required")

    source = _load_source(Path(args.source_path))
    target = _target(dsn)
    results: list[dict[str, Any]] = []

    for table in sorted(source):
        src = source[table]
        dst = target.get(table)
        if dst is None:
            results.append({"table": table, "match": False, "missing_table": True})
            continue

        columns = _column_diff(src["columns"], dst["columns"])
        src_cons = _multiset(src["constraints"], _constraint_key)
        dst_cons = _multiset(dst["constraints"], _constraint_key)
        src_idx = _multiset(src["indexes"], _index_key)
        dst_idx = _multiset(dst["indexes"], _index_key)

        result = {
            "table": table,
            "rls_source": bool(src["rls_enabled"]),
            "rls_target": bool(dst["rls_enabled"]),
            "rls_forced_source": bool(src["rls_forced"]),
            "rls_forced_target": bool(dst["rls_forced"]),
            **columns,
            "missing_constraints": [json.loads(v) for v in _delta(src_cons, dst_cons)],
            "extra_constraints": [json.loads(v) for v in _delta(dst_cons, src_cons)],
            "missing_indexes": [json.loads(v) for v in _delta(src_idx, dst_idx)],
            "extra_indexes": [json.loads(v) for v in _delta(dst_idx, src_idx)],
        }
        result["match"] = not any([
            result["rls_source"] != result["rls_target"],
            result["rls_forced_source"] != result["rls_forced_target"],
            result["missing_columns"],
            result["extra_columns"],
            result["structure_differences"],
            result["default_differences"],
            result["missing_constraints"],
            result["extra_constraints"],
            result["missing_indexes"],
            result["extra_indexes"],
        ])
        results.append(result)

    report = {
        "schema_version": "empire.schema-semantic-compare.v1",
        "read_only": True,
        "tables_compared": len(results),
        "tables_matching": sum(1 for x in results if x.get("match")),
        "tables_different": sum(1 for x in results if not x.get("match")),
        "all_equal": all(x.get("match") for x in results),
        "tables": results,
    }
    path = Path(args.output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "tables_compared": report["tables_compared"],
        "tables_matching": report["tables_matching"],
        "tables_different": report["tables_different"],
        "all_equal": report["all_equal"],
        "read_only": True,
    }, sort_keys=True))
    for item in results:
        if item.get("match"):
            continue
        summary = {
            "table": item["table"],
            "rls_missing": item.get("rls_source") and not item.get("rls_target"),
            "column_structure": len(item.get("structure_differences", [])),
            "column_defaults": len(item.get("default_differences", [])),
            "missing_constraints": len(item.get("missing_constraints", [])),
            "extra_constraints": len(item.get("extra_constraints", [])),
            "missing_indexes": len(item.get("missing_indexes", [])),
            "extra_indexes": len(item.get("extra_indexes", [])),
        }
        print(json.dumps(summary, sort_keys=True))
        if item.get("structure_differences"):
            print(json.dumps({
                "table": item["table"],
                "structure_differences": item["structure_differences"],
            }, sort_keys=True))
        if item.get("default_differences"):
            print(json.dumps({
                "table": item["table"],
                "default_differences": item["default_differences"],
            }, sort_keys=True))
        if item.get("missing_indexes"):
            print(json.dumps({
                "table": item["table"],
                "missing_indexes": item["missing_indexes"],
            }, sort_keys=True))
        if item.get("missing_constraints"):
            print(json.dumps({
                "table": item["table"],
                "missing_constraints": item["missing_constraints"],
            }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
