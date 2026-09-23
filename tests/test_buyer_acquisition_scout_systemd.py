from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buyer_scout_service_is_bounded_observe_only():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "run_buyer_acquisition_scout.py" in text
    assert "--max-queries 20" in text
    assert "--max-probes 20" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text


def test_buyer_scout_timer_is_not_high_frequency():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.timer"
    ).read_text()

    assert "OnUnitInactiveSec=30min" in text
    assert "Persistent=true" in text


def test_buyer_scout_service_persists_only_to_holding_area():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "reconcile_buyer_acquisition_scout.py" in text
    assert "persist_buyer_scout_candidates.py" in text
    assert "outbound_governor" not in text


def test_buyer_scout_service_materializes_review_readiness():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "materialize_buyer_scout_review_readiness.py" in text
    assert "persist_buyer_scout_candidates.py" in text


def test_buyer_scout_service_builds_non_mutating_promotion_plan():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "build_buyer_scout_promotion_plan.py" in text


def test_buyer_scout_service_labels_pipeline_stages():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    for stage in (
        "DISCOVER + PROBE",
        "RECONCILE",
        "PERSIST HOLDING AREA",
        "REVIEW READINESS",
        "PROMOTION PLAN",
    ):
        assert stage in text
