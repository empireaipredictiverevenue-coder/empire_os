from pathlib import Path


def test_backup_observer_systemd_is_direct_postgres_read_only_probe():
    root = Path(__file__).resolve().parents[1]
    text = (
        root
        / "deploy/systemd/empire-data-cloud-backup-observer.service"
    ).read_text(encoding="utf-8")

    assert "User=postgres" in text
    assert "Group=postgres" in text
    assert "Type=oneshot" in text
    assert "/usr/bin/pgbackrest" in text
    assert "--stanza=empiredb" in text
    assert "--output=json info" in text
    assert "--log-level-file=off" in text
    assert " backup " not in text
    assert " restore " not in text
    assert "/srv/empire_os/.venv/bin/python" not in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text


def test_backup_observer_writes_only_ephemeral_runtime_status():
    root = Path(__file__).resolve().parents[1]
    text = (
        root
        / "deploy/systemd/empire-data-cloud-backup-observer.service"
    ).read_text(encoding="utf-8")

    assert "RuntimeDirectory=empire-data-cloud" in text
    assert "RuntimeDirectoryPreserve=yes" in text
    assert "/run/empire-data-cloud/pgbackrest.json" in text
    assert "/var/backups/empiredb/pgbackrest" not in text


def test_founder_dashboard_api_is_canonical_system_service():
    root = Path(__file__).resolve().parents[1]
    text = (
        root / "deploy/systemd/empire-founder-dashboard-api.service"
    ).read_text(encoding="utf-8")

    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "WantedBy=multi-user.target" in text
