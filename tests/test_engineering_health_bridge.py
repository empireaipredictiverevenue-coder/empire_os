from empire_os.engineering_health_bridge import build_engineering_health_report


def test_failed_test_reaches_incident_manager(tmp_path):
    log = tmp_path / "test.log"
    log.write_text("FAILED tests/test_x.py::test_x - AssertionError\n1 failed, 4 passed in 2.00s\n")
    report = build_engineering_health_report(log)
    assert report["healthy"] is False
    assert report["incident_report"]["incident_count"] == 1
    diagnosis = report["incident_report"]["diagnoses"][0]
    assert diagnosis["playbook"] == "escalate"
    assert diagnosis["escalation_required"] is True
    assert diagnosis["execution_authority"] == "none"
    assert report["auto_repair_permitted"] is False


def test_green_suite_closes_incident(tmp_path):
    log = tmp_path / "test.log"
    log.write_text("2087 passed, 58 warnings in 139.32s (0:02:19)\n")
    report = build_engineering_health_report(log)
    assert report["healthy"] is True
    assert report["incident_report"]["incident_count"] == 0


def test_partial_suite_never_passes(tmp_path):
    log = tmp_path / "test.log"
    log.write_text(".......................... [ 89%]\n")
    report = build_engineering_health_report(log)
    assert report["healthy"] is False
    assert report["incident_report"]["requires_escalation"] is True
