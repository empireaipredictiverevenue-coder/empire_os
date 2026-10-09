import json

from empire_os.engineering_health_publisher import publish


def test_publisher_retains_green_evidence(tmp_path):
    log = tmp_path / "pytest.log"
    log.write_text("2087 passed, 58 warnings in 139.32s (0:02:19)\n")
    target = tmp_path / "runtime" / "engineering_health" / "latest.json"
    report = publish(log, target)
    retained = json.loads(target.read_text())
    assert report["healthy"] is True
    assert retained["healthy"] is True
    assert retained["incident_report"]["incident_count"] == 0
    assert retained["execution_authority"] == "none"
    assert retained["observed_at"]


def test_publisher_retains_failure_without_healing(tmp_path):
    log = tmp_path / "pytest.log"
    log.write_text("FAILED tests/test_x.py::test_x - AssertionError\n1 failed in 1.00s\n")
    target = tmp_path / "latest.json"
    report = publish(log, target)
    retained = json.loads(target.read_text())
    assert report["healthy"] is False
    assert retained["incident_report"]["requires_escalation"] is True
    assert retained["auto_repair_permitted"] is False
    assert not list(tmp_path.glob(".engineering-health-*"))
