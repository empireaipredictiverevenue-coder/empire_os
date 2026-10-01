from pathlib import Path


def test_department_business_failure_does_not_poison_service_health():
    source = Path(
        "scripts/run_department_cycle.py"
    ).read_text()

    assert 'payload["service_health"] = "completed"' in source
    assert 'payload["work_ok"] = worker_ok is not False' in source
    assert "return 0 if worker_ok is not False else 1" not in source


def test_qualification_business_state_does_not_poison_service_health():
    source = Path(
        "scripts/run_qualification_cycle.py"
    ).read_text()

    assert 'result["business_ok"] = bool(result["ok"])' in source
    assert 'result["service_health"] = "completed"' in source
    assert 'return 0 if result["ok"] else 1' not in source


def test_real_exceptions_are_not_swallowed():
    department = Path(
        "scripts/run_department_cycle.py"
    ).read_text()

    qualification = Path(
        "scripts/run_qualification_cycle.py"
    ).read_text()

    assert "except Exception" not in department
    assert "except Exception" not in qualification
