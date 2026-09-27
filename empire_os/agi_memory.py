"""Memory routing contracts for Empire's agentic intelligence stack.

Memory retrieval is scoped and typed. This module does not persist memory or
grant tool/commercial authority.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


MEMORY_TYPES = (
    "working",
    "episodic",
    "semantic",
    "procedural",
    "outcome_conditioned",
)


TASK_MEMORY_DEFAULTS = {
    "research": ("working", "semantic", "episodic"),
    "planning": ("working", "semantic", "procedural", "episodic"),
    "commercial_decision": (
        "working", "semantic", "procedural", "episodic", "outcome_conditioned"
    ),
    "execution_review": (
        "working", "procedural", "episodic", "outcome_conditioned"
    ),
    "learning_review": (
        "episodic", "semantic", "procedural", "outcome_conditioned"
    ),
    "quantitative_research": (
        "working",
        "semantic",
        "procedural",
        "episodic",
        "outcome_conditioned",
    ),
    "coding": ("working", "semantic", "procedural", "episodic"),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_memory_query(
    *,
    task_type: str,
    task_id: str,
    entity_refs: Sequence[str] = (),
    topic_keys: Sequence[str] = (),
    max_items_per_type: int = 20,
    include_unverified_outcome_memory: bool = False,
) -> dict[str, Any]:
    task_type = _text(task_type).lower()
    task_id = _text(task_id)
    if not task_id:
        raise ValueError("task_id required")
    if task_type not in TASK_MEMORY_DEFAULTS:
        raise ValueError("unsupported task_type")
    if not 1 <= int(max_items_per_type) <= 100:
        raise ValueError("max_items_per_type must be between 1 and 100")

    memory_types = TASK_MEMORY_DEFAULTS[task_type]
    return {
        "schema_version": "agi_memory_query.v1",
        "task_id": task_id,
        "task_type": task_type,
        "memory_types": list(memory_types),
        "entity_refs": list(dict.fromkeys(_text(x) for x in entity_refs if _text(x))),
        "topic_keys": list(dict.fromkeys(_text(x) for x in topic_keys if _text(x))),
        "max_items_per_type": int(max_items_per_type),
        "filters": {
            "outcome_conditioned_requires_verified_outcome": True,
            "include_unverified_outcome_memory": bool(
                include_unverified_outcome_memory
            ),
        },
        "execution_authority": "none",
        "retrieval_only": True,
    }


def review_memory_item(item: Mapping[str, Any]) -> dict[str, Any]:
    memory_type = _text(item.get("memory_type"))
    ref = _text(item.get("ref"))
    evidence_refs = [
        _text(x) for x in item.get("evidence_refs", ()) if _text(x)
    ]
    blockers: list[str] = []

    if memory_type not in MEMORY_TYPES:
        blockers.append("unsupported_memory_type")
    if not ref:
        blockers.append("memory_ref_required")
    if not evidence_refs:
        blockers.append("evidence_refs_required")
    if memory_type == "outcome_conditioned":
        if item.get("verified_outcome") is not True:
            blockers.append("verified_outcome_required")
        if not _text(item.get("outcome_ref")):
            blockers.append("outcome_ref_required")
    if item.get("synthetic") is True and memory_type == "outcome_conditioned":
        blockers.append("synthetic_cannot_be_outcome_conditioned_memory")

    return {
        "memory_type": memory_type or None,
        "ref": ref or None,
        "evidence_refs": evidence_refs,
        "accepted_for_retrieval": not blockers,
        "blockers": blockers,
        "execution_authority": "none",
    }
