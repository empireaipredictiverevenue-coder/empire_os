from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buyer_scout_service_is_bounded_observe_only():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "run_buyer_acquisition_scout.py" in text
    assert "--max-queries 20" in text
    assert "--max-probes 20" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text


def test_buyer_scout_timer_is_not_high_frequency():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.timer"
    ).read_text()

    assert "OnUnitInactiveSec=30min" in text
    assert "Persistent=true" in text
