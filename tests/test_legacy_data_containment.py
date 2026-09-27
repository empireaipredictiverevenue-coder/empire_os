from pathlib import Path

from empire_os.legacy_data_containment import (
    legacy_data_contained,
    legacy_operating_state_alias,
    legacy_status_aliases,
)


def test_legacy_data_containment_reads_persisted_guard_state(tmp_path: Path):
    path = tmp_path / "guard.json"
    path.write_text(
        '{"state":"contained","contained":true}',
        encoding="utf-8",
    )

    assert legacy_data_contained(path) is True


def test_missing_or_non_contained_status_is_safe_false(tmp_path: Path):
    assert legacy_data_contained(tmp_path / "missing.json") is False

    path = tmp_path / "guard.json"
    path.write_text(
        '{"state":"healthy","contained":false}',
        encoding="utf-8",
    )
    assert legacy_data_contained(path) is False


def test_compatibility_aliases_preserve_existing_consumers():
    aliases = legacy_status_aliases(
        contained=True,
        state="contained",
    )

    assert aliases == {
        "supabase_egress_contained": True,
        "supabase_guard_state": "contained",
    }
    assert (
        legacy_operating_state_alias(True)
        == "SUPABASE_CONTAINED_LOCAL_RECOVERY"
    )
