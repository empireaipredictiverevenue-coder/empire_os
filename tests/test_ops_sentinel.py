from datetime import datetime, timedelta, timezone

from empire_os.ops_sentinel import (
    CRITICAL_SERVICES,
    CRITICAL_TIMERS,
    analyze,
    build_repair_plan,
)


def healthy_units():
    return {
        unit: "active"
        for unit in (*CRITICAL_SERVICES, *CRITICAL_TIMERS)
    }


def test_down_service_gets_safe_restart_plan():
    units = healthy_units()
    units["empire-public-gateway.service"] = "failed"
    findings = analyze(unit_states=units, runtime={})
    plan = build_repair_plan(findings)
    assert any(
        row["action"] == "restart_unit"
        and row["target"] == "empire-public-gateway.service"
        for row in plan
    )


def test_business_blocker_is_not_auto_repaired():
    units = healthy_units()
    findings = analyze(
        unit_states=units,
        runtime={"commercial_loop": {"loop_complete": False, "highest_blocker": "buyer_conversation"}},
    )
    assert any(f.code == "commercial_loop_blocked" for f in findings)
    assert build_repair_plan(findings) == []


def test_degraded_source_requests_safe_refresh():
    units = healthy_units()
    findings = analyze(unit_states=units, runtime={"source_health": {"end_to_end_healthy": False}})
    plan = build_repair_plan(findings)
    assert any(row["target"] == "source_health_refresh" for row in plan)


def test_coder_model_cooldown_is_visible_but_not_repaired():
    units = healthy_units()
    findings = analyze(
        unit_states=units,
        runtime={
            "coder_model_health": {
                "routes": {
                    "ollama:small": {
                        "status": "cooldown",
                        "cooldown_until": (
                            datetime.now(timezone.utc) + timedelta(minutes=5)
                        ).isoformat(),
                    }
                }
            }
        },
    )
    assert any(f.code == "coder_model_route_degraded" for f in findings)
    assert build_repair_plan(findings) == []


def test_expired_coder_cooldown_is_not_reported():
    units = healthy_units()
    findings = analyze(
        unit_states=units,
        runtime={
            "coder_model_health": {
                "routes": {
                    "ollama:old": {
                        "status": "cooldown",
                        "cooldown_until": (
                            datetime.now(timezone.utc) - timedelta(minutes=5)
                        ).isoformat(),
                    }
                }
            }
        },
    )
    assert not any(f.code == "coder_model_route_degraded" for f in findings)
