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
    assert all(
        row.classification == "production_runtime"
        for row in rows
        if row.path == "empire_os/worker.py"
    )


def test_discovery_classifies_docs_tests_apps_and_scripts(tmp_path: Path):
    for directory in ("docs", "tests", "apps/web", "scripts"):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)

    (tmp_path / "docs" / "note.md").write_text("Supabase migration", encoding="utf-8")
    (tmp_path / "tests" / "test_db.py").write_text("supabase test", encoding="utf-8")
    (tmp_path / "apps" / "web" / "db.ts").write_text("SUPABASE_URL", encoding="utf-8")
    (tmp_path / "scripts" / "db.sh").write_text("supabase.co", encoding="utf-8")

    rows = discover_vendor_dependencies(tmp_path)
    by_path = {row.path: row.classification for row in rows}

    assert by_path["docs/note.md"] == "documentation"
    assert by_path["tests/test_db.py"] == "test_reference"
    assert by_path["apps/web/db.ts"] == "application_runtime"
    assert by_path["scripts/db.sh"] == "runtime_integration"


def test_marker_matching_is_case_insensitive_and_one_finding_per_line(tmp_path: Path):
    (tmp_path / "empire_os").mkdir()
    (tmp_path / "empire_os" / "worker.py").write_text(
        "client = SupabaseClient(SUPABASE_URL)\n",
        encoding="utf-8",
    )

    rows = discover_vendor_dependencies(tmp_path)

    assert len(rows) == 1
    assert rows[0].marker == "SUPABASE_URL"
