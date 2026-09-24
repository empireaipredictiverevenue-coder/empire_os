from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_service_uses_protected_runtime_environment():
    text = (
        ROOT / "deploy/systemd/empire-legacy-permit-recovery.service"
    ).read_text()

    assert "User=ubuntu" in text
    assert "EnvironmentFile=-/etc/empire_os.env" in text
    assert "Environment=PYTHONPATH=/srv/empire_os" in text
    assert "--batch-size 250" in text


def test_recovery_service_is_observe_only_and_runtime_write_bounded():
    text = (
        ROOT / "deploy/systemd/empire-legacy-permit-recovery.service"
    ).read_text()

    assert "legacy_permit_recovery_observer.py" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "ProtectSystem=strict" in text
    assert "outbound" not in text.casefold()


def test_recovery_timer_is_bounded_cadence():
    text = (
        ROOT / "deploy/systemd/empire-legacy-permit-recovery.timer"
    ).read_text()

    assert "OnUnitInactiveSec=30min" in text
    assert "Persistent=true" in text


def test_recovery_deployer_runs_tests_before_install():
    text = (
        ROOT / "scripts/deploy_legacy_permit_recovery.sh"
    ).read_text()

    test_pos = text.index("=== TEST ===")
    install_pos = text.index("=== INSTALL SERVICE + TIMER ===")
    first_cycle_pos = text.index("=== RUN FIRST OBSERVE CYCLE ===")

    assert test_pos < install_pos < first_cycle_pos
    assert "test_legacy_permit_recovery.py" in text
    assert "test_legacy_permit_recovery_systemd.py" in text
    assert "database_write_performed" in text
    assert "canonical_promotion_performed" in text
    assert "outbound_sent" in text
    assert "actual_revenue" in text
