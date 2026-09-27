"""Deterministic schema compatibility checks for EmpireDB migration.

This verifier is structural and read-only. It does not apply DDL.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


_WHITESPACE = re.compile(r"\s+")


def _normalize_sql(value: str | None) -> str | None:
    if value is None:
        return None
    return _WHITESPACE.sub(" ", value.strip()).replace("public.", "")


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    data_type: str
    nullable: bool
    default: str | None = None


@dataclass(frozen=True)
class CheckConstraintSpec:
    name: str
    definition: str


@dataclass(frozen=True)
class ForeignKeySpec:
    columns: tuple[str, ...]
    referenced_table: str
    referenced_columns: tuple[str, ...]
    definition: str | None = None


@dataclass(frozen=True)
class IndexSpec:
    name: str
    columns: tuple[str, ...] = ()
    unique: bool = False
    definition: str | None = None


@dataclass(frozen=True)
class PolicySpec:
    name: str
    command: str
    roles: tuple[str, ...] = ()
    using_expression: str | None = None
    check_expression: str | None = None


@dataclass(frozen=True)
class TriggerSpec:
    name: str
    definition: str


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]
    primary_key: tuple[str, ...] = ()
    unique_constraints: tuple[tuple[str, ...], ...] = ()
    check_constraints: tuple[CheckConstraintSpec, ...] = ()
    foreign_keys: tuple[ForeignKeySpec, ...] = ()
    indexes: tuple[IndexSpec, ...] = ()
    rls_enabled: bool = False
    force_rls: bool = False
    rls_policies: tuple[PolicySpec, ...] = ()
    triggers: tuple[TriggerSpec, ...] = ()


@dataclass(frozen=True)
class SchemaManifest:
    tables: tuple[TableSpec, ...]
    extensions: tuple[tuple[str, str], ...] = ()


def _by_table(manifest: SchemaManifest) -> dict[str, TableSpec]:
    return {table.name.removeprefix("public."): table for table in manifest.tables}


def _normalized_unique_constraints(
    constraints: tuple[tuple[str, ...], ...],
) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted(tuple(columns) for columns in constraints))


def _normalized_checks(
    checks: tuple[CheckConstraintSpec, ...],
) -> tuple[tuple[str, str | None], ...]:
    return tuple(sorted(
        (check.name, _normalize_sql(check.definition))
        for check in checks
    ))


def _normalized_foreign_keys(
    foreign_keys: tuple[ForeignKeySpec, ...],
) -> tuple[tuple[tuple[str, ...], str, tuple[str, ...], str | None], ...]:
    return tuple(sorted(
        (
            tuple(key.columns),
            key.referenced_table.removeprefix("public."),
            tuple(key.referenced_columns),
            _normalize_sql(key.definition),
        )
        for key in foreign_keys
    ))


def _normalized_indexes(
    indexes: tuple[IndexSpec, ...],
) -> tuple[tuple[str, tuple[str, ...], bool, str | None], ...]:
    return tuple(sorted(
        (
            index.name,
            tuple(index.columns),
            bool(index.unique),
            _normalize_sql(index.definition),
        )
        for index in indexes
    ))


def _normalized_policies(
    policies: tuple[PolicySpec, ...],
) -> tuple[tuple[str, str, tuple[str, ...], str | None, str | None], ...]:
    return tuple(sorted(
        (
            policy.name,
            policy.command.upper(),
            tuple(sorted(policy.roles)),
            _normalize_sql(policy.using_expression),
            _normalize_sql(policy.check_expression),
        )
        for policy in policies
    ))


def _normalized_triggers(
    triggers: tuple[TriggerSpec, ...],
) -> tuple[tuple[str, str | None], ...]:
    return tuple(sorted(
        (trigger.name, _normalize_sql(trigger.definition))
        for trigger in triggers
    ))


def compare_schema(
    source: SchemaManifest,
    target: SchemaManifest,
) -> dict[str, object]:
    """Compare migration-critical semantics without mutating either database."""

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
            if _normalize_sql(source_column.default) != _normalize_sql(
                target_column.default
            ):
                findings.append(f"default_mismatch:{name}.{column_name}")

        if source_table.primary_key != target_table.primary_key:
            findings.append(f"primary_key_mismatch:{name}")

        if _normalized_unique_constraints(source_table.unique_constraints) != (
            _normalized_unique_constraints(target_table.unique_constraints)
        ):
            findings.append(f"unique_constraint_mismatch:{name}")

        if _normalized_checks(source_table.check_constraints) != (
            _normalized_checks(target_table.check_constraints)
        ):
            findings.append(f"check_constraint_mismatch:{name}")

        if _normalized_foreign_keys(source_table.foreign_keys) != (
            _normalized_foreign_keys(target_table.foreign_keys)
        ):
            findings.append(f"foreign_key_mismatch:{name}")

        if _normalized_indexes(source_table.indexes) != (
            _normalized_indexes(target_table.indexes)
        ):
            findings.append(f"index_mismatch:{name}")

        if source_table.rls_enabled != target_table.rls_enabled:
            findings.append(f"rls_state_mismatch:{name}")

        if source_table.force_rls != target_table.force_rls:
            findings.append(f"force_rls_mismatch:{name}")

        if _normalized_policies(source_table.rls_policies) != (
            _normalized_policies(target_table.rls_policies)
        ):
            findings.append(f"rls_policy_mismatch:{name}")

        if _normalized_triggers(source_table.triggers) != (
            _normalized_triggers(target_table.triggers)
        ):
            findings.append(f"trigger_mismatch:{name}")

    extra_tables = sorted(set(target_tables) - set(source_tables))

    return {
        "schema_version": "empire.data-cloud-schema-compat.v3",
        "compatible": not findings,
        "findings": findings,
        "source_table_count": len(source_tables),
        "target_table_count": len(target_tables),
        "extra_target_tables": extra_tables,
        "source_extension_count": len(source.extensions),
        "target_extension_count": len(target.extensions),
        "extension_compatibility_owner": "data_cloud_extension_plan",
        "authority": {
            "schema_mutation": False,
            "drop_table": False,
            "production_cutover": False,
        },
    }


def manifest_from_rows(rows: Iterable[dict[str, object]]) -> SchemaManifest:
    """Build a column/PK/RLS manifest from normalized introspection rows.

    Rich constraints/indexes/policies/triggers/extensions are attached by the
    dedicated catalog-introspection assembler before cutover verification.
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
                default=(
                    None
                    if item.get("column_default") is None
                    else str(item["column_default"])
                ),
            )
            for item in items
        )
        primary_key = tuple(
            str(item["column_name"])
            for item in items
            if bool(item.get("primary_key"))
        )
        rls_enabled = any(bool(item.get("rls_enabled")) for item in items)
        force_rls = any(bool(item.get("force_rls")) for item in items)
        tables.append(
            TableSpec(
                name=table_name,
                columns=columns,
                primary_key=primary_key,
                rls_enabled=rls_enabled,
                force_rls=force_rls,
            )
        )
    return SchemaManifest(tables=tuple(tables))
