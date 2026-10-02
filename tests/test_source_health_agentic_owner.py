from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_source_health_observes_agentic_acquisition_owner():
    unit = (ROOT / "deploy/systemd/empire-source-health.service").read_text()
    script = (ROOT / "scripts/run_source_health_observer_cron.sh").read_text()
    assert "empire-autonomous-revenue-os.service" in unit
    assert "empire-acquisition.timer" not in unit
    assert "systemctl is-active --quiet empire-autonomous-revenue-os.service" in script
    assert "systemctl is-enabled --quiet empire-autonomous-revenue-os.service" in script
    assert "empire-acquisition.timer" not in script
