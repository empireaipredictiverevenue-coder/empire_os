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


def test_approved_vendor_boundaries_are_not_business_runtime_coupling(tmp_path: Path):
    (tmp_path / "empire_os" / "data_backends").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()

    (tmp_path / "empire_os" / "canonical_data_gateway.py").write_text(
        "SUPABASE_URL",
        encoding="utf-8",
    )
    (tmp_path / "empire_os" / "data_backends" / "supabase_legacy.py").write_text(
        "supabase.co",
        encoding="utf-8",
    )
    (tmp_path / "empire_os" / "supabase_egress_guard.py").write_text(
        "Supabase",
        encoding="utf-8",
    )
    (tmp_path / "empire_os" / "legacy_data_egress.py").write_text(
        "Supabase",
        encoding="utf-8",
    )
    (tmp_path / "empire_os" / "reliability_agent.py").write_text(
        "Supabase contained",
        encoding="utf-8",
    )
    (tmp_path / "empire_os" / "astra_token_transport.py").write_text(
        "supabase.co",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "run_supabase_egress_guard.py").write_text(
        "Supabase",
        encoding="utf-8",
    )

    rows = discover_vendor_dependencies(tmp_path)
    by_path = {row.path: row.classification for row in rows}

    assert by_path["empire_os/canonical_data_gateway.py"] == "canonical_gateway"
    assert by_path["empire_os/data_backends/supabase_legacy.py"] == "legacy_adapter"
    assert by_path["empire_os/supabase_egress_guard.py"] == "migration_containment"
    assert by_path["empire_os/legacy_data_egress.py"] == "migration_containment"
    assert by_path["empire_os/reliability_agent.py"] == "migration_observer"
    assert by_path["empire_os/astra_token_transport.py"] == "legacy_observer_adapter"
    assert by_path["scripts/run_supabase_egress_guard.py"] == "migration_containment"
