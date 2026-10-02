from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_snapshot_service_uses_only_dedicated_reader_environment():
    text = (ROOT / "deploy/systemd/empire-revenue-exchange-snapshot.service").read_text()
    assert "EnvironmentFile=/etc/empire_revenue_exchange.env" in text
    assert "EnvironmentFile=/etc/empiredb.env" not in text
    assert "EnvironmentFile=/etc/empire_os.env" not in text
    assert "User=ubuntu" in text
    assert "NoNewPrivileges=true" in text
    assert "ReadWritePaths=/srv/empire_os/runtime/revenue_exchange" in text


def test_snapshot_refresh_requires_dedicated_dsn_key():
    text = (ROOT / "scripts/refresh_revenue_exchange_snapshot.py").read_text()
    assert 'READER_DSN_KEY = "EMPIRE_REVENUE_EXCHANGE_READER_DSN"' in text
    assert 'env[READER_DSN_KEY]' in text
    assert 'env["EMPIREDB_DSN"]' not in text
