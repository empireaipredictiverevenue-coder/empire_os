from __future__ import annotations

from decimal import Decimal

import pytest

from empire_os.data_cloud_shadow_copy import (
    SHADOW_TABLES,
    ShadowTable,
    _normalize,
    canonical_row_bytes,
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


def test_shadow_manifest_contains_no_duplicate_names() -> None:
    names = [item.name for item in SHADOW_TABLES]
    assert len(names) == len(set(names))


def test_shadow_runner_contract_has_no_destructive_mode() -> None:
    import inspect
    import empire_os.data_cloud_shadow_copy as module

    source = inspect.getsource(module)
    assert "DELETE FROM" not in source.upper()
    assert "TRUNCATE " not in source.upper()
    assert "--mode" in source
    assert 'choices=("plan", "copy")' in source
    assert '"production_cutover_authority": False' in source
