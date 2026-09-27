from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_commercial_exchange_service_is_read_only_runtime_materializer():
    text = (
        ROOT / "deploy/systemd/empire-commercial-exchange.service"
    ).read_text()

    assert "EnvironmentFile=/etc/empire_os.env" in text
    assert "scripts/refresh_commercial_exchange.py" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "--limit 200" in text


def test_commercial_exchange_timer_is_persistent():
    text = (
        ROOT / "deploy/systemd/empire-commercial-exchange.timer"
    ).read_text()

    assert "OnUnitInactiveSec=5min" in text
    assert "Persistent=true" in text
    assert "empire-commercial-exchange.service" in text
