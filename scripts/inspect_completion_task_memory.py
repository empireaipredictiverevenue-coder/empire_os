#!/usr/bin/env python3
"""Read shared completion-attempt memory without side effects."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.completion_task_memory import (
    load_attempt_memory, preflight_task, prior_completion_plan_handoffs,
    task_key,
)
from empire_os.master_execution_ledger import parse_checklist


def report(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    memory = load_attempt_memory(root)
    if memory["status"] != "AVAILABLE":
        return {
            "schema_version": "empire.completion-memory-inspection.v1",
            "status": "MEMORY_INVALID_HOLD",
            "reason": memory.get("reason"),
            "execution_authority": "none",
        }
    try:
        rows = parse_checklist(root / "docs/MASTER_REMAINING_CHECKLIST.md")
    except OSError:
        return {
            "schema_version": "empire.completion-memory-inspection.v1",
            "status": "CHECKLIST_UNAVAILABLE_HOLD",
            "execution_authority": "none",
        }

    plan_history = prior_completion_plan_handoffs(root)
    if plan_history["status"] != "AVAILABLE":
        return {
            "schema_version": "empire.completion-memory-inspection.v1",
            "status": "PLAN_HISTORY_INVALID_HOLD",
            "reason": plan_history.get("reason"),
            "execution_authority": "none",
        }
    pending = [row for row in rows if row.status == "PENDING"]
    previously_planned = sum(
        task_key(row.section, row.item) in plan_history["by_task"]
        for row in pending
    )
    matches = []
    for row in rows:
        if row.status != "PENDING":
            continue
        decision = preflight_task(
            memory, section=row.section, item=row.item,
        )
        if decision["decision"] not in ("HOLD", "REVIEW_NEW_EVIDENCE"):
            continue
        matches.append({
            "line": row.line,
            "section": row.section,
            "task": row.item,
            "task_key": decision["task_key"],
            "state": decision["reason"],
            "decision": "HOLD_NEW_EXECUTION",
            "last_attempt_id": decision["last_attempt_id"],
            "feature_commit": decision.get("commit"),
            "blocker": decision.get("blocker"),
            "evidence_refs": decision["evidence_refs"],
            "checklist_status": "PENDING",
        })
    return {
        "schema_version": "empire.completion-memory-inspection.v1",
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "canonical_pending_count": sum(row.status == "PENDING" for row in rows),
        "attempt_event_count": memory["event_count"],
        "remembered_task_count": memory["known_task_count"],
        "held_pending_task_count": len(matches),
        "historic_plan_handoff_packets": plan_history["historical_plan_packet_count"],
        "previous_plan_submitted_pending_count": previously_planned,
        "new_pending_tasks_without_any_plan_handoff": len(pending)-previously_planned,
        "plan_handoff_is_not_implementation": True,
        "items": matches,
        "external_execution_performed": False,
        "checklist_mutation_performed": False,
        "execution_authority": "none",
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root",default="/srv/empire_os")
    args=parser.parse_args()
    result=report(args.repo_root)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["status"]=="AVAILABLE" else 2


if __name__=="__main__":
    raise SystemExit(main())
