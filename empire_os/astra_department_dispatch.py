"""Dispatch eligible Astra Executive plan steps into department work."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.department_work_queue import DepartmentWorkQueue


ASTRA_EXECUTIVE = Path("runtime/astra/executive_latest.json")
OUTPUT = Path("runtime/astra/department_dispatch_latest.json")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def dispatch_executive_plan(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    snapshot = _read(root / ASTRA_EXECUTIVE)
    plan_id = str(snapshot.get("plan_id") or "").strip()
    queue = DepartmentWorkQueue(root)

    queued = 0
    existing = 0
    authority_blocked = 0
    unowned = 0
    items: list[dict[str, Any]] = []

    if plan_id:
        for step in snapshot.get("plan") or []:
            if not isinstance(step, Mapping):
                continue
            eligible = step.get("auto_dispatch_eligible") is True
            founder_gate = step.get("founder_gate_required") is True
            authority = str(step.get("authority") or "").strip()
            departments = [
                str(value).strip()
                for value in (step.get("department_keys") or [])
                if str(value).strip()
            ]

            if (
                not eligible
                or founder_gate
                or authority not in {"observe", "internal_write"}
            ):
                authority_blocked += 1
                continue
            if not departments:
                unowned += 1
                continue

            priority = 80
            work, created = queue.enqueue_step(
                plan_id=plan_id,
                step=step,
                priority=priority,
                reopen_blocked_reasons=(
                    "specialist_adapter_required",
                ),
            )
            queued += int(created)
            existing += int(not created)
            items.append({
                "work_id": work.id,
                "step_id": work.step_id,
                "departments": list(work.department_keys),
                "target_component": work.target_component,
                "action": work.action,
                "created": created,
            })

    payload = {
        "schema_version": "empire.astra.department_dispatch.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": plan_id or None,
        "plan_available": bool(plan_id),
        "queued_count": queued,
        "existing_count": existing,
        "authority_blocked_count": authority_blocked,
        "unowned_count": unowned,
        "queue_counts": queue.counts(),
        "items": items,
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
