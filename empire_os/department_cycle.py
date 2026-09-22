"""Run one bounded department heartbeat and evaluate the Astra plan."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from empire_os.astra_department_evaluator import evaluate_executive_plan
from empire_os.department_worker import run_department_worker


OUTPUT = Path("runtime/astra/department_cycle_latest.json")


def run_department_cycle(
    repo_root: str | Path,
    *,
    max_items: int = 4,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    worker = run_department_worker(
        root,
        max_items=max_items,
        timeout_seconds=timeout_seconds,
    )
    evaluation = evaluate_executive_plan(root)
    payload = {
        "schema_version": "empire.department_cycle.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "worker": {
            "ok": worker.get("ok"),
            "processed_count": worker.get("processed_count"),
            "done_count": worker.get("done_count"),
            "blocked_count": worker.get("blocked_count"),
            "failed_count": worker.get("failed_count"),
        },
        "evaluation": {
            "plan_id": evaluation.get("plan_id"),
            "evaluation_state": evaluation.get("evaluation_state"),
            "eligible_step_count": evaluation.get(
                "eligible_step_count"
            ),
            "status_counts": evaluation.get("status_counts") or {},
            "undispatched_step_ids": evaluation.get(
                "undispatched_step_ids"
            ) or [],
            "result_evidence_refs": evaluation.get(
                "result_evidence_refs"
            ) or [],
        },
        "external_execution_performed": False,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
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
