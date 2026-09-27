from pathlib import Path

from empire_os.data_cloud_rollback_readiness import (
    build_rollback_readiness,
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_rollback_ready_when_legacy_config_retained(tmp_path):
    env = _write(
        tmp_path / "empire_os.env",
        "SUPABASE_URL=https://example.invalid\n"
        "SUPABASE_SERVICE_KEY=secret-placeholder\n",
    )

    report = build_rollback_readiness(empire_os_env=env)

    assert report["read_only"] is True
    assert report["current_backend"] == "supabase_legacy"
    assert report["legacy_config_retained"] is True
    assert report["supabase_not_retired"] is True
    assert report["reversible_backend_selection"] is True
    assert report["destructive_database_work_required"] is False
    assert report["rollback_ready"] is True
    assert report["production_cutover_authority"] is False


def test_rollback_proof_remains_ready_during_candidate_empiredb_selection(
    tmp_path,
):
    env = _write(
        tmp_path / "empire_os.env",
        "EMPIRE_DATA_BACKEND=empiredb\n"
        "SUPABASE_URL=https://example.invalid\n"
        "SUPABASE_SERVICE_KEY=secret-placeholder\n",
    )

    report = build_rollback_readiness(empire_os_env=env)

    assert report["current_backend"] == "empiredb"
    assert report["legacy_config_retained"] is True
    assert report["reversible_backend_selection"] is True
    assert report["rollback_ready"] is True


def test_rollback_fails_closed_if_supabase_config_missing(tmp_path):
    env = _write(
        tmp_path / "empire_os.env",
        "SUPABASE_URL=https://example.invalid\n",
    )

    report = build_rollback_readiness(empire_os_env=env)

    assert report["legacy_config_retained"] is False
    assert report["supabase_not_retired"] is False
    assert report["rollback_ready"] is False


def test_rollback_report_never_exposes_secret_values(tmp_path):
    env = _write(
        tmp_path / "empire_os.env",
        "SUPABASE_URL=https://example.invalid\n"
        "SUPABASE_SERVICE_KEY=do-not-leak-me\n",
    )

    report = build_rollback_readiness(empire_os_env=env)

    assert "do-not-leak-me" not in str(report)
    assert report["legacy_config"]["SUPABASE_SERVICE_KEY"] is True
