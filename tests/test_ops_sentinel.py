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


def test_legacy_end_to_end_flag_alone_does_not_trigger_repair():
    units = healthy_units()
    findings = analyze(
        unit_states=units,
        runtime={"source_health": {"end_to_end_healthy": False}},
    )
    assert findings == []
    assert build_repair_plan(findings) == []


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


def test_source_write_evidence_gap_is_visible_but_not_unhealthy():
    units = healthy_units()
    findings = analyze(
        unit_states=units,
        runtime={
            "source_health": {
                "endpoint_healthy": True,
                "canonical_ingest_scheduled": True,
                "canonical_ingest_authorized": False,
                "end_to_end_healthy": False,
                "blockers": ["canonical_ingest_not_authorized"],
            }
        },
    )
    row = next(
        item for item in findings
        if item.code == "source_ingest_evidence_unverified"
    )
    assert row.severity == "info"
    assert row.repairable is False
    assert build_repair_plan(findings) == []


def test_source_endpoint_failure_stays_warning_and_repairable():
    units = healthy_units()
    findings = analyze(
        unit_states=units,
        runtime={
            "source_health": {
                "endpoint_healthy": False,
                "canonical_ingest_scheduled": True,
                "canonical_ingest_authorized": True,
                "errors": ["TimeoutError"],
                "blockers": ["source_probe_error"],
            }
        },
    )
    row = next(
        item for item in findings
        if item.code == "source_pipeline_degraded"
    )
    assert row.severity == "warning"
    assert row.repairable is True
    plan = build_repair_plan(findings)
    assert any(
        item["target"] == "source_health_refresh"
        for item in plan
    )


def test_coder_cooldown_failover_is_informational():
    units = healthy_units()
    findings = analyze(
        unit_states=units,
        runtime={
            "coder_model_health": {
                "routes": {
                    "ollama:small": {
                        "status": "cooldown",
                        "cooldown_until": (
                            datetime.now(timezone.utc)
                            + timedelta(minutes=5)
                        ).isoformat(),
                    }
                }
            }
        },
    )
    row = next(
        item for item in findings
        if item.code == "coder_model_route_degraded"
    )
    assert row.severity == "info"


def test_agentic_revenue_owner_replaces_legacy_critical_timers():
    assert "empire-autonomous-revenue-os.service" in CRITICAL_SERVICES
    assert "empire-acquisition.timer" not in CRITICAL_TIMERS
    assert "empire-qualification.timer" not in CRITICAL_TIMERS


def test_down_autonomous_revenue_owner_gets_safe_restart_plan():
    units = healthy_units()
    units["empire-autonomous-revenue-os.service"] = "failed"
    findings = analyze(unit_states=units, runtime={})
    plan = build_repair_plan(findings)
    assert any(
        row["action"] == "restart_unit"
        and row["target"] == "empire-autonomous-revenue-os.service"
        for row in plan
    )


def recent_fallback_runtime():
    current = datetime.now(timezone.utc).isoformat()
    return {
        "source_health": {
            "source": "overpass",
            "endpoint_healthy": False,
            "blockers": ["source_probe_error"],
            "errors": ["private upstream failure details"],
        },
        "acquisition": {
            "schema_version": "acquisition_cycle.v2",
            "observed_at": current,
            "ok": True,
            "fallback_used": True,
            "source": "permits",
            "attempted_sources": ["courtlistener", "permits"],
            "canonical_acquisition_observed": True,
            "real_data_only": True,
            "prospect_canonical_write": False,
            "outreach_enabled": False,
            "payment_enabled": False,
        },
        "acquisition_last_success": {
            "schema_version": "acquisition_success.v2",
            "observed_at": current,
            "source": "permits",
            "real_data_only": True,
            "canonical_writes": False,
            "prospect_canonical_write": False,
            "signal_inbox_write": True,
            "write_store": "runtime_signal_inbox",
        },
    }


def test_live_original_acquisition_fallback_changes_overpass_warning_to_info():
    evidence = recent_fallback_runtime()
    findings = analyze(unit_states=healthy_units(), runtime=evidence)
    codes = {f.code for f in findings}
    assert "source_pipeline_degraded" not in codes
    row = next(f for f in findings
               if f.code == "source_endpoint_degraded_fallback_active")
    assert row.severity == "info"
    assert row.repairable is False
    assert row.evidence["fallback_source"] == "permits"
    assert row.evidence["canonical_ingest_authorized"] is False
    assert row.evidence["outreach_authorized"] is False
    assert "private" not in str(row.evidence)
    assert build_repair_plan(findings) == []


import pytest


@pytest.mark.parametrize("field,value", [
    ("observed_at", "2026-09-01T00:00:00+00:00"),
    ("ok", False),
    ("source", "overpass"),
    ("canonical_acquisition_observed", False),
    ("real_data_only", False),
    ("prospect_canonical_write", True),
    ("outreach_enabled", True),
    ("payment_enabled", True),
    ("fallback_used", False),
    ("attempted_sources", ["courtlistener"]),
])
def test_unverified_replay_or_authority_preserves_original_warning(field, value):
    evidence = recent_fallback_runtime()
    evidence["acquisition"][field] = value
    findings = analyze(unit_states=healthy_units(), runtime=evidence)
    assert any(f.code == "source_pipeline_degraded" and f.severity == "warning"
               for f in findings)
    assert not any(f.code == "source_endpoint_degraded_fallback_active"
                   for f in findings)


@pytest.mark.parametrize("field,value", [
    ("source", "unrelated"),
    ("observed_at", "2026-09-01T00:00:00+00:00"),
    ("real_data_only", False),
    ("signal_inbox_write", False),
    ("canonical_writes", True),
    ("prospect_canonical_write", True),
    ("write_store", "empiredb"),
])
def test_forged_last_success_keeps_source_warning(field, value):
    evidence = recent_fallback_runtime()
    evidence["acquisition_last_success"][field] = value
    findings = analyze(unit_states=healthy_units(), runtime=evidence)
    assert any(f.code == "source_pipeline_degraded" for f in findings)


def test_last_success_receipt_absent_is_not_called_healthy():
    evidence = recent_fallback_runtime()
    del evidence["acquisition_last_success"]
    findings = analyze(unit_states=healthy_units(), runtime=evidence)
    assert any(f.code == "source_pipeline_degraded" for f in findings)
