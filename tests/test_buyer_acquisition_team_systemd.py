from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buyer_acquisition_team_service_is_observe_runtime_only():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-team.service"
    ).read_text()

    assert "refresh_buyer_acquisition_team.py" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "outbound_governor" not in text


def test_buyer_acquisition_team_timer_is_persistent():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-team.timer"
    ).read_text()

    assert "OnUnitInactiveSec=5min" in text
    assert "Persistent=true" in text
    assert "empire-buyer-acquisition-team.service" in text
