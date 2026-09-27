"""Transactional pg_dump COPY importer for EmpireDB shadow migration.

This module consumes a plain SQL data-only pg_dump generated from the canonical
source database. It imports only the explicit Empire Data Cloud shadow manifest,
requires all target tables to be empty, never truncates or deletes, and has no
authority to change the canonical backend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Mapping, Sequence

import psycopg
from psycopg import sql

from empire_os.data_cloud_shadow_copy import SHADOW_TABLES, ShadowTable, validate_manifest


_COPY_HEADER = re.compile(
    rb'^COPY (?:"?public"?\.)"?(?P<table>[A-Za-z_][A-Za-z0-9_]*)"? '
    rb'\((?P<columns>[^)]*)\) FROM stdin;\r?\n

@dataclass(frozen=True)
class CopyBlock:
    table: str
    columns: tuple[str, ...]
    data_start: int
    data_end: int
    row_count: int
    primary_key_sha256: str


def _safe_column(value: str) -> str:
    if not _COLUMN.fullmatch(value):
        raise ValueError(f"unsafe COPY column: {value!r}")
    return value


def _decode_copy_text(value: bytes) -> str | None:
    if value == b"\\N":
        return None
    out = bytearray()
    index = 0
    simple = {
        ord("b"): 8,
        ord("f"): 12,
        ord("n"): 10,
        ord("r"): 13,
        ord("t"): 9,
        ord("v"): 11,
        ord("\\"): 92,
    }
    while index < len(value):
        byte = value[index]
        if byte != 92:
            out.append(byte)
            index += 1
            continue
        index += 1
        if index >= len(value):
            out.append(92)
            break
        marker = value[index]
        if marker in simple:
            out.append(simple[marker])
            index += 1
            continue
        if marker == ord("x"):
            index += 1
            digits = bytearray()
            while index < len(value) and len(digits) < 2:
                current = value[index]
                if current not in b"0123456789abcdefABCDEF":
                    break
                digits.append(current)
                index += 1
            if not digits:
                out.extend(b"\\x")
            else:
                out.append(int(digits.decode("ascii"), 16))
            continue
        if marker in b"01234567":
            digits = bytearray()
            while index < len(value) and len(digits) < 3:
                current = value[index]
                if current not in b"01234567":
                    break
                digits.append(current)
                index += 1
            out.append(int(digits.decode("ascii"), 8))
            continue
        out.append(marker)
        index += 1
    return out.decode("utf-8")


def _digest_strings(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(values):
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def scan_dump(
    path: str | os.PathLike[str],
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, CopyBlock]:
    validate_manifest(tables)
    wanted = {item.name: item for item in tables}
    blocks: dict[str, CopyBlock] = {}

    with open(path, "rb") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            match = _COPY_HEADER.match(line)
            if not match:
                continue

            table = _safe_column(match.group("table").decode("ascii"))
            raw_columns = match.group("columns").decode("ascii")
            columns = tuple(
                _unquote_identifier(part)
                for part in raw_columns.split(",")
                if part.strip()
            )
            data_start = handle.tell()
            row_count = 0
            primary_keys: list[str] = []
            item = wanted.get(table)
            pk_index: int | None = None
            if item is not None:
                if table in blocks:
                    raise RuntimeError(f"{table}: duplicate COPY block in source dump")
                try:
                    pk_index = columns.index(item.primary_key)
                except ValueError as exc:
                    raise RuntimeError(
                        f"{table}: source COPY is missing primary key "
                        f"{item.primary_key!r}"
                    ) from exc

            data_end = data_start
            while True:
                row_start = handle.tell()
                row = handle.readline()
                if not row:
                    raise RuntimeError(f"{table}: unterminated COPY block")
                if row in {b"\\.\n", b"\\.\r\n", b"\\."}:
                    data_end = row_start
                    break
                if item is None:
                    continue
                values = row.rstrip(b"\r\n").split(b"\t")
                if len(values) != len(columns):
                    raise RuntimeError(
                        f"{table}: COPY row has {len(values)} fields; "
                        f"expected {len(columns)}"
                    )
                primary_key = _decode_copy_text(values[pk_index])
                if primary_key is None:
                    raise RuntimeError(f"{table}: NULL primary key in source dump")
                primary_keys.append(primary_key)
                row_count += 1

            if item is not None:
                blocks[table] = CopyBlock(
                    table=table,
                    columns=columns,
                    data_start=data_start,
                    data_end=data_end,
                    row_count=row_count,
                    primary_key_sha256=_digest_strings(primary_keys),
                )

    missing = [item.name for item in tables if item.name not in blocks]
    if missing:
        raise RuntimeError(
            "source dump is missing required COPY block(s): "
            + ", ".join(missing)
        )
    return blocks


class DumpEmpireTarget:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def connect(self) -> psycopg.Connection[Any]:
        connection = psycopg.connect(
            self.dsn,
            connect_timeout=5,
            application_name="empire-shadow-dump-import",
        )
        connection.execute("SET ROLE empiredb_migrator")
        connection.execute("SET statement_timeout = '10min'")
        return connection

    @staticmethod
    def columns(
        connection: psycopg.Connection[Any],
        table: str,
    ) -> tuple[str, ...]:
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (table,),
        ).fetchall()
        if not rows:
            raise RuntimeError(f"{table}: target table does not exist")
        return tuple(str(row[0]) for row in rows)

    @staticmethod
    def count(connection: psycopg.Connection[Any], table: str) -> int:
        statement = sql.SQL("SELECT count(*) FROM public.{}").format(
            sql.Identifier(table)
        )
        return int(connection.execute(statement).fetchone()[0])

    @staticmethod
    def primary_keys(
        connection: psycopg.Connection[Any],
        item: ShadowTable,
    ) -> list[str]:
        statement = sql.SQL(
            "SELECT {}::text FROM public.{} ORDER BY {}"
        ).format(
            sql.Identifier(item.primary_key),
            sql.Identifier(item.name),
            sql.Identifier(item.primary_key),
        )
        return [str(row[0]) for row in connection.execute(statement).fetchall()]


def build_plan(
    blocks: Mapping[str, CopyBlock],
    target: DumpEmpireTarget,
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_empty = True
    all_compatible = True
    with target.connect() as connection:
        for item in tables:
            block = blocks[item.name]
            target_columns = target.columns(connection, item.name)
            missing_target = sorted(set(block.columns) - set(target_columns))
            target_count = target.count(connection, item.name)
            table_empty = target_count == 0
            compatible = not missing_target
            all_empty = all_empty and table_empty
            all_compatible = all_compatible and compatible
            rows.append(
                {
                    "table": item.name,
                    "primary_key": item.primary_key,
                    "source_rows": block.row_count,
                    "target_rows": target_count,
                    "target_empty": table_empty,
                    "source_columns": len(block.columns),
                    "target_columns": len(target_columns),
                    "missing_target_columns": missing_target,
                    "schema_compatible": compatible,
                    "source_pk_sha256": block.primary_key_sha256,
                }
            )

    return {
        "schema_version": "empire.shadow-dump-plan.v1",
        "canonical_backend_unchanged": True,
        "source_delete_authority": False,
        "target_delete_authority": False,
        "production_cutover_authority": False,
        "all_targets_empty": all_empty,
        "schema_compatible": all_compatible,
        "tables": rows,
    }


def _write_block_to_copy(
    dump: BinaryIO,
    connection: psycopg.Connection[Any],
    block: CopyBlock,
) -> None:
    columns = sql.SQL(", ").join(sql.Identifier(name) for name in block.columns)
    statement = sql.SQL(
        "COPY public.{} ({}) FROM STDIN WITH (FORMAT text)"
    ).format(sql.Identifier(block.table), columns)

    dump.seek(block.data_start)
    remaining = block.data_end - block.data_start
    with connection.cursor().copy(statement) as copy:
        while remaining:
            chunk = dump.read(min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError(f"{block.table}: unexpected EOF during COPY")
            copy.write(chunk)
            remaining -= len(chunk)


def import_dump(
    dump_path: str | os.PathLike[str],
    blocks: Mapping[str, CopyBlock],
    target: DumpEmpireTarget,
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, Any]:
    preflight = build_plan(blocks, target, tables)
    if not preflight["schema_compatible"]:
        raise RuntimeError("shadow dump import blocked: schema incompatibility")
    if not preflight["all_targets_empty"]:
        raise RuntimeError(
            "shadow dump import blocked: target tables are not empty; "
            "no delete or truncate authority is available"
        )

    verification: list[dict[str, Any]] = []
    with open(dump_path, "rb") as dump:
        with target.connect() as connection:
            with connection.transaction():
                for item in tables:
                    block = blocks[item.name]
                    _write_block_to_copy(dump, connection, block)
                    target_count = target.count(connection, item.name)
                    target_pk_sha256 = _digest_strings(
                        target.primary_keys(connection, item)
                    )
                    verified = (
                        target_count == block.row_count
                        and target_pk_sha256 == block.primary_key_sha256
                    )
                    result = {
                        "table": item.name,
                        "source_rows": block.row_count,
                        "target_rows": target_count,
                        "source_pk_sha256": block.primary_key_sha256,
                        "target_pk_sha256": target_pk_sha256,
                        "verified": verified,
                    }
                    verification.append(result)
                    print(json.dumps(result, sort_keys=True), flush=True)
                    if not verified:
                        raise RuntimeError(
                            f"{item.name}: shadow import verification failed"
                        )

    return {
        "schema_version": "empire.shadow-dump-import.v1",
        "canonical_backend_unchanged": True,
        "source_delete_authority": False,
        "target_delete_authority": False,
        "production_cutover_authority": False,
        "verified": all(row["verified"] for row in verification),
        "tables": verification,
    }


def _target_from_env() -> DumpEmpireTarget:
    dsn = os.getenv("EMPIREDB_MIGRATOR_DSN", "").strip()
    if not dsn:
        raise RuntimeError("EMPIREDB_MIGRATOR_DSN is required")
    return DumpEmpireTarget(dsn)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transactional EmpireDB shadow import from pg_dump COPY data"
    )
    parser.add_argument("--dump-path", required=True)
    parser.add_argument("--mode", choices=("plan", "copy"), default="plan")
    parser.add_argument(
        "--report-path",
        default="runtime/data_cloud/shadow_dump_latest.json",
    )
    args = parser.parse_args(argv)

    path = Path(args.dump_path)
    if not path.is_file():
        raise RuntimeError(f"source dump not found: {path}")

    blocks = scan_dump(path)
    target = _target_from_env()
    if args.mode == "plan":
        report = build_plan(blocks, target)
    else:
        report = import_dump(path, blocks, target)

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

)
_COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _unquote_identifier(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1].replace('""', '"')
    return _safe_column(value)


@dataclass(frozen=True)
class CopyBlock:
    table: str
    columns: tuple[str, ...]
    data_start: int
    data_end: int
    row_count: int
    primary_key_sha256: str


def _safe_column(value: str) -> str:
    if not _COLUMN.fullmatch(value):
        raise ValueError(f"unsafe COPY column: {value!r}")
    return value


def _decode_copy_text(value: bytes) -> str | None:
    if value == b"\\N":
        return None
    out = bytearray()
    index = 0
    simple = {
        ord("b"): 8,
        ord("f"): 12,
        ord("n"): 10,
        ord("r"): 13,
        ord("t"): 9,
        ord("v"): 11,
        ord("\\"): 92,
    }
    while index < len(value):
        byte = value[index]
        if byte != 92:
            out.append(byte)
            index += 1
            continue
        index += 1
        if index >= len(value):
            out.append(92)
            break
        marker = value[index]
        if marker in simple:
            out.append(simple[marker])
            index += 1
            continue
        if marker == ord("x"):
            index += 1
            digits = bytearray()
            while index < len(value) and len(digits) < 2:
                current = value[index]
                if current not in b"0123456789abcdefABCDEF":
                    break
                digits.append(current)
                index += 1
            if not digits:
                out.extend(b"\\x")
            else:
                out.append(int(digits.decode("ascii"), 16))
            continue
        if marker in b"01234567":
            digits = bytearray()
            while index < len(value) and len(digits) < 3:
                current = value[index]
                if current not in b"01234567":
                    break
                digits.append(current)
                index += 1
            out.append(int(digits.decode("ascii"), 8))
            continue
        out.append(marker)
        index += 1
    return out.decode("utf-8")


def _digest_strings(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(values):
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def scan_dump(
    path: str | os.PathLike[str],
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, CopyBlock]:
    validate_manifest(tables)
    wanted = {item.name: item for item in tables}
    blocks: dict[str, CopyBlock] = {}

    with open(path, "rb") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            match = _COPY_HEADER.match(line)
            if not match:
                continue

            table = match.group(1).decode("ascii")
            raw_columns = match.group(2).decode("ascii")
            columns = tuple(
                _safe_column(part.strip())
                for part in raw_columns.split(",")
                if part.strip()
            )
            data_start = handle.tell()
            row_count = 0
            primary_keys: list[str] = []
            item = wanted.get(table)
            pk_index: int | None = None
            if item is not None:
                if table in blocks:
                    raise RuntimeError(f"{table}: duplicate COPY block in source dump")
                try:
                    pk_index = columns.index(item.primary_key)
                except ValueError as exc:
                    raise RuntimeError(
                        f"{table}: source COPY is missing primary key "
                        f"{item.primary_key!r}"
                    ) from exc

            data_end = data_start
            while True:
                row_start = handle.tell()
                row = handle.readline()
                if not row:
                    raise RuntimeError(f"{table}: unterminated COPY block")
                if row in {b"\\.\n", b"\\.\r\n", b"\\."}:
                    data_end = row_start
                    break
                if item is None:
                    continue
                values = row.rstrip(b"\r\n").split(b"\t")
                if len(values) != len(columns):
                    raise RuntimeError(
                        f"{table}: COPY row has {len(values)} fields; "
                        f"expected {len(columns)}"
                    )
                primary_key = _decode_copy_text(values[pk_index])
                if primary_key is None:
                    raise RuntimeError(f"{table}: NULL primary key in source dump")
                primary_keys.append(primary_key)
                row_count += 1

            if item is not None:
                blocks[table] = CopyBlock(
                    table=table,
                    columns=columns,
                    data_start=data_start,
                    data_end=data_end,
                    row_count=row_count,
                    primary_key_sha256=_digest_strings(primary_keys),
                )

    missing = [item.name for item in tables if item.name not in blocks]
    if missing:
        raise RuntimeError(
            "source dump is missing required COPY block(s): "
            + ", ".join(missing)
        )
    return blocks


class DumpEmpireTarget:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def connect(self) -> psycopg.Connection[Any]:
        connection = psycopg.connect(
            self.dsn,
            connect_timeout=5,
            application_name="empire-shadow-dump-import",
        )
        connection.execute("SET ROLE empiredb_migrator")
        connection.execute("SET statement_timeout = '10min'")
        return connection

    @staticmethod
    def columns(
        connection: psycopg.Connection[Any],
        table: str,
    ) -> tuple[str, ...]:
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (table,),
        ).fetchall()
        if not rows:
            raise RuntimeError(f"{table}: target table does not exist")
        return tuple(str(row[0]) for row in rows)

    @staticmethod
    def count(connection: psycopg.Connection[Any], table: str) -> int:
        statement = sql.SQL("SELECT count(*) FROM public.{}").format(
            sql.Identifier(table)
        )
        return int(connection.execute(statement).fetchone()[0])

    @staticmethod
    def primary_keys(
        connection: psycopg.Connection[Any],
        item: ShadowTable,
    ) -> list[str]:
        statement = sql.SQL(
            "SELECT {}::text FROM public.{} ORDER BY {}"
        ).format(
            sql.Identifier(item.primary_key),
            sql.Identifier(item.name),
            sql.Identifier(item.primary_key),
        )
        return [str(row[0]) for row in connection.execute(statement).fetchall()]


def build_plan(
    blocks: Mapping[str, CopyBlock],
    target: DumpEmpireTarget,
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_empty = True
    all_compatible = True
    with target.connect() as connection:
        for item in tables:
            block = blocks[item.name]
            target_columns = target.columns(connection, item.name)
            missing_target = sorted(set(block.columns) - set(target_columns))
            target_count = target.count(connection, item.name)
            table_empty = target_count == 0
            compatible = not missing_target
            all_empty = all_empty and table_empty
            all_compatible = all_compatible and compatible
            rows.append(
                {
                    "table": item.name,
                    "primary_key": item.primary_key,
                    "source_rows": block.row_count,
                    "target_rows": target_count,
                    "target_empty": table_empty,
                    "source_columns": len(block.columns),
                    "target_columns": len(target_columns),
                    "missing_target_columns": missing_target,
                    "schema_compatible": compatible,
                    "source_pk_sha256": block.primary_key_sha256,
                }
            )

    return {
        "schema_version": "empire.shadow-dump-plan.v1",
        "canonical_backend_unchanged": True,
        "source_delete_authority": False,
        "target_delete_authority": False,
        "production_cutover_authority": False,
        "all_targets_empty": all_empty,
        "schema_compatible": all_compatible,
        "tables": rows,
    }


def _write_block_to_copy(
    dump: BinaryIO,
    connection: psycopg.Connection[Any],
    block: CopyBlock,
) -> None:
    columns = sql.SQL(", ").join(sql.Identifier(name) for name in block.columns)
    statement = sql.SQL(
        "COPY public.{} ({}) FROM STDIN WITH (FORMAT text)"
    ).format(sql.Identifier(block.table), columns)

    dump.seek(block.data_start)
    remaining = block.data_end - block.data_start
    with connection.cursor().copy(statement) as copy:
        while remaining:
            chunk = dump.read(min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError(f"{block.table}: unexpected EOF during COPY")
            copy.write(chunk)
            remaining -= len(chunk)


def import_dump(
    dump_path: str | os.PathLike[str],
    blocks: Mapping[str, CopyBlock],
    target: DumpEmpireTarget,
    tables: Sequence[ShadowTable] = SHADOW_TABLES,
) -> dict[str, Any]:
    preflight = build_plan(blocks, target, tables)
    if not preflight["schema_compatible"]:
        raise RuntimeError("shadow dump import blocked: schema incompatibility")
    if not preflight["all_targets_empty"]:
        raise RuntimeError(
            "shadow dump import blocked: target tables are not empty; "
            "no delete or truncate authority is available"
        )

    verification: list[dict[str, Any]] = []
    with open(dump_path, "rb") as dump:
        with target.connect() as connection:
            with connection.transaction():
                for item in tables:
                    block = blocks[item.name]
                    _write_block_to_copy(dump, connection, block)
                    target_count = target.count(connection, item.name)
                    target_pk_sha256 = _digest_strings(
                        target.primary_keys(connection, item)
                    )
                    verified = (
                        target_count == block.row_count
                        and target_pk_sha256 == block.primary_key_sha256
                    )
                    result = {
                        "table": item.name,
                        "source_rows": block.row_count,
                        "target_rows": target_count,
                        "source_pk_sha256": block.primary_key_sha256,
                        "target_pk_sha256": target_pk_sha256,
                        "verified": verified,
                    }
                    verification.append(result)
                    print(json.dumps(result, sort_keys=True), flush=True)
                    if not verified:
                        raise RuntimeError(
                            f"{item.name}: shadow import verification failed"
                        )

    return {
        "schema_version": "empire.shadow-dump-import.v1",
        "canonical_backend_unchanged": True,
        "source_delete_authority": False,
        "target_delete_authority": False,
        "production_cutover_authority": False,
        "verified": all(row["verified"] for row in verification),
        "tables": verification,
    }


def _target_from_env() -> DumpEmpireTarget:
    dsn = os.getenv("EMPIREDB_MIGRATOR_DSN", "").strip()
    if not dsn:
        raise RuntimeError("EMPIREDB_MIGRATOR_DSN is required")
    return DumpEmpireTarget(dsn)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transactional EmpireDB shadow import from pg_dump COPY data"
    )
    parser.add_argument("--dump-path", required=True)
    parser.add_argument("--mode", choices=("plan", "copy"), default="plan")
    parser.add_argument(
        "--report-path",
        default="runtime/data_cloud/shadow_dump_latest.json",
    )
    args = parser.parse_args(argv)

    path = Path(args.dump_path)
    if not path.is_file():
        raise RuntimeError(f"source dump not found: {path}")

    blocks = scan_dump(path)
    target = _target_from_env()
    if args.mode == "plan":
        report = build_plan(blocks, target)
    else:
        report = import_dump(path, blocks, target)

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
