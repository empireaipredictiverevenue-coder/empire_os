from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deferred_enrichment_service_uses_bounded_batch():
    unit = (
        ROOT / "deploy/systemd/empire-buyer-deferred-enrichment.service"
    ).read_text()
    assert (
        "run_buyer_deferred_enrichment.py --limit 48 --workers 8"
        in unit
    )
    assert "TimeoutStartSec=300" in unit


def test_existing_schedule_connects_recovered_reviews_to_gtm():
    # Reuse systemd handoff instead of creating a new timer or agent.
    unit = (ROOT / "deploy/systemd/empire-buyer-deferred-enrichment.service").read_text()
    timer = (ROOT / "deploy/systemd/empire-buyer-deferred-enrichment.timer").read_text()
    source = (ROOT / "scripts/run_buyer_deferred_enrichment.py").read_text()
    assert "OnSuccess=empire-gtm-pipeline.service" in unit
    assert "OnSuccess=empire-company-routed-buyer-review.service" in unit
    assert "OnUnitInactiveSec=2min" in timer
    assert '"buyer_review_proposed"' in source
    assert "queue.resolve(" in source
    assert '"buyer_reviews_proposed": proposed' in source
    assert '"execution_allowed": False' in source


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


def test_parallel_enrichment_is_bounded_to_eight_lanes():
    script = (
        ROOT / "scripts/run_buyer_deferred_enrichment.py"
    ).read_text()
    assert "ThreadPoolExecutor" in script
    assert "MAX_CYCLE_WORKERS = 8" in script
    assert "MAX_CYCLE_LIMIT = 48" in script
    assert "worker_ceiling = min(MAX_CYCLE_WORKERS, cpu_count)" in script
    assert "lease_seconds=420" in script
    assert "live_calls_placed" in script
    assert '"execution_allowed": False' in script
