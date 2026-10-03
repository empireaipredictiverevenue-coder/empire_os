from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ringleader_observer_service_is_observe_only_and_hardened():
    text = (
        ROOT / "deploy/systemd/empire-outbound-ringleader-observer.service"
    ).read_text(encoding="utf-8")

    assert "EMPIRE_OUTBOUND_RINGLEADER_MODE=OBSERVE" in text
    assert "EMPIRE_OUTBOUND_TELEMETRY_SOURCE=resend" in text
    assert "EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE=false" in text
    assert "-m empire_os.outbound_ringleader_observer" in text
    assert "ExecStartPre=/srv/empire_os/.venv/bin/python -m empire_os.outbound_ringleader_preflight" in text
    assert "--execute" not in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ProtectHome=true" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "EnvironmentFile=-/srv/empire_os/runtime/secrets/outbound-deliverability.env" in text
    assert "RESEND_API_KEY=" not in text
    assert "EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN=" not in text


def test_ringleader_observer_timer_is_bounded_and_persistent():
    text = (
        ROOT / "deploy/systemd/empire-outbound-ringleader-observer.timer"
    ).read_text(encoding="utf-8")

    assert "OnBootSec=2min" in text
    assert "OnUnitActiveSec=5min" in text
    assert "AccuracySec=30s" in text
    assert "Persistent=true" in text
    assert "Unit=empire-outbound-ringleader-observer.service" in text


def test_ringleader_env_example_defaults_to_no_database_authority():
    text = (
        ROOT / "config/outbound_deliverability.env.example"
    ).read_text(encoding="utf-8")

    assert "EMPIRE_OUTBOUND_RINGLEADER_MODE=OBSERVE" in text
    assert "EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN=" in text
    assert "EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN=" in text

    for line in text.splitlines():
        if line.startswith("EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN="):
            assert line == "EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN="
        if line.startswith("EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN="):
            assert line == "EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN="
        if line.startswith("RESEND_API_KEY="):
            assert line == "RESEND_API_KEY="



def test_ringleader_watchdog_service_is_read_only_and_independent():
    text = (
        ROOT / "deploy/systemd/empire-outbound-ringleader-watchdog.service"
    ).read_text(encoding="utf-8")

    assert "-m empire_os.outbound_ringleader_watchdog" in text
    assert "EMPIRE_OUTBOUND_OBSERVER_MAX_AGE_MINUTES=15" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ProtectHome=true" in text
    assert "ReadOnlyPaths=/etc /srv/empire_os/runtime" in text
    assert "ReadWritePaths=" not in text


def test_ringleader_watchdog_timer_checks_after_observer_has_had_time_to_run():
    text = (
        ROOT / "deploy/systemd/empire-outbound-ringleader-watchdog.timer"
    ).read_text(encoding="utf-8")

    assert "OnBootSec=7min" in text
    assert "OnUnitActiveSec=5min" in text
    assert "AccuracySec=30s" in text
    assert "Persistent=true" in text
    assert "Unit=empire-outbound-ringleader-watchdog.service" in text


def test_observer_service_has_runtime_write_access_for_heartbeat_only_surface():
    text = (
        ROOT / "deploy/systemd/empire-outbound-ringleader-observer.service"
    ).read_text(encoding="utf-8")
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
