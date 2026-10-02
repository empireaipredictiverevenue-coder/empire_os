from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/install_revenue_exchange_snapshot_runtime.sh"


def test_installer_requires_explicit_reader_provision_flag():
    text = SCRIPT.read_text()
    assert '"${1:-}" == "--provision-reader"' in text
    assert "provision_revenue_exchange_reader.py\" --apply" in text
    assert "dedicated Revenue Exchange reader is not provisioned" in text
    assert "rerun with --provision-reader" in text
    assert "systemctl stop empire-revenue-exchange-snapshot.timer" in text


def test_installer_does_not_embed_db_credentials_or_broad_dsn():
    text = SCRIPT.read_text()
    assert "EMPIREDB_DSN=" not in text
    assert "EMPIREDB_MIGRATOR_DSN=" not in text
    assert "password=" not in text.lower()
