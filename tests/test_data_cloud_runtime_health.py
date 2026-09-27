from pathlib import Path
from types import SimpleNamespace

import empire_os.data_cloud_runtime_health as health


def _runner(argv, **_kwargs):
    if argv[:2] == ["systemctl", "is-active"]:
        return SimpleNamespace(returncode=0, stdout="active\n", stderr="")
    if argv and argv[0] == "pgbackrest":
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '[{"status":{"code":0},"backup":'
                '[{"label":"20260927-202202F"}]}]'
            ),
            stderr="",
        )
    raise AssertionError(argv)


def test_collect_health_is_read_only_and_keeps_supabase_canonical(
    monkeypatch,
    tmp_path,
):
    db_env = tmp_path / "empiredb.env"
    db_env.write_text(
        "EMPIREDB_DSN=postgresql://app:secret@127.0.0.1:5432/empiredb\n",
        encoding="utf-8",
    )
    os_env = tmp_path / "empire_os.env"
    os_env.write_text("OTHER=value\n", encoding="utf-8")

    monkeypatch.setattr(
        health,
        "_postgres_probe",
        lambda dsn, *, application_name: {
            "healthy": True,
            "database": "empiredb",
            "in_recovery": False,
            "archive_mode": "off",
            "prospects_visible": 32899,
        },
    )
    monkeypatch.setattr(
        health,
        "_pgbackrest_probe",
        lambda **_kwargs: {
            "healthy": True,
            "backup_count": 1,
            "latest_label": "20260927-202202F",
            "repo_type": "posix",
            "repo_path": "/var/backups/empiredb/pgbackrest",
            "cipher_type": "aes-256-cbc",
            "encrypted": True,
            "off_node_repository_verified": False,
        },
    )

    result = health.collect_data_cloud_health(
        runner=_runner,
        empiredb_env=db_env,
        empire_os_env=os_env,
    )

    assert result["read_only"] is True
    assert result["production_cutover_authority"] is False
    assert result["canonical_backend"] == "supabase_legacy"
    assert result["canonical_backend_source"] == "default_supabase_legacy"
    assert result["candidate_runtime_healthy"] is True
    assert result["operational_cutover_ready"] is False
    assert result["archive_mode_on"] is False
    assert result["pitr_verified"] is False
    assert "off_node_backup" in result["open_gates"]
    assert "wal_pitr" in result["open_gates"]


def test_pgbackrest_probe_uses_postgres_owned_observer(
    monkeypatch,
    tmp_path,
):
    snapshot = tmp_path / "pgbackrest.json"
    snapshot.write_text(
        '[{"status":{"code":0},"backup":'
        '[{"label":"20260927-202202F"}]}]',
        encoding="utf-8",
    )
    config = tmp_path / "empiredb.conf"
    config.write_text(
        "[empiredb]\n"
        "pg1-path=/var/lib/postgresql/18/main\n"
        "[global]\n"
        "repo1-type=posix\n"
        "repo1-path=/var/backups/empiredb/pgbackrest\n"
        "repo1-cipher-type=aes-256-cbc\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        health,
        "PGBACKREST_OBSERVER_SNAPSHOT",
        snapshot,
    )
    monkeypatch.setattr(health, "PGBACKREST_CONFIG", config)

    calls = []

    def runner(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        )

    result = health._pgbackrest_probe(runner=runner)

    assert calls == [[
        "systemctl",
        "start",
        "empire-data-cloud-backup-observer.service",
    ]]
    assert result["healthy"] is True
    assert result["backup_count"] == 1
    assert result["latest_label"] == "20260927-202202F"
    assert result["encrypted"] is True
    assert result["off_node_repository_verified"] is False


def test_pgbackrest_probe_fails_closed_if_observer_service_fails():
    result = health._pgbackrest_probe(
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="failed",
        )
    )

    assert result["healthy"] is False
    assert result["error_class"] == "PgBackRestObserverServiceFailed"
