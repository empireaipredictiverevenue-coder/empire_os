#!/usr/bin/env python3
"""One bounded EmpireOS reliability control cycle."""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.control_conveyor import build_conveyor
from empire_os.commercial_loop_reader import read_commercial_loop, CommercialLoopReadError
from empire_os.incident_manager import build_incident_report
from empire_os.engineering_health_bridge import build_engineering_health_report
from empire_os.ops_healer import execute_plan
from empire_os.ops_sentinel import observe
from empire_os.runtime_self_heal import run_runtime_self_heal
from empire_os.sovereign_infrastructure_observer import collect_sovereign_infrastructure_health
from empire_os.conversation_control_operational_truth import inspect_conversation_evidence
from empire_os.supabase_egress_guard import (
    MANAGED_TIMERS,
    supabase_egress_contained,
)

OUTPUT = Path("/srv/empire_os/runtime/ops_control/latest.json")


def unit_state(unit: str) -> str:
    result = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return (result.stdout or "").strip() or "unknown"



def _apply_egress_containment_context(
    sentinel: dict,
    *,
    contained: bool,
) -> dict:
    if not contained:
        return sentinel

    result = dict(sentinel)
    findings = list(result.get("findings") or [])
    repair_plan = list(result.get("repair_plan") or [])
    managed = set(MANAGED_TIMERS)

    deferred_findings = [
        row for row in findings
        if row.get("code") == "critical_timer_down"
        and row.get("component") in managed
    ]
    deferred_repairs = [
        row for row in repair_plan
        if row.get("target") in managed
    ]
    result["findings"] = [
        row for row in findings
        if row not in deferred_findings
    ]
    result["repair_plan"] = [
        row for row in repair_plan
        if row not in deferred_repairs
    ]
    result["intentional_containment"] = {
        "active": True,
        "reason": "supabase_egress",
        "deferred_finding_count": len(deferred_findings),
        "deferred_repair_count": len(deferred_repairs),
        "deferred_findings": deferred_findings,
        "deferred_repairs": deferred_repairs,
    }
    return result


def observe_leadgen_truth(
    *,
    root: Path = Path("/srv/empire_os"),
    relay_health: Mapping[str, Any] | None = None,
    qualifier_timer_enabled: bool | None = None,
) -> dict[str, Any]:
    """Read-only revenue/evidence audit owned by the existing Ops Control cycle.

    These are commercial-readiness blockers, NOT automatic repair requests.
    Never include provider payloads, contact identities or secret values.
    """
    inconsistent: list[str] = []
    blocked: list[str] = []

    def evidence(relative: str, code: str) -> dict[str, Any]:
        try:
            value = json.loads((root / relative).read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("invalid document shape")
            return value
        except (OSError, ValueError):
            inconsistent.append("EVIDENCE_UNAVAILABLE_" + code)
            return {}

    measured = evidence(
        "runtime/campaigns_control/campaign_measured_outcome_latest.json",
        "CAMPAIGN_MEASURED",
    )
    bindings = evidence(
        "runtime/control_plane/runtime_control_bindings_latest.json",
        "CANONICAL_BINDINGS",
    )
    fabric = evidence(
        "runtime/control_plane/detection_fabric_latest.json",
        "DETECTION_FABRIC",
    )
    leadsmart = evidence(
        "runtime/revenue/lead_smart/launch_readiness/latest.json",
        "LEADSMART_READINESS",
    )
    routing = evidence(
        "runtime/revenue/lead_smart/ringba/routing_observation/latest.json",
        "LEADSMART_ROUTING",
    )
    gtm_review = evidence(
        "runtime/gtm_pipeline/founder_review_required_latest.json",
        "GTM_FOUNDER_REVIEW",
    )

    def campaign_control(document: Mapping[str, Any]) -> str | None:
        lanes = document.get("lanes")
        if not isinstance(lanes, list):
            return None
        for lane in lanes:
            if isinstance(lane, dict) and lane.get("lane") == "campaigns":
                control = (lane.get("controls") or {}).get("outcome_linkage")
                if isinstance(control, dict):
                    return str(control.get("status") or "")
        return None

    count = measured.get("exact_outcome_match_count")
    matches = measured.get("exact_outcome_matches")
    verified = measured.get("runtime_verified_controls")
    valid_count = type(count) is int and count >= 0
    if measured and (
        not valid_count
        or not isinstance(matches, list)
        or len(matches) != count
        or type(measured.get("outcome_linkage_proved")) is not bool
        or not isinstance(verified, list)
    ):
        inconsistent.append("CAMPAIGN_OUTCOME_SCHEMA_MISMATCH")

    measured_proved = (
        valid_count and count > 0
        and isinstance(matches, list) and len(matches) == count
        and measured.get("outcome_linkage_proved") is True
        and isinstance(verified, list)
        and "outcome_linkage" in verified
    )
    if measured and valid_count:
        if measured.get("outcome_linkage_proved") is not bool(count):
            inconsistent.append("CAMPAIGN_OUTCOME_FLAG_CONFLICT")
        if isinstance(verified, list) and (
            ("outcome_linkage" in verified) is not bool(count)
        ):
            inconsistent.append("CAMPAIGN_OUTCOME_VERIFICATION_CONFLICT")
    governance = measured.get("governance")
    if measured and (
        not isinstance(governance, dict)
        or any(governance.get(key) is not False for key in (
            "outbound", "db_write", "campaign_state_mutated",
            "action_authority_granted",
        ))
    ):
        inconsistent.append("CAMPAIGN_GOVERNANCE_INTEGRITY")

    canonical = campaign_control(bindings)
    materialized = campaign_control(fabric)
    for source, state in (("CANONICAL", canonical), ("FABRIC", materialized)):
        if state is None:
            inconsistent.append("CAMPAIGN_CONTROL_MISSING_" + source)
        elif (state == "VERIFIED_RUNTIME") != bool(measured_proved):
            inconsistent.append("CAMPAIGN_OUTCOME_BINDING_CONFLICT_" + source)
    if not measured_proved:
        blocked.append("CAMPAIGN_OUTCOME_NOT_PROVEN")

    if relay_health is None:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8775/health", timeout=2
            ) as response:
                relay_health = json.loads(response.read(4096))
        except (OSError, ValueError, urllib.error.URLError):
            relay_health = {}
    if not isinstance(relay_health, Mapping):
        relay_health = {}
    relay_ready = (
        relay_health.get("ok") is True
        and relay_health.get("provider") == "gmail_api"
        and relay_health.get("sender_configured") is True
        and relay_health.get("oauth_token_present") is True
    )
    if not relay_ready:
        blocked.append("OWNED_MAILBOX_NOT_READY")

    routing_verified = routing.get("routing_runtime_verified") is True
    leadsmart_ready = (
        leadsmart.get("launch_ready") is True
        and routing_verified
    )
    if leadsmart.get("launch_ready") is True and not routing_verified:
        inconsistent.append("LEADSMART_LAUNCH_ROUTING_CONFLICT")
    if not leadsmart_ready:
        blocked.append("LEADSMART_NOT_READY")

    founder_count = gtm_review.get("count")
    founder_items = gtm_review.get("items")
    founder_count_valid = type(founder_count) is int and founder_count >= 0
    if gtm_review and (
        not founder_count_valid
        or not isinstance(founder_items, list)
        or len(founder_items) != founder_count
        or gtm_review.get("outbound_authorized") is not False
        or gtm_review.get("execution_authority") != "none"
    ):
        inconsistent.append("GTM_FOUNDER_REVIEW_EVIDENCE_CONFLICT")
    if founder_count_valid and founder_count > 0:
        blocked.append("GTM_FOUNDER_REVIEWS_PENDING")

    if qualifier_timer_enabled is None:
        result = subprocess.run(
            ["systemctl", "is-enabled", "empire-qualification.timer"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        qualifier_timer_enabled = (
            result.returncode == 0 and result.stdout.strip() == "enabled"
        )
    if not qualifier_timer_enabled:
        blocked.append("QUALIFICATION_TIMER_NOT_BOOT_ENABLED")

    inconsistent = sorted(set(inconsistent))
    blocked = sorted(set(blocked))
    state = (
        "INCONSISTENT" if inconsistent
        else "BLOCKED" if blocked
        else "READY"
    )
    return {
        "schema_version": "empire.leadgen.ops_truth.v1",
        "status": state,
        "preflight_checks_clear": state == "READY",
        "integrity_findings": inconsistent,
        "readiness_blockers": blocked,
        "integrity_finding_count": len(inconsistent),
        "readiness_blocker_count": len(blocked),
        "campaign_measured_matches": count if valid_count else None,
        "campaign_outcome_proved": bool(measured_proved),
        "owned_mailbox_configured": bool(relay_ready),
        "lead_smart_launch_ready": bool(leadsmart_ready),
        "qualification_timer_boot_enabled": bool(qualifier_timer_enabled),
        "gtm_founder_reviews_pending": founder_count if founder_count_valid else None,
        "mode": "OBSERVE",
        "execution_authority": "NONE",
        "automatic_repairs_executed": 0,
        "actual_revenue": False,
    }


USER_WORKER_UNITS = (
    "empire-acquisition.service",
    "empire-call-manager.service",
    "empire-hunter-outcome-learning.service",
    "empire-market-gps.service",
)


def observe_user_workers(
    *,
    runner=subprocess.run,
    effective_uid: int | None = None,
) -> dict[str, Any]:
    """Observe known user-owned workers; never restart them or expose env files.

    Ops Control runs as root. Drop privilege for the Ubuntu user's systemd
    manager instead of interacting with it through root's own user scope.
    """
    uid = os.geteuid() if effective_uid is None else effective_uid
    base = ["systemctl", "--user", "show"]
    if uid == 0:
        base = [
            "runuser", "-u", "ubuntu", "--", "env",
            "XDG_RUNTIME_DIR=/run/user/1000",
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
            *base,
        ]
    rows: list[dict[str, str]] = []
    unavailable = 0
    for unit in USER_WORKER_UNITS:
        try:
            result = runner(
                [*base, unit, "-p", "ActiveState", "-p", "Result"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            fields = dict(
                line.split("=", 1) for line in result.stdout.splitlines()
                if "=" in line
            )
            if result.returncode:
                state, reason = "unknown", "user_manager_unavailable"
            else:
                state = fields.get("ActiveState") or "unknown"
                reason = fields.get("Result") or "unknown"
        except (OSError, ValueError, subprocess.SubprocessError):
            state, reason = "unknown", "user_manager_unavailable"
        if state == "unknown":
            unavailable += 1
        rows.append({"unit": unit, "state": state, "result": reason})
    failures = [row["unit"] for row in rows if row["state"] == "failed"]
    return {
        "schema_version": "empire.user_worker_health.v1",
        "status": (
            "DEGRADED" if failures
            else "UNKNOWN" if unavailable
            else "HEALTHY"
        ),
        "observed_worker_count": len(rows),
        "failed_worker_count": None if unavailable else len(failures),
        "confirmed_failed_worker_count": len(failures),
        "user_manager_unavailable_count": unavailable,
        "failed_workers": failures,
        "workers": rows,
        "mode": "OBSERVE",
        "automatic_repairs_executed": 0,
        "execution_authority": "NONE",
    }


def leadgen_truth_transition(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Diff only stable reason codes; no contacts, money or secrets are logged."""
    previous = previous if isinstance(previous, Mapping) else {}
    prior = previous.get("leadgen_truth")
    prior = prior if isinstance(prior, Mapping) else {}
    before = set(prior.get("integrity_findings") or []) | set(
        prior.get("readiness_blockers") or []
    )
    after = set(current.get("integrity_findings") or []) | set(
        current.get("readiness_blockers") or []
    )
    prior_status = prior.get("status") if prior else None
    status = current.get("status")
    return {
        "changed": prior_status != status or before != after,
        "previous_status": prior_status,
        "current_status": status,
        "new_findings": sorted(after - before),
        "resolved_findings": sorted(before - after),
        "active_finding_count": len(after),
        "automatic_repairs_executed": 0,
        "execution_authority": "NONE",
    }


def main() -> int:
    mode = os.getenv("EMPIRE_OPS_HEAL_MODE", "OBSERVE").strip().upper()
    if mode not in {"OBSERVE", "GUARDED_EXECUTE"}:
        mode = "OBSERVE"

    egress_contained = supabase_egress_contained()
    runtime_doctor = run_runtime_self_heal(
        observe_only=(mode != "GUARDED_EXECUTE" or egress_contained),
    )
    sentinel = observe(unit_state)
    sentinel = _apply_egress_containment_context(
        sentinel,
        contained=egress_contained,
    )
    repairs = []
    if mode == "GUARDED_EXECUTE" and not egress_contained:
        repairs = execute_plan(sentinel.get("repair_plan") or [], max_actions=3)

    engineering_log = Path("/srv/empire_os/runtime/engineering_health/pytest_latest.log")
    engineering_health = build_engineering_health_report(engineering_log)
    incident_manager = build_incident_report(sentinel)
    if engineering_health is not None:
        engineering_incidents = engineering_health["incident_report"]
        incident_manager["diagnoses"].extend(engineering_incidents["diagnoses"])
        incident_manager["incident_count"] = len(incident_manager["diagnoses"])
        incident_manager["requires_escalation"] = (
            incident_manager["requires_escalation"] or engineering_incidents["requires_escalation"]
        )
        incident_manager["highest_priority"] = max(
            (item["commercial_priority"] for item in incident_manager["diagnoses"]),
            default=None,
        )
        incident_manager["engineering_health"] = engineering_health
    try:
        commercial_loop = read_commercial_loop(
            Path("/srv/empire_os/runtime/commercial_loop/latest.json")
        )
        commercial_loop_read_error = None
    except CommercialLoopReadError as exc:
        commercial_loop = {}
        commercial_loop_read_error = str(exc)
    conveyor = build_conveyor(
        commercial_loop if isinstance(commercial_loop, dict) else {}
    )
    if commercial_loop_read_error:
        conveyor["commercial_loop_read_error"] = commercial_loop_read_error
        conveyor["current_blocker"] = "commercial_loop_snapshot_unavailable"
        conveyor["blocker_state"] = "unknown"
        conveyor["owner_component"] = "commercial_loop_observer"
        conveyor["authority"] = "observe"
        conveyor["next_event"] = "commercial_loop_snapshot_refresh_required"
        conveyor["loop_complete"] = False

    findings = sentinel.get("findings") or []
    blocking_findings = [
        row
        for row in findings
        if row.get("severity") in {"critical", "warning"}
    ]
    leadgen_truth = observe_leadgen_truth()
    user_worker_health = observe_user_workers()
    # Add passive sovereign capacity/recovery evidence to the SAME Ops Control
    # snapshot and incident fabric; never add units to the healer allowlist.
    sovereign_infrastructure = collect_sovereign_infrastructure_health()
    # Existing Founder Ops snapshot: only counts and control states,
    # never reply bodies, sender identities, outbound or DB connections.
    conversation_evidence_review = inspect_conversation_evidence(Path("/srv/empire_os"))
    passive_incidents = build_incident_report({
        "findings": sovereign_infrastructure["service_findings"],
    })
    if passive_incidents["incident_count"]:
        incident_manager["diagnoses"].extend(passive_incidents["diagnoses"])
        incident_manager["incident_count"] = len(incident_manager["diagnoses"])
        incident_manager["requires_escalation"] = (
            incident_manager["requires_escalation"] or passive_incidents["requires_escalation"]
        )
        incident_manager["highest_priority"] = max(
            (item["commercial_priority"] for item in incident_manager["diagnoses"]),
            default=None,
        )
    health_domains = {
        "conversation_evidence": conversation_evidence_review["status"],
        "sovereign_infrastructure": sovereign_infrastructure["status"],
        "user_owned_workers": user_worker_health["status"],
        "leadgen_commercial_truth": leadgen_truth["status"],
        "infrastructure": (
            "HEALTHY"
            if runtime_doctor.get("status") == "HEALTHY"
            else "DEGRADED"
        ),
        "services_and_timers": (
            "DEGRADED"
            if any(
                row.get("code") in {
                    "critical_service_down",
                    "critical_timer_down",
                }
                for row in blocking_findings
            )
            else "HEALTHY"
        ),
        "acquisition_and_buyer_pipeline": (
            "DEGRADED"
            if any(
                row.get("code") in {
                    "source_pipeline_degraded",
                    "buyer_review_worker_failed",
                }
                for row in blocking_findings
            )
            else "HEALTHY"
        ),
        "model_providers": (
            "DEGRADED"
            if any(
                row.get("code") in {
                    "model_provider_degraded",
                    "coder_model_route_degraded",
                }
                for row in blocking_findings
            )
            else "HEALTHY"
        ),
    }

    try:
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    # Seed exactly one baseline event when change-only history is first installed.
    if not (OUTPUT.parent / "leadgen_truth_transitions.jsonl").exists():
        previous = {}
    transition = leadgen_truth_transition(previous, leadgen_truth)

    payload = {
        "schema_version": "empire.ops_control_cycle.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "supabase_egress_contained": egress_contained,
        "runtime_doctor": runtime_doctor,
        "sentinel": sentinel,
        "health_domains": health_domains,
        "leadgen_truth": leadgen_truth,
        "user_worker_health": user_worker_health,
        "sovereign_infrastructure": sovereign_infrastructure,
        "conversation_evidence_review": conversation_evidence_review,
        "leadgen_truth_transition": transition,
        "leadgen_preflight_checks_clear": leadgen_truth["preflight_checks_clear"],
        "blocking_finding_count": len(blocking_findings),
        "blocking_findings": blocking_findings,
        "healer": {
            "proposed": len(sentinel.get("repair_plan") or []),
            "executed": len(repairs),
            "results": repairs,
        },
        "incident_manager": incident_manager,
        "conveyor": conveyor,
        "healthy": (
            runtime_doctor.get("status") == "HEALTHY"
            and not blocking_findings
        ),
        "business_blocker": next(
            (
                row.get("evidence", {}).get("highest_blocker")
                for row in sentinel.get("findings") or []
                if row.get("code") == "commercial_loop_blocked"
            ),
            None,
        ),
    }
    incident_output = Path("/srv/empire_os/runtime/incidents/latest.json")
    incident_output.parent.mkdir(parents=True, exist_ok=True)
    incident_tmp = incident_output.with_suffix(".json.tmp")
    incident_tmp.write_text(json.dumps(incident_manager, indent=2, sort_keys=True) + "\n")
    incident_tmp.replace(incident_output)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    if transition["changed"]:
        # Durable event history is change-only; no repeated timer noise.
        changes = OUTPUT.parent / "leadgen_truth_transitions.jsonl"
        event = {"observed_at": payload["observed_at"], **transition}
        with changes.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))

    failed_repairs = [row for row in repairs if row.get("ok") is not True]
    return 2 if failed_repairs else 0


if __name__ == "__main__":
    raise SystemExit(main())
