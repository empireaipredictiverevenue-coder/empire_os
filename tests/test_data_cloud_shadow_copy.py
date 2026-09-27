from __future__ import annotations

import ast
from decimal import Decimal

import pytest

from empire_os.data_cloud_shadow_copy import (
    SHADOW_TABLES,
    ShadowTable,
    _normalize,
    canonical_row_bytes,
    plan,
    resolve_tables,
    validate_manifest,
)


def test_shadow_manifest_is_fk_ordered() -> None:
    validate_manifest()
    positions = {item.name: index for index, item in enumerate(SHADOW_TABLES)}
    for item in SHADOW_TABLES:
        for parent in item.parents:
            assert positions[parent] < positions[item.name]


def test_resolve_tables_auto_includes_dependencies() -> None:
    selected = resolve_tables(["outbound_events"])
    names = [item.name for item in selected]
    assert "outbound_events" in names
    assert "outbound_intents" in names
    assert "prospects" in names
    assert "business_entities" in names
    assert "buyers" in names
    assert "gtm_opportunities" in names
    assert names.index("outbound_intents") < names.index("outbound_events")


def test_unknown_shadow_table_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown shadow-copy tables"):
        resolve_tables(["definitely_not_a_table"])


def test_manifest_rejects_child_before_parent() -> None:
    with pytest.raises(ValueError, match="appear after child"):
        validate_manifest(
            (
                ShadowTable("child", parents=("parent",)),
                ShadowTable("parent"),
            )
        )


def test_canonical_normalization_ignores_numeric_scale() -> None:
    left = canonical_row_bytes({"value": 1.0, "other": Decimal("5.0000")})
    right = canonical_row_bytes({"value": Decimal("1.000"), "other": 5})
    assert left == right


def test_canonical_normalization_aligns_utc_z_timestamp() -> None:
    assert _normalize("2026-09-27T18:30:00Z") == "2026-09-27T18:30:00+00:00"
    assert _normalize("2026-09-27T18:30:00.000000+00:00") == (
        "2026-09-27T18:30:00+00:00"
    )


def test_shadow_manifest_contains_no_duplicate_names() -> None:
    names = [item.name for item in SHADOW_TABLES]
    assert len(names) == len(set(names))


def test_shadow_runner_contract_has_no_destructive_mode() -> None:
    import inspect
    import empire_os.data_cloud_shadow_copy as module

    source = inspect.getsource(module)
    tree = ast.parse(source)

    executed_sql_literals: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in {"execute", "executemany"}:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            executed_sql_literals.append(first.value.upper())

    assert all("DELETE FROM" not in sql_text for sql_text in executed_sql_literals)
    assert all("TRUNCATE" not in sql_text for sql_text in executed_sql_literals)
    assert "SUPABASE_" not in source
    assert "--mode" in source
    assert 'choices=("plan", "copy")' in source
    assert '"production_cutover_authority": False' in source


class _PlanSource:
    def exact_count(self, table: str, primary_key: str) -> int:
        return 1

    def page(
        self,
        table: str,
        primary_key: str,
        *,
        after: object | None,
        limit: int,
        columns=None,
    ):
        return [{"id": "00000000-0000-0000-0000-000000000001", "live_only": "x"}]


class _PlanTarget:
    def columns(self, table: str):
        return [("id", "uuid")]

    def exact_count(self, table: str) -> int:
        return 0


def test_plan_flags_missing_target_columns() -> None:
    report = plan(
        _PlanSource(),
        _PlanTarget(),
        (ShadowTable("example"),),
    )
    assert report["schema_compatible"] is False
    assert report["tables"][0]["missing_target_columns"] == ["live_only"]
