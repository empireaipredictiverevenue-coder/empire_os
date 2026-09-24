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


def test_catalog_refresh_runs_pricing_drift_verifier():
    text = (
        ROOT / "deploy/systemd/empire-commercial-product-catalog.service"
    ).read_text()

    assert "verify_commercial_pricing_snapshot.py" in text


def test_catalog_cycle_owns_country_native_pricing_sync():
    text = (
        ROOT / "deploy/systemd/empire-commercial-product-catalog.service"
    ).read_text()

    assert "sync_market_pricing.py" in text
    assert "apply_solar_economics_policy.py" in text
    assert "refresh_solar_economics.py" in text
    assert "EnvironmentFile=/etc/empire_os.env" in text


def test_catalog_service_can_write_solar_economics_runtime():
    text = (
        ROOT / "deploy/systemd/empire-commercial-product-catalog.service"
    ).read_text()

    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime/solar_opportunity_maps" in text



def test_catalog_cycle_syncs_founder_approved_commercial_pricing():
    text = (
        ROOT / "deploy/systemd/empire-commercial-product-catalog.service"
    ).read_text()

    assert "sync_founder_approved_commercial_pricing.py" in text
