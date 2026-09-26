from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buyer_scout_service_is_bounded_internal_research():
    text = (
        ROOT / "deploy/systemd/empire-buyer-scout.service"
    ).read_text()

    assert "run_buyer_scout.py" in text
    assert "--max-queries 12" in text
    assert "--results-per-query 5" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "outbound_governor" not in text
    assert "voice_outbound" not in text


def test_buyer_scout_timer_is_persistent_and_slower_than_planning_loop():
    text = (
        ROOT / "deploy/systemd/empire-buyer-scout.timer"
    ).read_text()

    assert "OnUnitInactiveSec=30min" in text
    assert "Persistent=true" in text
