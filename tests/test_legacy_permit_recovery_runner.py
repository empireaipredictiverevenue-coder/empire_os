from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_permit_recovery_runner_is_observe_only():
    text = (
        ROOT / "scripts/run_legacy_permit_recovery_observer.py"
    ).read_text()

    assert "refresh_legacy_permit_recovery_observer" in text
    assert "database_write_performed" in text
    assert "canonical_promotion_performed" in text
    assert "outbound_sent" in text
    assert "actual_revenue" in text
    assert "execution_authority" in text


def test_legacy_permit_recovery_core_has_no_mutating_rest_method():
    text = (
        ROOT / "empire_os/legacy_permit_recovery.py"
    ).read_text()

    assert 'request_json("GET"' in text
    assert 'request_json("POST"' not in text
    assert 'request_json("PATCH"' not in text
    assert 'request_json("DELETE"' not in text
    assert '"NO_PROMOTION_OBSERVE_ONLY"' in text
    assert '"historical_only": True' in text
    assert '"current_truth": False' in text
