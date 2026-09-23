from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buyer_acquisition_verifier_requires_safe_internal_team():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    for unit in (
        "empire-qualification-booster.timer",
        "empire-buyer-review-materializer.timer",
        "empire-buyer-deferred-enrichment.timer",
        "empire-buyer-capacity-readiness.timer",
        "empire-commercial-evidence-auto-verifier.timer",
        "empire-commercial-product-catalog.timer",
        "empire-commercial-exchange.timer",
        "empire-buyer-acquisition-team.timer",
        "empire-buyer-scout.timer",
    ):
        assert unit in text

    assert '"safe_internal_automation_ready"' in text
    assert '"production_ready"' in text


def test_buyer_acquisition_verifier_treats_live_send_units_as_external_gate():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "empire-outbound-governor.timer" in text
    assert "empire-outbound-followup.timer" in text
    assert "empire-voice-outbound.timer" in text
    assert "live_external_automation_detected" in text
    assert "not live_external_automation_detected" in text


def test_buyer_acquisition_verifier_requires_catalog_and_scout_artifacts():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "runtime/commercial_catalog/latest.json" in text
    assert "runtime/commercial_exchange/latest.json" in text
    assert "runtime/buyer_acquisition/latest.json" in text
    assert "runtime/buyer_acquisition/scout_latest.json" in text


def test_buyer_acquisition_verifier_requires_scout_artifact():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "runtime/buyer_acquisition/scout_latest.json" in text
    assert "buyer_scout_safe" in text
    assert "database_write_performed" in text


def test_buyer_acquisition_verifier_requires_reconciliation_artifact():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "runtime/buyer_acquisition/reconciliation_latest.json" in text
    assert "buyer_scout_reconciliation_safe" in text
    assert "automatic_ingest_authorized" in text
