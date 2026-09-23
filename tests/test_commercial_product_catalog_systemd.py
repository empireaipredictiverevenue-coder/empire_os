from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_catalog_refresh_service_uses_restricted_materializer():
    text = (
        ROOT / "deploy/systemd/empire-commercial-product-catalog.service"
    ).read_text()

    assert "refresh_commercial_product_catalog.py" in text
    assert "intelligence_materializer.env" in text
    assert "ReadWritePaths=/srv/empire_os/runtime/commercial_catalog" in text
    assert "outbound" not in text.lower()


def test_catalog_refresh_timer_is_persistent():
    text = (
        ROOT / "deploy/systemd/empire-commercial-product-catalog.timer"
    ).read_text()

    assert "OnUnitInactiveSec=5min" in text
    assert "Persistent=true" in text
