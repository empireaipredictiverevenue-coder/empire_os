from empire_os.engineering_incident_adapter import inspect_pytest_log


def test_failed_regression_is_reported_not_auto_repaired(tmp_path):
    path = tmp_path / "pytest.log"
    path.write_text("FAILED tests/test_example.py::test_x - AssertionError\n1 failed, 382 passed in 124.00s\n")
    result = inspect_pytest_log(path)
    assert result["status"] == "FAILED"
    assert result["failed_cases"] == ["tests/test_example.py::test_x"]
    assert result["incidents"][0]["execution_authority"] == "none"
    assert result["incidents"][0]["repairable"] is False


def test_incomplete_log_fails_closed(tmp_path):
    path = tmp_path / "pytest.log"
    path.write_text("................................ [ 17%]\n")
    assert inspect_pytest_log(path)["status"] == "INCOMPLETE"


def test_completed_pass_is_healthy(tmp_path):
    path = tmp_path / "pytest.log"
    path.write_text("113 passed in 1.82s\n")
    assert inspect_pytest_log(path) == {"status": "PASSED", "incidents": []}


def test_missing_log_is_reported(tmp_path):
    assert inspect_pytest_log(tmp_path / "missing.log")["status"] == "MISSING"
