from pathlib import Path
from types import SimpleNamespace

from empire_os import data_cloud_backup_observer as observer


def test_backup_observer_is_read_only_and_sanitized(tmp_path):
    config = tmp_path / "empiredb.conf"
    config.write_text(
        "[empiredb]\n"
        "pg1-path=/var/lib/postgresql/18/main\n"
        "[global]\n"
        "repo1-type=posix\n"
        "repo1-path=/var/backups/empiredb/pgbackrest\n"
        "repo1-cipher-type=aes-256-cbc\n"
        "repo1-cipher-pass=must-never-appear\n",
        encoding="utf-8",
    )

    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '[{"status":{"code":0},"backup":'
                '[{"label":"20260927-202202F"}]}]'
            ),
            stderr="",
        )

    result = observer.observe_pgbackrest(
        runner=runner,
        config_path=config,
    )

    assert calls[0][0][0] == "pgbackrest"
    assert "info" in calls[0][0]
    assert "backup" not in calls[0][0]
    assert "restore" not in calls[0][0]
    assert result["healthy"] is True
    assert result["backup_count"] == 1
    assert result["latest_label"] == "20260927-202202F"
    assert result["encrypted"] is True
    assert result["read_only"] is True
    assert result["backup_creation"] is False
    assert result["restore_performed"] is False
    assert result["production_cutover_authority"] is False
    assert "cipher_pass" not in str(result)
    assert "must-never-appear" not in str(result)


def test_backup_observer_fails_closed():
    result = observer.observe_pgbackrest(
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="permission denied",
        )
    )

    assert result["healthy"] is False
    assert result["error_class"] == "PgBackRestPermissionDenied"
    assert result["production_cutover_authority"] is False


def test_backup_observer_systemd_runs_as_postgres():
    root = Path(__file__).resolve().parents[1]
    text = (
        root
        / "deploy/systemd/empire-data-cloud-backup-observer.service"
    ).read_text(encoding="utf-8")

    assert "User=postgres" in text
    assert "Group=postgres" in text
    assert "Type=oneshot" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "-m empire_os.data_cloud_backup_observer" in text


def test_founder_dashboard_api_is_canonical_system_service():
    root = Path(__file__).resolve().parents[1]
    text = (
        root / "deploy/systemd/empire-founder-dashboard-api.service"
    ).read_text(encoding="utf-8")

    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "WantedBy=multi-user.target" in text
