from pathlib import Path

from empire_os.data_cloud_infrastructure import GIB, HostObservation
from empire_os.data_cloud_readiness import build_readiness_snapshot


def test_readiness_snapshot_combines_host_and_dependency_inventory(tmp_path: Path):
    (tmp_path / "empire_os").mkdir()
    (tmp_path / "empire_os" / "worker.py").write_text(
        "SUPABASE_URL = 'example'\ncanonical_supabase = True\n",
        encoding="utf-8",
    )
    host = HostObservation(
        cpu_count=8,
        memory_bytes=16 * GIB,
        disk_total_bytes=500 * GIB,
        disk_free_bytes=250 * GIB,
        postgres_available=False,
        pgbouncer_available=False,
        patroni_available=False,
        pgbackrest_available=False,
    )

    result = build_readiness_snapshot(tmp_path, host_observation=host)

    assert result["host"]["capacity_ready"] is True
    assert result["dependency_inventory"]["finding_count"] == 2
    assert result["dependency_inventory"]["file_count"] == 1
    assert result["dependency_inventory"]["runtime_finding_count"] == 2
    assert result["dependency_inventory"]["runtime_file_count"] == 1
    assert result["dependency_inventory"]["runtime_scan_clear"] is False
    assert result["gates"]["foundation_contract_present"] is False
    assert result["gates"]["foundation_contract_verified"] is False
    assert result["gates"]["postgres_runtime_verified"] is False
    assert result["authority"]["database_mutation"] is False


def test_readiness_snapshot_never_emits_matching_line_content(tmp_path: Path):
    (tmp_path / "empire_os").mkdir()
    (tmp_path / "empire_os" / "secretish.py").write_text(
        "SUPABASE_SERVICE_KEY = 'do-not-leak-this-value'\n",
        encoding="utf-8",
    )
    host = HostObservation(
        cpu_count=8,
        memory_bytes=16 * GIB,
        disk_total_bytes=500 * GIB,
        disk_free_bytes=250 * GIB,
        postgres_available=True,
        pgbouncer_available=True,
        patroni_available=True,
        pgbackrest_available=True,
    )

    result = build_readiness_snapshot(tmp_path, host_observation=host)

    rendered = str(result)
    assert "do-not-leak-this-value" not in rendered
    assert result["dependency_inventory"]["finding_count"] == 1
    assert result["authority"]["production_cutover"] is False


def test_architecture_presence_does_not_imply_verification(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "EMPIRE_DATA_CLOUD_ARCHITECTURE.md").write_text(
        "# architecture",
        encoding="utf-8",
    )
    host = HostObservation(
        cpu_count=8,
        memory_bytes=16 * GIB,
        disk_total_bytes=500 * GIB,
        disk_free_bytes=250 * GIB,
        postgres_available=True,
        pgbouncer_available=True,
        patroni_available=True,
        pgbackrest_available=True,
    )

    result = build_readiness_snapshot(tmp_path, host_observation=host)

    assert result["gates"]["foundation_contract_present"] is True
    assert result["gates"]["foundation_contract_verified"] is False


def test_docs_and_tests_do_not_count_as_runtime_coupling(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs" / "migration.md").write_text(
        "Supabase migration note",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_legacy.py").write_text(
        "SUPABASE_URL = 'test'",
        encoding="utf-8",
    )
    host = HostObservation(
        cpu_count=8,
        memory_bytes=16 * GIB,
        disk_total_bytes=500 * GIB,
        disk_free_bytes=250 * GIB,
        postgres_available=True,
        pgbouncer_available=True,
        patroni_available=True,
        pgbackrest_available=True,
    )

    result = build_readiness_snapshot(tmp_path, host_observation=host)

    inventory = result["dependency_inventory"]
    assert inventory["finding_count"] == 2
    assert inventory["runtime_finding_count"] == 0
    assert inventory["runtime_scan_clear"] is True
