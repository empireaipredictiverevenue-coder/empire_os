#!/usr/bin/env python3
"""One bounded EmpireOS reliability control cycle."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from empire_os.control_conveyor import build_conveyor
from empire_os.incident_manager import build_incident_report
from empire_os.ops_healer import execute_plan
from empire_os.ops_sentinel import observe
from empire_os.runtime_self_heal import run_runtime_self_heal
from empire_os.supabase_egress_guard import supabase_egress_contained

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


def main() -> int:
    mode = os.getenv("EMPIRE_OPS_HEAL_MODE", "OBSERVE").strip().upper()
    if mode not in {"OBSERVE", "GUARDED_EXECUTE"}:
        mode = "OBSERVE"

    egress_contained = supabase_egress_contained()
    runtime_doctor = run_runtime_self_heal(
        observe_only=(mode != "GUARDED_EXECUTE" or egress_contained),
    )
    sentinel = observe(unit_state)
    repairs = []
    if mode == "GUARDED_EXECUTE" and not egress_contained:
        repairs = execute_plan(sentinel.get("repair_plan") or [], max_actions=3)

    incident_manager = build_incident_report(sentinel)
    try:
        commercial_loop = json.loads(
            Path("/srv/empire_os/runtime/commercial_loop/latest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        commercial_loop = {}
    conveyor = build_conveyor(
        commercial_loop if isinstance(commercial_loop, dict) else {}
    )

    findings = sentinel.get("findings") or []
    blocking_findings = [
        row
        for row in findings
        if row.get("severity") in {"critical", "warning"}
    ]
    health_domains = {
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

    payload = {
        "schema_version": "empire.ops_control_cycle.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "supabase_egress_contained": egress_contained,
        "runtime_doctor": runtime_doctor,
        "sentinel": sentinel,
        "health_domains": health_domains,
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
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))

    failed_repairs = [row for row in repairs if row.get("ok") is not True]
    return 2 if failed_repairs else 0


if __name__ == "__main__":
    raise SystemExit(main())
