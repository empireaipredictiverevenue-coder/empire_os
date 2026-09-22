from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_3f_production_verifier_checks_required_automation():
    text = (
        ROOT / "scripts/verify_phase_3f_production.py"
    ).read_text()

    for unit in (
        "empire-department-cycle.timer",
        "empire-astra-dispatcher.timer",
        "empire-predictive-intelligence.timer",
        "empire-opportunity-loop.timer",
        "empire-predictive-cloud-status.timer",
        "empire-founder-dashboard-api.service",
    ):
        assert unit in text

    assert "loginctl" in text
    assert "Linger" in text
    assert "runtime/phase_closeout/phase_3f_latest.json" in text
    assert '"production_ready": production_ready' in text
    assert '"execution_authority": "none"' in text
    assert '"database_migration_applied_by_verifier": False' in text
