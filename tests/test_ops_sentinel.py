from datetime import datetime, timedelta, timezone

from empire_os.ops_sentinel import analyze, build_repair_plan


def test_down_service_gets_safe_restart_plan():
    units = {
        "empire-autonomous-execution.service": "failed",
        "empire-public-gateway.service": "active",
        "empire-ops-mcp.service": "active",
        "empire-cloudflared.service": "active",
        "empire-acquisition.timer": "active",
        "empire-qualification.timer": "active",
    }
    findings = analyze(unit_states=units, runtime={})
    plan = build_repair_plan(findings)
    assert any(
        row["action"] == "restart_unit"
        and row["target"] == "empire-autonomous-execution.service"
        for row in plan
    )


def test_business_blocker_is_not_auto_repaired():
    units = {
        "empire-autonomous-execution.service": "active",
        "empire-public-gateway.service": "active",
        "empire-ops-mcp.service": "active",
        "empire-cloudflared.service": "active",
        "empire-acquisition.timer": "active",
        "empire-qualification.timer": "active",
    }
    findings = analyze(
        unit_states=units,
        runtime={"commercial_loop": {"loop_complete": False, "highest_blocker": "buyer_conversation"}},
    )
    assert any(f.code == "commercial_loop_blocked" for f in findings)
    assert build_repair_plan(findings) == []


def test_degraded_source_requests_safe_refresh():
    units = {
        "empire-autonomous-execution.service": "active",
        "empire-public-gateway.service": "active",
        "empire-ops-mcp.service": "active",
        "empire-cloudflared.service": "active",
        "empire-acquisition.timer": "active",
        "empire-qualification.timer": "active",
    }
    findings = analyze(unit_states=units, runtime={"source_health": {"end_to_end_healthy": False}})
    plan = build_repair_plan(findings)
    assert any(row["target"] == "source_health_refresh" for row in plan)


def test_coder_model_cooldown_is_visible_but_not_repaired():
    units = {
        "empire-autonomous-execution.service": "active",
        "empire-public-gateway.service": "active",
        "empire-ops-mcp.service": "active",
        "empire-cloudflared.service": "active",
        "empire-acquisition.timer": "active",
        "empire-qualification.timer": "active",
    }
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
    units = {
        "empire-autonomous-execution.service": "active",
        "empire-public-gateway.service": "active",
        "empire-ops-mcp.service": "active",
        "empire-cloudflared.service": "active",
        "empire-acquisition.timer": "active",
        "empire-qualification.timer": "active",
    }
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
