from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ops_control_cycle_owns_runtime_doctor():
    text = (ROOT / "scripts/run_ops_control_cycle.py").read_text()
    assert "run_runtime_self_heal" in text
    assert "supabase_egress_contained()" in text
    assert 'mode != "GUARDED_EXECUTE" or egress_contained' in text
    assert 'if mode == "GUARDED_EXECUTE" and not egress_contained' in text
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


def test_ops_control_defers_intentionally_contained_repairs():
    import importlib.util

    path = ROOT / "scripts/run_ops_control_cycle.py"
    spec = importlib.util.spec_from_file_location(
        "run_ops_control_cycle_test",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    sentinel = {
        "findings": [
            {
                "code": "critical_timer_down",
                "component": "empire-acquisition.timer",
                "severity": "warning",
            },
            {
                "code": "model_provider_degraded",
                "component": "model_health",
                "severity": "warning",
            },
        ],
        "repair_plan": [
            {
                "action": "restart_unit",
                "target": "empire-acquisition.timer",
            },
            {
                "action": "restart_unit",
                "target": "empire-public-gateway.service",
            },
        ],
    }

    result = module._apply_egress_containment_context(
        sentinel,
        contained=True,
    )

    assert [row["component"] for row in result["findings"]] == [
        "model_health"
    ]
    assert [row["target"] for row in result["repair_plan"]] == [
        "empire-public-gateway.service"
    ]
    containment = result["intentional_containment"]
    assert containment["active"] is True
    assert containment["reason"] == "supabase_egress"
    assert containment["deferred_finding_count"] == 1
    assert containment["deferred_repair_count"] == 1
