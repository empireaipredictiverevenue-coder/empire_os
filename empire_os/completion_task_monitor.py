"""OBSERVE-only monitor for EmpireOS canonical completion tasks.

Materialised by the *existing* department cycle. No new timer, executor,
provider, database, commercial action, or agent is created. Historical PLAN
handoffs never become verified implementations or live outcomes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from empire_os.master_execution_ledger import LedgerItem, parse_checklist

SCHEMA = "empire.completion-task-monitor.v1"
RECONCILIATION_SCHEMA = "empire.completion_reconciliation.v1"
CHECKLIST = Path("docs/MASTER_REMAINING_CHECKLIST.md")
RECONCILIATION = Path("runtime/execution_plane/completion_reconciliation_latest.json")
OUTPUT = Path("runtime/execution_plane/completion_task_monitor_latest.json")
MAX_TASKS = 2000
MAX_HISTORY = 120
SOURCE_MAX_AGE = timedelta(minutes=20)
STALLED_AFTER = timedelta(hours=24)
ACTIVE_STATES = frozenset({"VERIFYING", "VERIFY_QUEUED"})
PRIORITY_STATES = {
    "BUILDER_PROVIDER_BLOCKED": (0, "PROVIDER_CAPACITY_HOLD",
        "Verify model capacity once before reconsidering the blocked implementation"),
    "NEEDS_WIRING_OR_TEST_FIX": (1, "FAILED_VERIFICATION",
        "Inspect the exact failed verification evidence before a bounded repair"),
    "CODE_COMPLETE_NOT_LIVE": (2, "DEPLOYMENT_EVIDENCE_REQUIRED",
        "Review the existing tested commit, then obtain governed production runtime proof"),
    "FOUNDER_GATE": (3, "FOUNDER_APPROVAL_REQUIRED",
        "Collect the exact approval evidence; never auto-approve"),
    "REAL_WORLD_EVIDENCE_REQUIRED": (4, "REAL_WORLD_PROOF_REQUIRED",
        "Collect independent buyer, payment or fulfilment evidence as applicable"),
    "NEEDS_LIVE_PROOF": (5, "LIVE_EVIDENCE_REQUIRED",
        "Verify actual production behaviour; test success alone is not completion"),
    "PLAN_HANDOFF_ONLY_BUILD_OR_VERIFY_PENDING": (6, "IMPLEMENTATION_NOT_VERIFIED",
        "Inspect the previous PLAN handoff and assign only new verified implementation"),
    "VERIFY_QUEUED": (7, "VERIFICATION_QUEUED", "Observe existing verification queue"),
    "VERIFYING": (7, "VERIFICATION_RUNNING", "Observe existing verification run"),
    "REVIEW_PRIOR_ATTEMPT": (3, "PRIOR_ATTEMPT_REVIEW",
        "Review the recorded prior attempt before any new work"),
    "INDEPENDENT_REVIEW_REQUIRED_BEFORE_RETRY": (3, "RETRY_REQUIRES_REVIEW",
        "Review new recovery evidence; no automatic retry"),
    "NEEDS_WIRING": (6, "IMPLEMENTATION_NOT_VERIFIED",
        "Investigate existing code and test evidence before implementation"),
    "VERIFY_NOT_MATERIALIZED": (6, "VERIFICATION_NOT_MATERIALIZED",
        "Find the actual verifier job before claiming verification"),
    "REVIEW_REQUIRED": (6, "REVIEW_REQUIRED",
        "Inspect the current exact checklist and evidence"),
}


class MonitorEvidenceError(ValueError):
    """Source is stale, incomplete, inconsistent or outside monitoring scope."""


def _stamp(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 48:
        raise MonitorEvidenceError("timestamp_not_valid")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MonitorEvidenceError("timestamp_not_valid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise MonitorEvidenceError("timestamp_not_aware")
    return stamp.astimezone(timezone.utc)


def _integer(value: Any) -> bool:
    return type(value) is int and 0 <= value <= MAX_TASKS


def _id(row: LedgerItem) -> str:
    digest = sha256(f"{row.line}|{row.section}|{row.item}".encode("utf-8"))
    return "check_" + digest.hexdigest()[:16]


def _key(row: LedgerItem) -> str:
    # Use the shared memory key so task identity survives line shifts.
    from empire_os.completion_task_memory import task_key
    return task_key(row.section, row.item)


def _previous_map(
    previous: Mapping[str, Any] | None, *,
    current: datetime,
) -> tuple[dict[str, Mapping[str, Any]], list[dict[str, Any]], datetime | None]:
    if previous is None:
        return {}, [], None
    if (previous.get("schema_version") != SCHEMA
            or previous.get("status") != "AVAILABLE"
            or previous.get("mode") != "OBSERVE"
            or previous.get("execution_authority") != "none"
            or previous.get("external_execution_performed") is not False):
        raise MonitorEvidenceError("previous_monitor_provenance_invalid")
    generated = _stamp(previous.get("generated_at"))
    if generated > current:
        raise MonitorEvidenceError("previous_monitor_from_future")
    prior = previous.get("items")
    timeline = previous.get("recent_transitions")
    if (not isinstance(prior, list) or len(prior) > MAX_TASKS
            or not isinstance(timeline, list) or len(timeline) > MAX_HISTORY):
        raise MonitorEvidenceError("previous_monitor_items_invalid")
    found: dict[str, Mapping[str, Any]] = {}
    for row in prior:
        if not isinstance(row, Mapping):
            raise MonitorEvidenceError("previous_monitor_row_invalid")
        key = row.get("task_key")
        if not isinstance(key, str) or not key.startswith("task_") or key in found:
            raise MonitorEvidenceError("previous_monitor_identity_ambiguous")
        if not isinstance(row.get("state"), str) or row["state"] not in PRIORITY_STATES:
            raise MonitorEvidenceError("previous_monitor_stage_untrusted")
        first, stage_at = _stamp(row.get("first_monitored_at")), _stamp(row.get("state_since"))
        if first > stage_at or stage_at > generated:
            raise MonitorEvidenceError("previous_monitor_clock_conflict")
        if not isinstance(row.get("monitored_cycles"), int) or type(row["monitored_cycles"]) is not int or row["monitored_cycles"] < 1:
            raise MonitorEvidenceError("previous_monitor_cycle_count_invalid")
        found[key] = row
    for event in timeline:
        if (not isinstance(event, dict) or event.get("task_key") not in found
                and event.get("to_state") != "CHECKLIST_MARKED_DONE"
                or event.get("from_state") not in PRIORITY_STATES
                or event.get("to_state") not in (set(PRIORITY_STATES) | {"CHECKLIST_MARKED_DONE"})
                or _stamp(event.get("observed_at")) > generated):
            raise MonitorEvidenceError("previous_monitor_transition_invalid")
    return found, list(timeline), generated


def build_completion_task_monitor(
    checklist: list[LedgerItem],
    reconciliation: Mapping[str, Any],
    *,
    now: datetime,
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure, fail-closed task monitor. Never dispatch or close a task."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise MonitorEvidenceError("monitor_clock_not_aware")
    current = now.astimezone(timezone.utc)
    if not isinstance(reconciliation, Mapping):
        raise MonitorEvidenceError("reconciliation_not_a_mapping")
    if (reconciliation.get("schema_version") != RECONCILIATION_SCHEMA
            or reconciliation.get("status") != "AVAILABLE"
            or reconciliation.get("mode") != "OBSERVE"
            or reconciliation.get("execution_authority") != "none"
            or reconciliation.get("external_execution_performed") is not False
            or reconciliation.get("automatic_checklist_mutation_allowed") is not False
            or reconciliation.get("production_mutation") is not False
            or type(reconciliation.get("verified_done_count")) is not int
            or reconciliation.get("verified_done_count") != 0):
        raise MonitorEvidenceError("reconciliation_contract_not_trusted")
    source_time = _stamp(reconciliation.get("generated_at"))
    age = current - source_time
    if age < -timedelta(minutes=2) or age > SOURCE_MAX_AGE:
        raise MonitorEvidenceError("reconciliation_stale_or_from_future")
    if len(checklist) > MAX_TASKS:
        raise MonitorEvidenceError("checklist_exceeds_bound")
    pending = [row for row in checklist if row.status == "PENDING"]
    done = [row for row in checklist if row.status == "DONE"]
    if len(pending) + len(done) != len(checklist):
        raise MonitorEvidenceError("unknown_checklist_status")
    if (not _integer(reconciliation.get("canonical_pending_count"))
            or reconciliation["canonical_pending_count"] != len(pending)
            or reconciliation.get("canonical_total_count") != len(checklist)
            or reconciliation.get("canonical_done_count") != len(done)):
        raise MonitorEvidenceError("reconciliation_checklist_count_mismatch")
    records = reconciliation.get("items")
    if (not isinstance(records, list)
            or len(records) != len(pending)
            or reconciliation.get("reconciled_item_count") != len(records)
            or any(not isinstance(row, Mapping) for row in records)):
        raise MonitorEvidenceError("reconciliation_item_count_mismatch")
    canonical = {_id(row): row for row in pending}
    if len(canonical) != len(pending):
        raise MonitorEvidenceError("ambiguous_canonical_checklist_ids")
    by_id: dict[str, Mapping[str, Any]] = {}
    counted: Counter[str] = Counter()
    for record in records:
        item_id = record.get("item_id")
        if (not isinstance(item_id, str) or item_id in by_id or item_id not in canonical
                or record.get("checklist_line") != canonical[item_id].line):
            raise MonitorEvidenceError("reconciled_identity_unbound")
        state = record.get("state")
        if not isinstance(state, str) or state not in PRIORITY_STATES:
            raise MonitorEvidenceError("unsupported_reconciliation_state")
        by_id[item_id] = record
        counted[state] += 1
    if (set(by_id) != set(canonical)
            or dict(counted) != reconciliation.get("state_counts")):
        raise MonitorEvidenceError("reconciliation_state_counts_untrusted")
    previous_items, history, last_generated = _previous_map(previous, current=current)
    if last_generated is not None and current <= last_generated:
        raise MonitorEvidenceError("monitor_clock_did_not_advance")
    items: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for item_id, row in sorted(canonical.items(), key=lambda pair: pair[1].line):
        record = by_id[item_id]
        key = _key(row)
        state = record["state"]
        old = previous_items.get(key)
        if old is not None and (old.get("section") != row.section or old.get("task") != row.item):
            raise MonitorEvidenceError("monitor_task_key_reused_for_another_task")
        state_changed = old is not None and old["state"] != state
        if state_changed:
            changed.append({
                "task_key": key,
                "checklist_line": row.line,
                "from_state": old["state"],
                "to_state": state,
                "observed_at": current.isoformat(),
            })
        state_since = current if old is None or state_changed else _stamp(old["state_since"])
        first = current if old is None else _stamp(old["first_monitored_at"])
        state_age = max(0, int((current - state_since).total_seconds()))
        priority, reason, next_action = PRIORITY_STATES[state]
        urgent = state in {"BUILDER_PROVIDER_BLOCKED", "NEEDS_WIRING_OR_TEST_FIX"}
        stale_in_stage = state_age >= int(STALLED_AFTER.total_seconds())
        signals = ([reason] if urgent else [])
        if stale_in_stage and state not in {"FOUNDER_GATE", "REAL_WORLD_EVIDENCE_REQUIRED"}:
            signals.append("NO_OBSERVED_STAGE_CHANGE_24H")
        items.append({
            "task_key": key,
            "item_id": item_id,
            "line": row.line,
            "section": row.section,
            "task": row.item,
            "checklist_status": "PENDING",
            "state": state,
            "department": record.get("department"),
            "execution_class": record.get("execution_class"),
            "first_monitored_at": first.isoformat(),
            "state_since": state_since.isoformat(),
            "state_age_seconds": state_age,
            "monitored_cycles": (old["monitored_cycles"] + 1) if old else 1,
            "priority_order": priority,
            "attention_reason": reason,
            "attention_required": urgent or stale_in_stage or state in {
                "CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE", "REVIEW_PRIOR_ATTEMPT",
                "INDEPENDENT_REVIEW_REQUIRED_BEFORE_RETRY",
            },
            "signals": signals,
            "next_evidence_step": next_action,
            "attempt_memory_state": record.get("attempt_memory_state"),
            "attempt_memory_commit": record.get("attempt_memory_commit"),
            "attempt_memory_blocker": record.get("attempt_memory_blocker"),
            "verification_job_id": record.get("verification_job_id"),
            "verification_verdict": record.get("verification_verdict"),
            "plan_handoff_is_not_implementation": True,
            "commercial_outcome_verified": False,
            "execution_authority": "none",
        })
    done_keys = {_key(row) for row in done}
    for key, old in previous_items.items():
        if key in done_keys:
            changed.append({
                "task_key": key, "checklist_line": None,
                "from_state": old["state"], "to_state": "CHECKLIST_MARKED_DONE",
                "observed_at": current.isoformat(),
            })
        elif not any(item["task_key"] == key for item in items):
            # A missing task whose exact identity is not checked DONE is
            # a renamed/removed task, not a completed task.
            raise MonitorEvidenceError("previous_task_disappeared_without_done")
    history.extend(changed)
    history = history[-MAX_HISTORY:]
    by_state = dict(sorted(counted.items()))
    by_department = dict(sorted(Counter(
        str(item["department"] or "UNASSIGNED") for item in items
    ).items()))
    priority_queue = sorted(
        (row for row in items if row["attention_required"]),
        key=lambda row: (row["priority_order"], -row["state_age_seconds"], row["line"]),
    )
    return {
        "schema_version": SCHEMA,
        "status": "AVAILABLE", "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "source_reconciliation_at": source_time.isoformat(),
        "source_age_seconds": int(max(0, age.total_seconds())),
        "first_observation_only_not_historical_task_age": previous is None,
        "checklist": {
            "pending": len(pending), "checked_done": len(done),
            "total": len(checklist),
            "checked_done_is_not_independent_production_proof": True,
        },
        "tracked_pending_count": len(items),
        "state_counts": by_state,
        "department_counts": by_department,
        "attention_count": len(priority_queue),
        "provider_blocked_count": counted["BUILDER_PROVIDER_BLOCKED"],
        "code_complete_not_live_count": counted["CODE_COMPLETE_NOT_LIVE"],
        "founder_gate_count": counted["FOUNDER_GATE"],
        "new_state_transition_count": len(changed),
        "new_state_transitions": changed[:MAX_HISTORY],
        "recent_transitions": history,
        "top_attention": priority_queue[:25],
        "items": items,
        "monitoring_not_dispatch": True,
        "notifications_sent": False,
        "automatic_checklist_mutation_allowed": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }


def _read(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise MonitorEvidenceError("monitor_source_not_json_object")
    return data


def refresh_completion_task_monitor(
    repo_root: str | Path, *, now: datetime | None = None,
) -> dict[str, Any]:
    """One observational materialisation in the EXISTING department cycle.

    If a source or previous monitor is corrupt/stale, preserve the last valid
    snapshot rather than replacing it with invented progress. The founder API
    separately exposes snapshot staleness.
    """
    root = Path(repo_root).resolve()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise MonitorEvidenceError("monitor_clock_not_aware")
    canonical_path = root / CHECKLIST
    before = sha256(canonical_path.read_bytes()).hexdigest()
    checklist = parse_checklist(canonical_path)
    source = _read(root / RECONCILIATION)
    destination = root / OUTPUT
    prior = _read(destination) if destination.exists() else None
    packet = build_completion_task_monitor(
        checklist, source, previous=prior, now=current,
    )
    if sha256(canonical_path.read_bytes()).hexdigest() != before:
        raise MonitorEvidenceError("canonical_checklist_changed_during_monitor")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        dir=destination.parent, prefix=".task_monitor_", suffix=".pending",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(packet, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)
    return packet
