"""Independent EmpireOS Orchestration Integrity Guardian.

Read-only executive control auditor. Does not implement tasks, alter the durable
queue, restart systemd, perform outbound actions, or grant authority. Checks
ASTRA itself independently of ASTRA's own success reports.

Owner: Engineering / Control Fabric assurance; escalation: Founder/ASTRA.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

SCHEMA = "empire.orchestration_integrity_guardian.v1"
OUTPUT = Path("runtime/orchestration_integrity/latest.json")
QUEUE_DIR = Path("runtime/departments/work")
DISPATCH = Path("runtime/astra/department_dispatch_latest.json")
EVALUATION = Path("runtime/astra/executive_evaluation_latest.json")
SERVICE = "empire-department-cycle.service"
# These are ceilings on a known deficient service, NOT a safe target.
MAX_EXISTING_POST_HOOKS = 57
MAX_EXISTING_DROPINS = 42
MAX_QUEUE_ITEMS = 30000
MAX_EXECUTIVE_AGE = 1200


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _stamp_age(value: Any, now: datetime) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            return None
    except ValueError:
        return None
    return (now - parsed.astimezone(timezone.utc)).total_seconds()


def observe_service() -> dict[str, Any]:
    """Live read-only systemd observation, never a guessed baseline."""
    try:
        config = subprocess.run(
            ["systemctl", "cat", SERVICE], capture_output=True, text=True,
            timeout=8, check=False,
        )
        state = subprocess.run(
            ["systemctl", "show", SERVICE, "-p", "ActiveState",
             "-p", "SubState", "-p", "Result", "-p", "TimeoutStartUSec"],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "systemd_read_unavailable"}
    if config.returncode or state.returncode:
        return {"available": False, "reason": "systemd_service_unavailable"}
    values = dict(line.split("=", 1) for line in state.stdout.splitlines() if "=" in line)
    return {
        "available": True,
        "post_hook_count": sum(
            line.strip().startswith("ExecStartPost=")
            for line in config.stdout.splitlines()
        ),
        "drop_in_count": sum(
            ".service.d/" in line and line.startswith("# /")
            for line in config.stdout.splitlines()
        ),
        "active_state": values.get("ActiveState", "unknown"),
        "sub_state": values.get("SubState", "unknown"),
        "process_result": values.get("Result", "unknown"),
        "timeout_start_usec": values.get("TimeoutStartUSec"),
        "evidence": "live:systemd:" + SERVICE,
    }


def observe_queue(root: Path) -> dict[str, Any]:
    """Inspect actual stage outcomes and ownership, not aggregate DONE labels."""
    counts: Counter[str] = Counter()
    stage_only: Counter[str] = Counter()
    root_causes: Counter[tuple[str, str, str]] = Counter()
    malformed = 0
    unowned = 0
    scanned = 0
    statuses = ("ready", "running", "review", "done", "blocked", "failed")
    if not all((root / QUEUE_DIR / status).is_dir() for status in statuses):
        return {"available": False, "reason": "canonical_queue_directories_missing"}
    for status in statuses:
        for path in (root / QUEUE_DIR / status).glob("*.json"):
            scanned += 1
            if scanned > MAX_QUEUE_ITEMS:
                return {"available": False, "reason": "queue_scan_limit"}
            row = _read_json(path)
            if not row or row.get("status") != status.upper() or not isinstance(row.get("id"), str):
                malformed += 1
                continue
            counts[status] += 1
            result = row.get("result")
            result = result if isinstance(result, dict) else {}
            if status == "done" and result.get("implementation_performed") is False:
                stage_only[str(row.get("target_component") or "unknown")] += 1
            if status in ("failed", "blocked"):
                owners = row.get("department_keys")
                if not isinstance(owners, list) or not owners:
                    unowned += 1
                owner = ",".join(sorted(owners)) if isinstance(owners, list) and owners else "UNOWNED"
                reason = str(row.get("error") or "")
                if "insufficient_verified_outcome_cohort" in reason:
                    cause = "real_outcome_evidence_missing"
                elif "specialist_adapter_required" in reason:
                    cause = "specialist_adapter_missing"
                elif "runtime provider is not configured" in reason:
                    cause = "database_provider_unconfigured"
                elif "exceed_egress_quota" in reason:
                    cause = "provider_egress_restricted"
                elif "timeout" in reason:
                    cause = "adapter_timeout"
                else:
                    cause = "other_canonical_failure"
                root_causes[(owner, str(row.get("target_component") or "unknown"), cause)] += 1
    return {
        "available": True,
        "counts": {k: counts[k] for k in ("ready", "running", "review", "done", "blocked", "failed")},
        "unresolved_count": sum(counts[k] for k in ("ready", "running", "review", "blocked", "failed")),
        "blocked_or_failed_count": counts["blocked"] + counts["failed"],
        "stage_only_done_not_implementation_count": sum(stage_only.values()),
        "stage_only_by_target": dict(stage_only),
        "unowned_exceptions": unowned,
        "malformed_work_items": malformed,
        "owner_incidents": [
            {"departments": owner, "component": component, "root_cause": cause, "count": amount}
            for (owner, component, cause), amount in sorted(
                root_causes.items(), key=lambda row: (-row[1], row[0])
            )[:12]
        ],
        "evidence": "canonical:department_work_queue",
    }


def assess(
    queue: Mapping[str, Any], service: Mapping[str, Any],
    dispatch: Mapping[str, Any] | None,
    evaluation: Mapping[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Pure governance decision. No edits, retries, or service control."""
    if now.utcoffset() is None:
        raise ValueError("aware clock required")
    issues: list[dict[str, Any]] = []
    def add(code: str, severity: str, owner: str, evidence: str, *, gate: bool = False) -> None:
        issues.append({"code": code, "severity": severity,
                       "owner": owner, "evidence": evidence,
                       "release_gate_violation": gate})

    if service.get("available") is not True:
        add("SERVICE_TRUTH_UNAVAILABLE", "CRITICAL", "engineering", "live:systemd", gate=True)
    else:
        hooks = service.get("post_hook_count")
        dropins = service.get("drop_in_count")
        if type(hooks) is not int or type(dropins) is not int:
            add("SERVICE_COUNTS_INVALID", "CRITICAL", "engineering", "live:systemd", gate=True)
        else:
            if hooks > MAX_EXISTING_POST_HOOKS or dropins > MAX_EXISTING_DROPINS:
                add("ARCHITECTURE_HOOK_GROWTH", "CRITICAL", "engineering",
                    "live:systemd:service_wiring", gate=True)
            if hooks >= MAX_EXISTING_POST_HOOKS:
                add("EXISTING_SERIAL_HOOK_DEBT", "HIGH", "engineering",
                    "live:systemd:service_wiring")
        if service.get("sub_state") == "start-post":
            add("SERIAL_EXECUTION_STILL_RUNNING", "HIGH", "operations_fulfilment",
                "live:systemd:service_state")

    if queue.get("available") is not True:
        add("QUEUE_TRUTH_UNAVAILABLE", "CRITICAL", "engineering",
            "canonical:department_work_queue", gate=True)
    else:
        if queue.get("malformed_work_items"):
            add("QUEUE_CORRUPTION_OR_SCHEMA_DRIFT", "CRITICAL", "engineering",
                "canonical:department_work_queue", gate=True)
        if queue.get("unowned_exceptions"):
            add("UNOWNED_WORK_EXCEPTIONS", "CRITICAL", "strategy_executive",
                "canonical:department_work_queue", gate=True)
        if queue.get("blocked_or_failed_count", 0):
            add("UNRESOLVED_EXECUTIVE_EXCEPTIONS", "HIGH", "strategy_executive",
                "canonical:department_work_queue")
        if queue.get("stage_only_done_not_implementation_count", 0):
            add("STAGE_DONE_IS_NOT_CUSTOMER_DELIVERY", "HIGH", "strategy_executive",
                "canonical:department_work_queue")

    if dispatch is None or evaluation is None:
        add("EXECUTIVE_REPORT_MISSING", "CRITICAL", "strategy_executive",
            "runtime:astra", gate=True)
    else:
        for name, source in (("dispatch", dispatch), ("evaluation", evaluation)):
            age = _stamp_age(source.get("generated_at"), now)
            if age is None or age < -120 or age > MAX_EXECUTIVE_AGE:
                add("STALE_" + name.upper(), "CRITICAL", "strategy_executive",
                    "runtime:astra:" + name, gate=True)
        if dispatch.get("customer_delivery_verified") is True and queue.get("unresolved_count", 0):
            add("FALSE_CUSTOMER_DELIVERY_CLAIM", "CRITICAL", "strategy_executive",
                "runtime:astra:dispatch", gate=True)
        if evaluation.get("plan_success_claimed") is True and (
            evaluation.get("evaluation_state") not in ("INTERNAL_WORK_COMPLETE",)
            or not evaluation.get("result_evidence_refs")
        ):
            add("FALSE_PLAN_SUCCESS_CLAIM", "CRITICAL", "strategy_executive",
                "runtime:astra:evaluation", gate=True)

    return {
        "schema_version": SCHEMA,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "agent": "Orchestration Integrity Guardian",
        "mode": "OBSERVE",
        "status": "CRITICAL" if any(x["severity"] == "CRITICAL" for x in issues) else
                  "DEGRADED" if issues else "HEALTHY",
        "release_gate": "REJECT" if any(x["release_gate_violation"] for x in issues) else "NO_NEW_VIOLATION",
        "current_business_completion_verified": False,
        "queue_truth": dict(queue),
        "service_truth": dict(service),
        "findings": issues,
        "finding_count": len(issues),
        "executive_incident_owners": list(queue.get("owner_incidents") or []),
        "next_action": "Correct release-gate violations and prove end-to-end completion; keep pre-existing debt open until fixed.",
        "outbound_sent": False,
        "production_mutation": False,
        "revenue_recognized": False,
        "execution_authority": "none",
    }


def run_guardian(root: str | Path, *, now: datetime | None = None,
                 service: Mapping[str, Any] | None = None) -> dict[str, Any]:
    repo = Path(root).resolve()
    result = assess(
        observe_queue(repo),
        observe_service() if service is None else service,
        _read_json(repo / DISPATCH),
        _read_json(repo / EVALUATION),
        now=now or datetime.now(timezone.utc),
    )
    path = repo / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return result
