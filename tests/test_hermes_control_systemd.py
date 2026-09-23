from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "deploy/systemd/empire-hermes-control.service"
TIMER = ROOT / "deploy/systemd/empire-hermes-control.timer"


def test_hermes_service_is_unprivileged_and_observe_bounded():
    text = SERVICE.read_text()

    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "EMPIRE_AUTONOMOUS_MODE=OBSERVE" in text
    assert "EMPIRE_HERMES_BIN=/home/ubuntu/.local/bin/hermes" in text
    assert "/home/ubuntu/.local/bin" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ProtectHome=read-only" in text
    assert "RestrictSUIDSGID=true" in text
    assert "run_hermes_control_worker.py" in text
    assert "--max-jobs 1" in text

    assert "/srv/empire_os/.git" in text
    assert "/srv/empire_os/runtime/hermes_control" in text


def test_hermes_timer_is_bounded():
    text = TIMER.read_text()

    assert "OnUnitInactiveSec=2min" in text
    assert "Persistent=true" in text
    assert "Unit=empire-hermes-control.service" in text
