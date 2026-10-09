import importlib.util
from pathlib import Path

from empire_os.engineering_health_bridge import build_engineering_health_report


def _runner():
    source = Path(__file__).resolve().parents[1] / "scripts" / "run_incident_manager.py"
    spec = importlib.util.spec_from_file_location("engineering_incident_runner_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_incident_runner_includes_failed_regressions(tmp_path, monkeypatch):
    runner = _runner()
    control = tmp_path / "control.json"
    control.write_text('{"sentinel":{"findings":[]}}')
    log = tmp_path / "pytest.log"
    log.write_text("FAILED tests/test_x.py::test_x - AssertionError\n1 failed in 0.1s\n")
    output = tmp_path / "incidents.json"
    monkeypatch.setattr(runner, "CONTROL", control)
    monkeypatch.setattr(runner, "ENGINEERING_LOG", log)
    monkeypatch.setattr(runner, "OUTPUT", output)
    assert runner.main() == 0
    import json
    result = json.loads(output.read_text())
    assert result["incident_count"] == 1
    assert result["requires_escalation"] is True
    assert result["controls_execution"] is False


def test_incident_runner_omits_unavailable_engineering_evidence(tmp_path, monkeypatch):
    runner = _runner()
    monkeypatch.setattr(runner, "CONTROL", tmp_path / "missing.json")
    monkeypatch.setattr(runner, "ENGINEERING_LOG", tmp_path / "missing.log")
    monkeypatch.setattr(runner, "OUTPUT", tmp_path / "incidents.json")
    assert runner.main() == 0
    import json
    result = json.loads((tmp_path / "incidents.json").read_text())
    assert "engineering_health" not in result
