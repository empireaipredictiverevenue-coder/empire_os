"""Dispatch eligible Astra Executive plan steps into department work."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.department_adapter_registry import eligible_specialist_reopen_reasons
from empire_os.skill_exchange import recommend_work_item_skills
from empire_os.okf_adapter import list_private_research
from empire_os.astra_okf_auto_retrieval import auto_retrieve_for_astra


ASTRA_EXECUTIVE = Path("runtime/astra/executive_latest.json")
OUTPUT = Path("runtime/astra/department_dispatch_latest.json")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _goal_priority_map(snapshot: Mapping[str, Any]) -> dict[str, int]:
    """Bound Paperclip-style goal alignment using Empire's OWN goal priorities.

    A missing, invalid, disabled or duplicate goal keeps the legacy baseline.
    Never accept AI-inferred DICE factors or change work authority here.
    Priority 80..87 remains below existing completion-board class minimum 88.
    """
    goals = snapshot.get("goals")
    if not isinstance(goals, list):
        return {}
    result: dict[str, int] = {}
    duplicate: set[str] = set()
    for goal in goals:
        if not isinstance(goal, Mapping):
            continue
        key = goal.get("key")
        value = goal.get("priority")
        if not isinstance(key, str) or not key or goal.get("status") != "active":
            continue
        if key in result:
            duplicate.add(key)
            continue
        if type(value) is not int or not 0 <= value <= 100:
            continue
        result[key] = min(87, max(80, 80 + (value - 85) // 2))
    for key in duplicate:
        result.pop(key, None)
    return result


def dispatch_executive_plan(
    repo_root: str | Path, *, okf_bundle_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    snapshot = _read(root / ASTRA_EXECUTIVE)
    plan_id = str(snapshot.get("plan_id") or "").strip()
    goal_priorities = _goal_priority_map(snapshot)
    queue = DepartmentWorkQueue(root)

    # Advisory-only: the OKF catalogue is inspected separately from Astra's
    # existing plan/queue path. It cannot modify step eligibility,
    # existing approvals, job lists or DepartmentWorkQueue inputs.
    okf_advisory = None
    if okf_bundle_path is not None:
        try:
            allowed_root = (root / 'runtime/knowledge/okf_private').resolve()
            requested = Path(okf_bundle_path).resolve()
            if requested.parent != allowed_root or not requested.name.startswith('run-'):
                raise ValueError('okf_bundle_outside_private_runtime')
            bundle = list_private_research(
                requested, now=datetime.now(timezone.utc), max_results=10,
            )
            okf_advisory = {
                **bundle, 'mode': 'OBSERVE', 'research_only': True,
                'queue_mutated': False, 'execution_authority': 'none',
            }
        except Exception as exc:
            okf_advisory = {
                'status': 'unavailable', 'reason': type(exc).__name__,
                'research_only': True, 'queue_mutated': False,
                'execution_authority': 'none',
            }

    queued = 0
    existing = 0
    authority_blocked = 0
    unowned = 0
    specialist_retry_held_count = 0
    goal_priority_applied_count = 0
    items: list[dict[str, Any]] = []
    admitted_steps: list[Mapping[str, Any]] = []

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

            priority = goal_priorities.get(str(step.get("goal_key") or ""), 80)
            work, created = queue.enqueue_step(
                plan_id=plan_id,
                step=step,
                priority=priority,
                reopen_blocked_reasons=eligible_specialist_reopen_reasons(
                    root, str(step.get("target_component") or "").strip(),
                ),
            )
            queued += int(created)
            existing += int(not created)
            goal_priority_applied_count += int(created and priority > 80)
            retry_held = (
                work.status.value == "BLOCKED"
                and work.error == "specialist_adapter_required"
                and not eligible_specialist_reopen_reasons(root, work.target_component)
            )
            specialist_retry_held_count += int(retry_held)
            admitted_steps.append(step)
            items.append({
                "work_id": work.id,
                "effective_priority": work.priority,
                "specialist_retry_held": retry_held,
                "step_id": work.step_id,
                "departments": list(work.department_keys),
                "target_component": work.target_component,
                "action": work.action,
                "created": created,
                "skill_advice": recommend_work_item_skills({
                    "id": work.id, "department_keys": list(work.department_keys),
                    "target_component": work.target_component,
                }),
            })

    # Automatic research selection happens AFTER all queue decisions.
    # It cannot modify a step, work item, existing authority or dispatch.
    if okf_bundle_path is None and admitted_steps:
        auto_advisory = auto_retrieve_for_astra(root, admitted_steps)
        if auto_advisory["status"] != "no_relevant_company_bound_task":
            okf_advisory = auto_advisory

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
        "goal_priority_applied_to_new_work_count": goal_priority_applied_count,
        "specialist_retry_held_count": specialist_retry_held_count,
        "queue_counts": queue.counts(),
        "items": items,
        "okf_research_advisory": okf_advisory,
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
