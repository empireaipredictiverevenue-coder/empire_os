#!/usr/bin/env python3
"""One-shot proof-to-memory admission. Never creates closure checkpoints.

Reads only local EmpireOS snapshots and loopback Founder API. It appends one
immutable attempt receipt for each independently observed existing feature.
No service restart, agent execution, database mutation, or checklist closure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.completion_runtime_evidence import TASKS, observe_existing_runtime
from empire_os.completion_task_memory import (
    AttemptMemoryError, load_attempt_memory, record_attempt, task_key,
)
from empire_os.master_execution_ledger import parse_checklist

SCHEMA = "empire.completion.observed-runtime-capture.v1"


def capture_existing_runtime(root: Path, *, apply: bool = False) -> dict:
    state = load_attempt_memory(root)
    if state.get("status") != "AVAILABLE":
        raise AttemptMemoryError("existing_cross_agent_task_memory_unavailable")
    rows = parse_checklist(root / "docs/MASTER_REMAINING_CHECKLIST.md")
    reviewed: list[dict] = []
    for name in TASKS:
        matching = [row for row in rows if row.item == name and row.status == "PENDING"]
        if len(matching) != 1:
            raise AttemptMemoryError("unique_pending_task_unavailable")
        row = matching[0]
        prior = state["latest_by_task"].get(task_key(row.section, row.item))
        if not isinstance(prior, dict):
            raise AttemptMemoryError("tested_feature_memory_not_found")
        if prior["attempt_state"] == "RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE":
            reviewed.append({
                "task": name, "line": row.line,
                "status": "ALREADY_CAPTURED_NO_REPLAY",
                "receipt_id": prior["attempt_id"],
                "closure_performed": False,
            })
            continue
        if (prior["attempt_state"] != "CODE_VERIFIED_NOT_LIVE"
                or not prior.get("commit")):
            raise AttemptMemoryError("code_not_verifiably_tested_or_held")
        observation = observe_existing_runtime(root, name)
        item = {
            "task": name,
            "line": row.line,
            "status": "VERIFIED_READ_ONLY",
            "feature_commit": prior["commit"],
            "prior_attempt_id": prior["attempt_id"],
            "runtime_sources": observation["source_hashes"],
            "runtime_observation": observation["metrics"],
            "closure_performed": False,
        }
        if apply:
            result = record_attempt(
                root, section=row.section, item=row.item,
                owner=prior["owner"],
                attempt_state="RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE",
                commit=prior["commit"],
                reopens=prior["attempt_id"],
                evidence_refs=[
                    f"commit:{prior['commit']}", *observation["evidence_refs"],
                ],
            )
            item["status"] = "CAPTURED" if result["created"] else "ALREADY_CAPTURED"
            item["receipt_id"] = result["attempt_id"]
        reviewed.append(item)
    return {
        "schema_version": SCHEMA,
        "status": "OBSERVATION_CAPTURED" if apply else "OBSERVATION_PREVIEW",
        "mode": "OBSERVE",
        "checklist_status_changes": 0,
        "automatic_closure": False,
        "new_agent_jobs": 0,
        "notifications_sent": False,
        "external_execution_performed": False,
        "execution_authority": "none",
        "items": reviewed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--apply", action="store_true",
                        help="Append immutable evidence receipts after recomputing real runtime proof")
    args = parser.parse_args()
    try:
        output = capture_existing_runtime(Path(args.repo_root).resolve(), apply=args.apply)
    except (OSError, ValueError, TimeoutError) as exc:
        print(json.dumps({
            "schema_version": SCHEMA, "status": "HELD",
            "reason": type(exc).__name__ + ": " + str(exc)[:160],
            "external_execution_performed": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
