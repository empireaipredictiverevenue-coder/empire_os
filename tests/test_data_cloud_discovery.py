from pathlib import Path

from empire_os.data_cloud_discovery import discover_vendor_dependencies


def test_discovery_finds_vendor_markers_without_runtime_or_protected_paths(tmp_path: Path):
    (tmp_path / "empire_os").mkdir()
    (tmp_path / "runtime").mkdir()
    (tmp_path / "recovery").mkdir()
    (tmp_path / "empire_os" / "worker.py").write_text(
        "SUPABASE_URL = 'x'\ncanonical_supabase = True\n",
        encoding="utf-8",
    )
    (tmp_path / "runtime" / "state.json").write_text(
        '{"supabase": true}', encoding="utf-8"
    )
    (tmp_path / "recovery" / "legacy.py").write_text(
        "SUPABASE_URL = 'old'", encoding="utf-8"
    )

    rows = discover_vendor_dependencies(tmp_path)
    paths = {row.path for row in rows}

    assert "empire_os/worker.py" in paths
    assert "runtime/state.json" not in paths
    assert "recovery/legacy.py" not in paths
