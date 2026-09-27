"""Shadow evidence collector for typed-decision evaluation.

Normalizes already-observed records from governed Empire subsystems into
review queues and frozen evaluation candidates. No provider calls, no live
routing, no commercial mutation, no publishing, no sends.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.typed_decision_commercial_observations import (
    buyer_corridor_record_to_observation,
    routing_task_to_observation,
)
from empire_os.typed_decision_observations import reply_record_to_observation
from empire_os.typed_decision_search_observations import (
    keyword_record_to_observation,
    source_quality_record_to_observation,
)


ADAPTERS = {
    "reply_classification": reply_record_to_observation,
    "keyword_intent": keyword_record_to_observation,
    "source_quality": source_quality_record_to_observation,
    "buyer_corridor_fit": buyer_corridor_record_to_observation,
    "agent_routing": routing_task_to_observation,
}


def collect_shadow_candidates(
    rows: Iterable[Mapping[str, Any]],
    *,
    task_key: str,
) -> dict[str, Any]:
    if task_key not in ADAPTERS:
        raise ValueError("unsupported task_key")
    adapter = ADAPTERS[task_key]

    ready = []
    blocked = []
    seen = set()

    for raw in rows:
        item = adapter(raw)
        case_id = item.get("case_id")
        if case_id:
            if case_id in seen:
                blocked.append({
                    "case_id": case_id,
                    "blockers": ["duplicate_case_id"],
                })
                continue
            seen.add(case_id)
        if item.get("ready") is True:
            ready.append(item)
        else:
            blocked.append(item)

    return {
        "schema_version": "typed_decision_shadow_candidate_batch.v1",
        "task_key": task_key,
        "ready_count": len(ready),
        "blocked_count": len(blocked),
        "ready": ready,
        "blocked": blocked,
        "provider_called": False,
        "production_routing": False,
        "execution_authority": "none",
    }


def build_label_review_queue(
    candidate_batch: Mapping[str, Any],
) -> dict[str, Any]:
    queue = []
    for item in candidate_batch.get("ready") or []:
        queue.append({
            "case_id": item.get("case_id"),
            "task_key": item.get("task_key"),
            "inputs": item.get("inputs") or {},
            "source_ref": item.get("source_ref"),
            "point_in_time_ref": item.get("point_in_time_ref"),
            "existing_observed_label": (
                item.get("observed_existing_intent")
                or item.get("observed_current_route")
                or None
            ),
            "review_state": "pending",
            "suggested_label": None,
            "reviewer_ref": None,
        })

    return {
        "schema_version": "typed_decision_label_review_queue.v1",
        "task_key": candidate_batch.get("task_key"),
        "queue_count": len(queue),
        "queue": queue,
        "auto_label_applied": False,
        "provider_called": False,
        "execution_authority": "none",
    }


def shadow_collection_summary(
    batches: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    by_task = {}
    total_ready = 0
    total_blocked = 0

    for batch in batches:
        task = str(batch.get("task_key") or "").strip()
        if not task:
            continue
        ready_count = int(batch.get("ready_count") or 0)
        blocked_count = int(batch.get("blocked_count") or 0)
        by_task[task] = {
            "ready_count": ready_count,
            "blocked_count": blocked_count,
        }
        total_ready += ready_count
        total_blocked += blocked_count

    return {
        "schema_version": "typed_decision_shadow_collection_summary.v1",
        "by_task": dict(sorted(by_task.items())),
        "total_ready": total_ready,
        "total_blocked": total_blocked,
        "real_labels_collected": 0,
        "provider_outputs_collected": 0,
        "production_routing": False,
        "execution_authority": "none",
    }
