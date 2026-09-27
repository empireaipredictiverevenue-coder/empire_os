"""Deterministic schema compatibility checks for EmpireDB migration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    data_type: str
    nullable: bool


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]
    primary_key: tuple[str, ...] = ()
    rls_enabled: bool = False


@dataclass(frozen=True)
class SchemaManifest:
    tables: tuple[TableSpec, ...]


def _by_table(manifest: SchemaManifest) -> dict[str, TableSpec]:
    return {table.name.removeprefix("public."): table for table in manifest.tables}


def compare_schema(
    source: SchemaManifest,
    target: SchemaManifest,
) -> dict[str, object]:
    """Compare structural compatibility without mutating either database."""

    source_tables = _by_table(source)
    target_tables = _by_table(target)
    findings: list[str] = []

    for name, source_table in sorted(source_tables.items()):
        target_table = target_tables.get(name)
        if target_table is None:
            findings.append(f"missing_table:{name}")
            continue

        source_columns = {column.name: column for column in source_table.columns}
        target_columns = {column.name: column for column in target_table.columns}

        for column_name, source_column in sorted(source_columns.items()):
            target_column = target_columns.get(column_name)
            if target_column is None:
                findings.append(f"missing_column:{name}.{column_name}")
                continue
            if source_column.data_type != target_column.data_type:
                findings.append(f"type_mismatch:{name}.{column_name}")
            if source_column.nullable != target_column.nullable:
                findings.append(f"nullability_mismatch:{name}.{column_name}")

        if source_table.primary_key != target_table.primary_key:
            findings.append(f"primary_key_mismatch:{name}")

        if source_table.rls_enabled and not target_table.rls_enabled:
            findings.append(f"rls_missing:{name}")

    extra_tables = sorted(set(target_tables) - set(source_tables))

    return {
        "schema_version": "empire.data-cloud-schema-compat.v1",
        "compatible": not findings,
        "findings": findings,
        "source_table_count": len(source_tables),
        "target_table_count": len(target_tables),
        "extra_target_tables": extra_tables,
        "authority": {
            "schema_mutation": False,
            "drop_table": False,
            "production_cutover": False,
        },
    }


def manifest_from_rows(rows: Iterable[dict[str, object]]) -> SchemaManifest:
    """Build a manifest from normalized introspection rows.

    Expected keys: table_name, column_name, data_type, is_nullable,
    primary_key, rls_enabled.
    """
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        name = str(row["table_name"]).removeprefix("public.")
        grouped.setdefault(name, []).append(row)

    tables: list[TableSpec] = []
    for table_name, items in sorted(grouped.items()):
        columns = tuple(
            ColumnSpec(
                name=str(item["column_name"]),
                data_type=str(item["data_type"]),
                nullable=str(item["is_nullable"]).upper() == "YES",
            )
            for item in items
        )
        primary_key = tuple(
            str(item["column_name"])
            for item in items
            if bool(item.get("primary_key"))
        )
        rls_enabled = any(bool(item.get("rls_enabled")) for item in items)
        tables.append(
            TableSpec(
                name=table_name,
                columns=columns,
                primary_key=primary_key,
                rls_enabled=rls_enabled,
            )
        )
    return SchemaManifest(tables=tuple(tables))
