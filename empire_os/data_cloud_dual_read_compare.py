"""Read-only Supabase snapshot -> EmpireDB dual-read comparison.

The source side is a fresh plain-SQL data dump produced by
`supabase db dump --linked --data-only --use-copy`. The target side is the
EmpireDB application read DSN. This module has no write, delete, schema-change,
fallback, or production-cutover authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Sequence

import psycopg
from psycopg import sql

from empire_os.data_cloud_shadow_copy import SHADOW_TABLES, ShadowTable, validate_manifest
from empire_os.data_cloud_shadow_dump_import import CopyBlock, scan_dump


def _digest_primary_keys(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(values):
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _target_state(
    connection: psycopg.Connection[Any],
    item: ShadowTable,
) -> tuple[int, str]:
    count_stmt = sql.SQL("SELECT count(*) FROM public.{}").format(
        sql.Identifier(item.name)
    )
    count = int(connection.execute(count_stmt).fetchone()[0])

    pk_stmt = sql.SQL(
        "SELECT {}::text FROM public.{} ORDER BY {}::text"
    ).format(
        sql.Identifier(item.primary_key),
        sql.Identifier(item.name),
        sql.Identifier(item.primary_key),
    )
    values = [str(row[0]) for row in connection.execute(pk_stmt).fetchall()]
    return count, _digest_primary_keys(values)


def compare_snapshot_to_empiredb(
    blocks: dict[str, CopyBlock],
    dsn: str,
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, Any]:
    validate_manifest(tables)
    results: list[dict[str, Any]] = []
    equal_tables = 0
    source_ahead_tables = 0
    target_ahead_tables = 0
    identity_drift_tables = 0

    with psycopg.connect(
        dsn,
        connect_timeout=5,
        application_name="empire-dual-read-compare",
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET statement_timeout = '10min'")

        for item in tables:
            source = blocks[item.name]
            target_rows, target_digest = _target_state(connection, item)

            if (
                source.row_count == target_rows
                and source.primary_key_sha256 == target_digest
            ):
                state = "equal"
                equal_tables += 1
            elif source.row_count > target_rows:
                state = "source_ahead"
                source_ahead_tables += 1
            elif target_rows > source.row_count:
                state = "target_ahead"
                target_ahead_tables += 1
            else:
                state = "identity_drift"
                identity_drift_tables += 1

            result = {
                "table": item.name,
                "primary_key": item.primary_key,
                "source_rows": source.row_count,
                "target_rows": target_rows,
                "row_delta": source.row_count - target_rows,
                "source_pk_sha256": source.primary_key_sha256,
                "target_pk_sha256": target_digest,
                "state": state,
                "equal": state == "equal",
            }
            results.append(result)
            print(json.dumps(result, sort_keys=True))

    return {
        "schema_version": "empire.dual-read-compare.v1",
        "source": "supabase_db_dump_snapshot",
        "target": "empiredb",
        "read_only": True,
        "canonical_backend_unchanged": True,
        "dual_write_enabled": False,
        "write_fallback_enabled": False,
        "production_cutover_authority": False,
        "tables_compared": len(results),
        "equal_tables": equal_tables,
        "source_ahead_tables": source_ahead_tables,
        "target_ahead_tables": target_ahead_tables,
        "identity_drift_tables": identity_drift_tables,
        "all_equal": equal_tables == len(results),
        "tables": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dump-path",
        default="runtime/data_cloud/supabase_public_data.sql",
    )
    parser.add_argument(
        "--output-path",
        default="runtime/data_cloud/dual_read_compare_latest.json",
    )
    args = parser.parse_args(argv)

    dsn = os.environ.get("EMPIREDB_DSN")
    if not dsn:
        raise RuntimeError("EMPIREDB_DSN is required")

    dump_path = Path(args.dump_path)
    if not dump_path.is_file():
        raise RuntimeError(f"source dump not found: {dump_path}")

    blocks = scan_dump(dump_path)
    report = compare_snapshot_to_empiredb(blocks, dsn)

    output = Path(args.output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "all_equal": report["all_equal"],
        "tables_compared": report["tables_compared"],
        "equal_tables": report["equal_tables"],
        "source_ahead_tables": report["source_ahead_tables"],
        "target_ahead_tables": report["target_ahead_tables"],
        "identity_drift_tables": report["identity_drift_tables"],
        "read_only": report["read_only"],
        "canonical_backend_unchanged": report["canonical_backend_unchanged"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
