from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_predictive_intelligence_service_is_bounded_and_uses_runtime_env():
    text = (
        ROOT
        / "deploy/systemd/empire-predictive-intelligence.service"
    ).read_text()

    assert "EnvironmentFile=/etc/empire_os.env" in text
    assert "Environment=PYTHONPATH=/srv/empire_os" in text
    assert "scripts/build_predictive_intelligence.py" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text


def test_predictive_intelligence_timer_is_persistent():
    text = (
        ROOT
        / "deploy/systemd/empire-predictive-intelligence.timer"
    ).read_text()

    assert "OnUnitInactiveSec=5min" in text
    assert "Persistent=true" in text
    assert "empire-predictive-intelligence.service" in text
