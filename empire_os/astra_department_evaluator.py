"""Evaluate Astra department work against the executive plan."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.department_work_queue import DepartmentWorkQueue


ASTRA_EXECUTIVE = Path("runtime/astra/executive_latest.json")
OUTPUT = Path("runtime/astra/executive_evaluation_latest.json")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def evaluate_executive_plan(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    executive = _read(root / ASTRA_EXECUTIVE)
    plan_id = str(executive.get("plan_id") or "").strip()
    queue = DepartmentWorkQueue(root)

    work_by_step: dict[str, Mapping[str, Any]] = {}
    evidence_refs: list[str] = []
    statuses: Counter[str] = Counter()

    for directory_name, directory in (
        ("READY", queue.ready),
        ("RUNNING", queue.running),
        ("REVIEW", queue.review),
        ("DONE", queue.done),
        ("BLOCKED", queue.blocked),
        ("FAILED", queue.failed),
    ):
        for path in directory.glob("*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(row.get("plan_id") or "") != plan_id:
                continue
            step_id = str(row.get("step_id") or "").strip()
            if step_id:
                work_by_step[step_id] = row
            statuses[directory_name] += 1
            evidence_refs.extend(
                str(ref)
                for ref in (row.get("result_evidence_refs") or [])
                if str(ref).strip()
            )

    eligible_steps = [
        row for row in (executive.get("plan") or [])
        if isinstance(row, Mapping)
        and row.get("auto_dispatch_eligible") is True
        and row.get("founder_gate_required") is not True
    ]
    undispatched = [
        str(row.get("step_id") or "")
        for row in eligible_steps
        if str(row.get("step_id") or "") not in work_by_step
    ]

    if not plan_id:
        state = "NO_PLAN"
    elif undispatched:
        state = "NOT_FULLY_DISPATCHED"
    elif statuses["FAILED"]:
        state = "FAILED"
    elif statuses["BLOCKED"]:
        state = "BLOCKED"
    elif statuses["READY"] or statuses["RUNNING"] or statuses["REVIEW"]:
        state = "IN_PROGRESS"
    elif eligible_steps and statuses["DONE"] == len(eligible_steps):
        state = "INTERNAL_WORK_COMPLETE"
    else:
        state = "NO_ELIGIBLE_WORK"

    payload = {
        "schema_version": "empire.astra.executive_evaluation.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": plan_id or None,
        "evaluation_state": state,
        "eligible_step_count": len(eligible_steps),
        "undispatched_step_ids": undispatched,
        "status_counts": dict(sorted(statuses.items())),
        "result_evidence_refs": list(dict.fromkeys(evidence_refs)),
        "plan_success_claimed": False,
        "success_requires_observed_evidence": True,
        "external_execution_performed": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }

    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
