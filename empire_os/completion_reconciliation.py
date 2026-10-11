"""Reconcile live completion checklist items with automated verification evidence."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from empire_os.completion_task_memory import (
    load_attempt_memory, preflight_task, prior_completion_plan_handoffs,
    task_key,
)
from empire_os.master_execution_ledger import parse_checklist

SCHEMA_VERSION = "empire.completion_reconciliation.v1"
DISPATCH = Path("runtime/execution_plane/business_completion_dispatch_latest.json")
OUTPUT = Path("runtime/execution_plane/completion_reconciliation_latest.json")


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _verification_jobs(root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    jobs_root = root / "runtime/coder/jobs"
    for bucket in ("pending", "running", "completed", "failed"):
        for path in (jobs_root / bucket).glob("*.json"):
            packet = _read(path)
            if packet is None or packet.get("kind") != "VERIFY":
                continue
            source = packet.get("payload") or {}
            item_ids = [
                str(value).strip()
                for value in (source.get("completion_item_ids") or ())
                if str(value).strip()
            ]
            if not item_ids:
                continue
            row = {
                "bucket": bucket,
                "job_id": packet.get("id"),
                "updated_at": packet.get("updated_at"),
                "status": packet.get("status"),
                "error": packet.get("error"),
                "result": packet.get("result") or {},
                "tests": list(source.get("tests") or ()),
            }
            for item_id in item_ids:
                current = latest.get(item_id)
                if (
                    current is None
                    or str(row.get("updated_at") or "")
                    >= str(current.get("updated_at") or "")
                ):
                    latest[item_id] = row
    return latest


def _verify_verdict(job: Mapping[str, Any]) -> str | None:
    result = job.get("result")
    if not isinstance(result, Mapping):
        return None
    verification = result.get("verification")
    if not isinstance(verification, Mapping):
        return None
    value = str(verification.get("verdict") or "").strip().upper()
    return value or None


def _state_for(
    *,
    execution_class: str,
    verify_ready: bool,
    job: Mapping[str, Any] | None,
) -> str:
    if execution_class == "founder_gate":
        return "FOUNDER_GATE"
    if job is not None:
        bucket = str(job.get("bucket") or "")
        if bucket == "pending":
            return "VERIFY_QUEUED"
        if bucket == "running":
            return "VERIFYING"
        if bucket == "failed":
            return "NEEDS_WIRING_OR_TEST_FIX"
        verdict = _verify_verdict(job)
        if verdict in {"PASS", "PASS_WITH_WARNINGS"}:
            if execution_class == "evidence_required":
                return "REAL_WORLD_EVIDENCE_REQUIRED"
            return "NEEDS_LIVE_PROOF"
        return "NEEDS_WIRING_OR_TEST_FIX"
    if execution_class == "evidence_required":
        return "REAL_WORLD_EVIDENCE_REQUIRED"
    if execution_class == "builder_required":
        return "NEEDS_WIRING"
    if verify_ready:
        return "VERIFY_NOT_MATERIALIZED"
    return "REVIEW_REQUIRED"


def refresh_completion_reconciliation(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    dispatch = _read(root / DISPATCH)

    if dispatch is None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "completion_dispatch_unavailable",
            "generated_at": current.isoformat(),
            "execution_authority": "none",
        }
        _atomic_write(root / OUTPUT, payload)
        return payload

    memory = load_attempt_memory(root, now=current)
    if memory.get("status") != "AVAILABLE":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "MEMORY_INVALID_HOLD",
            "mode": "OBSERVE",
            "reason": "shared_attempt_memory_unavailable",
            "generated_at": current.isoformat(),
            "execution_authority": "none",
        }
        _atomic_write(root / OUTPUT, payload)
        return payload

    plan_history = prior_completion_plan_handoffs(root)
    if plan_history.get("status") != "AVAILABLE":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "PLAN_HISTORY_INVALID_HOLD",
            "reason": "historic_plan_handoff_evidence_unavailable",
            "execution_authority": "none",
        }
        _atomic_write(root / OUTPUT, payload)
        return payload

    checklist_path = root / "docs/MASTER_REMAINING_CHECKLIST.md"
    try:
        checklist_items = parse_checklist(checklist_path)
    except OSError:
        checklist_items = []
    canonical_by_id = {
        "check_" + sha256(
            f"{row.line}|{row.section}|{row.item}".encode("utf-8")
        ).hexdigest()[:16]: row
        for row in checklist_items if row.status == "PENDING"
    }
    jobs = _verification_jobs(root)
    items: list[dict[str, Any]] = []
    for packet in dispatch.get("packets") or ():
        if not isinstance(packet, Mapping):
            continue
        item_ids = list(packet.get("item_ids") or ())
        lines = list(packet.get("checklist_lines") or ())
        for index, item_id in enumerate(item_ids):
            item_id = str(item_id).strip()
            if not item_id:
                continue
            job = jobs.get(item_id)
            execution_class = str(
                packet.get("execution_class") or ""
            ).strip()
            state = _state_for(
                execution_class=execution_class,
                verify_ready=(
                    packet.get("verification_contract_ready") is True
                ),
                job=job,
            )
            known = canonical_by_id.get(item_id)
            prior = (
                preflight_task(
                    memory, section=known.section, item=known.item,
                ) if known is not None else None
            )
            attempt_state = (
                prior.get("reason")
                if isinstance(prior, dict)
                and prior.get("decision") in {
                    "HOLD", "REVIEW_NEW_EVIDENCE",
                } else None
            )
            previous_plan = (
                plan_history["by_task"].get(
                    task_key(known.section, known.item)
                )
                if known is not None else None
            )
            # A submitted PLAN is NOT implementation, approval, or live proof.
            if (previous_plan
                    and attempt_state is None
                    and execution_class != "founder_gate"
                    and state in {"NEEDS_WIRING", "REVIEW_REQUIRED",
                                  "VERIFY_NOT_MATERIALIZED"}):
                state = "PLAN_HANDOFF_ONLY_BUILD_OR_VERIFY_PENDING"
            # The memory is evidence of *work*, never a live-closure proof.
            # Founder gates remain founder gates regardless of memory.
            if execution_class != "founder_gate":
                if attempt_state == "CODE_VERIFIED_NOT_LIVE":
                    state = "CODE_COMPLETE_NOT_LIVE"
                elif attempt_state == "PROVIDER_CAPACITY_BLOCKED":
                    state = "BUILDER_PROVIDER_BLOCKED"
                elif attempt_state == "REVIEW_REQUIRED":
                    state = "REVIEW_PRIOR_ATTEMPT"
                elif attempt_state == "RESOLVED_WITH_NEW_EVIDENCE":
                    state = "INDEPENDENT_REVIEW_REQUIRED_BEFORE_RETRY"
            items.append({
                "item_id": item_id,
                "checklist_line": (
                    lines[index] if index < len(lines) else None
                ),
                "department": packet.get("department"),
                "workstreams": list(packet.get("workstreams") or ()),
                "execution_class": execution_class,
                "state": state,
                "attempt_memory_state": attempt_state,
                "attempt_memory_id": (
                    prior.get("last_attempt_id")
                    if isinstance(prior, dict) else None
                ),
                "attempt_memory_commit": (
                    prior.get("commit")
                    if isinstance(prior, dict) else None
                ),
                "attempt_memory_blocker": (
                    prior.get("blocker")
                    if isinstance(prior, dict) else None
                ),
                "historical_plan_work_id": (
                    previous_plan.get("work_id") if previous_plan else None
                ),
                "historical_plan_job_id": (
                    previous_plan.get("coder_job_id") if previous_plan else None
                ),
                "plan_handoff_is_not_implementation": True,
                "verification_job_id": (
                    job.get("job_id") if job else None
                ),
                "verification_verdict": (
                    _verify_verdict(job) if job else None
                ),
                "verification_error": (
                    job.get("error") if job else None
                ),
                "verification_tests": (
                    job.get("tests") if job else []
                ),
                "checklist_mutation_performed": False,
            })

    counts = Counter(row["state"] for row in items)
    remediation = [
        row for row in items
        if row["state"] == "NEEDS_WIRING_OR_TEST_FIX"
    ]
    live_proof = [
        row for row in items
        if row["state"] == "NEEDS_LIVE_PROOF"
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "canonical_total_count": dispatch.get("canonical_total_count"),
        "canonical_done_count": dispatch.get("canonical_done_count"),
        "canonical_pending_count": dispatch.get("source_pending_count"),
        "reconciled_item_count": len(items),
        "state_counts": dict(sorted(counts.items())),
        "attempt_memory_event_count": memory["event_count"],
        "attempt_memory_known_task_count": memory["known_task_count"],
        "attempt_memory_held_task_count": memory["held_task_count"],
        "historical_plan_packet_count": plan_history["historical_plan_packet_count"],
        "historical_plan_task_count": plan_history["historically_planned_task_count"],
        "remediation_candidate_count": len(remediation),
        "live_proof_candidate_count": len(live_proof),
        "founder_gate_count": int(counts.get("FOUNDER_GATE", 0)),
        "real_world_evidence_required_count": int(
            counts.get("REAL_WORLD_EVIDENCE_REQUIRED", 0)
        ),
        "items": items,
        "remediation_candidates": remediation,
        "live_proof_candidates": live_proof,
        "verified_done_count": 0,
        "automatic_checklist_mutation_allowed": False,
        "code_presence_is_not_completion": True,
        "production_mutation": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload
