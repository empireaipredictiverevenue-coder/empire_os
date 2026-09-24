from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ops_control_cycle_owns_runtime_doctor():
    text = (ROOT / "scripts/run_ops_control_cycle.py").read_text()
    assert "run_runtime_self_heal" in text
    assert 'observe_only=mode != "GUARDED_EXECUTE"' in text
    assert '"runtime_doctor": runtime_doctor' in text


def test_ops_control_service_keeps_autonomy_observe_and_uses_helper():
    text = (
        ROOT / "deploy/systemd/empire-ops-control.service"
    ).read_text()
    assert "EMPIRE_OPS_HEAL_MODE=GUARDED_EXECUTE" in text
    assert "EMPIRE_AUTONOMOUS_MODE=OBSERVE" in text
    assert "empire-ops-privileged-helper.service" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text


def test_control_fabric_registers_runtime_self_heal():
    from empire_os.control_fabric import default_registry

    by_name = {row.name: row for row in default_registry()}
    healer = by_name["runtime_self_heal"]
    assert healer.authority == "internal_write"
    assert healer.repair_policy == "allowlisted_reversible_only"
