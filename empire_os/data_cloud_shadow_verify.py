"""Independent read-only verification of an EmpireDB shadow import.

This verifier does not share the dump importer's target verification path. It
reads the committed import report, queries EmpireDB through the application
read DSN, recomputes row counts and primary-key digests, and fails closed on
any mismatch. It has no write, delete, schema, or cutover authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg import sql

from empire_os.data_cloud_shadow_copy import SHADOW_TABLES, ShadowTable, validate_manifest


def digest_primary_keys(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(values):
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_expected(
    report_path: str | os.PathLike[str],
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, dict[str, Any]]:
    validate_manifest(tables)
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "empire.shadow-dump-import.v1":
        raise RuntimeError("unexpected shadow import report schema")
    if payload.get("verified") is not True:
        raise RuntimeError("shadow import report is not verified")
    rows = payload.get("tables")
    if not isinstance(rows, list):
        raise RuntimeError("shadow import report tables must be a list")

    expected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise RuntimeError("invalid table verification row")
        table = str(row.get("table", ""))
        if not table or table in expected:
            raise RuntimeError(f"invalid or duplicate table in report: {table!r}")
        expected[table] = dict(row)

    wanted = {item.name for item in tables}
    missing = sorted(wanted - set(expected))
    extra = sorted(set(expected) - wanted)
    if missing or extra:
        raise RuntimeError(
            f"shadow import report manifest mismatch: missing={missing}, extra={extra}"
        )
    return expected


def verify_empiredb(
    dsn: str,
    expected: Mapping[str, Mapping[str, Any]],
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, Any]:
    validate_manifest(tables)
    results: list[dict[str, Any]] = []
    with psycopg.connect(
        dsn,
        connect_timeout=5,
        application_name="empire-shadow-independent-verify",
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET statement_timeout = '10min'")

        for item in tables:
            count_stmt = sql.SQL("SELECT count(*) FROM public.{}").format(
                sql.Identifier(item.name)
            )
            target_rows = int(connection.execute(count_stmt).fetchone()[0])

            pk_stmt = sql.SQL(
                "SELECT {}::text FROM public.{} ORDER BY {}::text"
            ).format(
                sql.Identifier(item.primary_key),
                sql.Identifier(item.name),
                sql.Identifier(item.primary_key),
            )
            keys = [str(row[0]) for row in connection.execute(pk_stmt).fetchall()]
            target_digest = digest_primary_keys(keys)

            source = expected[item.name]
            source_rows = int(source["source_rows"])
            source_digest = str(source["source_pk_sha256"])
            verified = (
                target_rows == source_rows
                and target_digest == source_digest
            )
            result = {
                "table": item.name,
                "source_rows": source_rows,
                "target_rows": target_rows,
                "source_pk_sha256": source_digest,
                "target_pk_sha256": target_digest,
                "verified": verified,
            }
            results.append(result)
            print(json.dumps(result, sort_keys=True))
            if not verified:
                raise RuntimeError(f"{item.name}: independent verification mismatch")

    return {
        "schema_version": "empire.shadow-independent-verify.v1",
        "read_only": True,
        "canonical_backend_unchanged": True,
        "production_cutover_authority": False,
        "tables_verified": len(results),
        "rows_verified": sum(item["target_rows"] for item in results),
        "verified": True,
        "tables": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-path",
        default="runtime/data_cloud/shadow_dump_import_latest.json",
    )
    parser.add_argument(
        "--output-path",
        default="runtime/data_cloud/shadow_independent_verify_latest.json",
    )
    args = parser.parse_args(argv)

    dsn = os.environ.get("EMPIREDB_DSN")
    if not dsn:
        raise RuntimeError("EMPIREDB_DSN is required")

    expected = load_expected(args.report_path)
    report = verify_empiredb(dsn, expected)

    output = Path(args.output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "verified": report["verified"],
        "tables_verified": report["tables_verified"],
        "rows_verified": report["rows_verified"],
        "read_only": report["read_only"],
        "canonical_backend_unchanged": report["canonical_backend_unchanged"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
