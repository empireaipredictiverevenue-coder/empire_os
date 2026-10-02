from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deferred_enrichment_service_uses_bounded_batch():
    unit = (
        ROOT / "deploy/systemd/empire-buyer-deferred-enrichment.service"
    ).read_text()
    assert "run_buyer_deferred_enrichment.py --limit 4" in unit
    assert "TimeoutStartSec=300" in unit


def test_deferred_enrichment_network_timeouts_fit_bounded_cycle():
    script = (
        ROOT / "scripts/run_buyer_deferred_enrichment.py"
    ).read_text()
    assert "BUYER_PROBE_TIMEOUT_SECONDS = 18.0" in script
    assert "IDENTITY_RECOVERY_TIMEOUT_SECONDS = 20.0" in script
    assert "TARGETED_PROBE_TIME_BUDGET_SECONDS = 10.0" in script
    assert "hard_timeout_seconds=BUYER_PROBE_TIMEOUT_SECONDS" in script
    assert "hard_timeout_seconds=IDENTITY_RECOVERY_TIMEOUT_SECONDS" in script
    assert "hard_timeout_seconds=45.0" not in script
    assert "hard_timeout_seconds=28.0" not in script
