"""Evidence-gated Economic Memory for Astra and Predictive Cloud.

The memory snapshot records two distinct things:
1. Astra department work as episodic execution history.
2. Commercial outcome-conditioned memory only when Cortex has produced a
   verified, non-synthetic terminal label with explicit outcome provenance.

Department DONE status is never treated as a verified commercial outcome.
This module grants no execution, accounting, commercial or model-mutation
authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from empire_os.agi_memory import review_memory_item


EXECUTIVE_EVALUATION = Path(
    "runtime/astra/executive_evaluation_latest.json"
)
CORTEX_LEARNING = Path(
    "runtime/cortex_learning/cortex_learning_latest.json"
)
WORK_ROOT = Path("runtime/departments/work")
OUTPUT = Path("runtime/economic_memory/latest.json")

WORK_STATES = (
    "ready",
    "running",
    "review",
    "done",
    "blocked",
    "failed",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _department_work_rows(
    repo_root: Path,
    *,
    plan_id: str,
) -> list[dict[str, Any]]:
    if not plan_id:
        return []
    rows: list[dict[str, Any]] = []
    root = repo_root / WORK_ROOT
    for state in WORK_STATES:
        directory = root / state
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            payload = _read(path)
            if _clean(payload.get("plan_id")) != plan_id:
                continue
            payload["status"] = (
                _clean(payload.get("status")).upper()
                or state.upper()
            )
            rows.append(payload)
    rows.sort(
        key=lambda row: (
            _clean(row.get("step_id")),
            _clean(row.get("id")),
        )
    )
    return rows


def _department_episode(row: Mapping[str, Any]) -> dict[str, Any]:
    work_id = _clean(row.get("id"))
    refs = [
        _clean(value)
        for value in (
            row.get("result_evidence_refs")
            or row.get("evidence_refs")
            or []
        )
        if _clean(value)
    ]
    item = {
        "memory_type": "episodic",
        "ref": f"department_work:{work_id}" if work_id else "",
        "evidence_refs": refs,
        "verified_outcome": False,
        "synthetic": False,
    }
    review = review_memory_item(item)
    return {
        **item,
        "work_id": work_id or None,
        "plan_id": _clean(row.get("plan_id")) or None,
        "step_id": _clean(row.get("step_id")) or None,
        "goal_key": _clean(row.get("goal_key")) or None,
        "department_keys": list(row.get("department_keys") or []),
        "target_component": _clean(row.get("target_component")) or None,
        "action": _clean(row.get("action")) or None,
        "status": _clean(row.get("status")).upper() or None,
        "result": (
            dict(row.get("result") or {})
            if isinstance(row.get("result"), Mapping)
            else {}
        ),
        "error": _clean(row.get("error")) or None,
        "accepted_for_retrieval": review[
            "accepted_for_retrieval"
        ],
        "memory_blockers": review["blockers"],
        "department_done_is_verified_outcome": False,
        "execution_authority": "none",
    }


def _outcome_memory(
    packet: Mapping[str, Any],
) -> dict[str, Any] | None:
    label = packet.get("label")
    label = label if isinstance(label, Mapping) else {}
    if label.get("available") is not True:
        return None
    if label.get("synthetic") is True:
        return None
    if label.get("forecast_derived") is True:
        return None

    entity_id = _clean(packet.get("entity_id"))
    outcome_ref = _clean(label.get("outcome_ref"))
    refs = [
        _clean(value)
        for value in (label.get("evidence_refs") or [])
        if _clean(value)
    ]
    material = f"{entity_id}|{outcome_ref}".encode("utf-8")
    memory_ref = (
        "economic_outcome:"
        + sha256(material).hexdigest()[:24]
        if entity_id and outcome_ref
        else ""
    )
    item = {
        "memory_type": "outcome_conditioned",
        "ref": memory_ref,
        "evidence_refs": refs,
        "verified_outcome": True,
        "outcome_ref": outcome_ref,
        "synthetic": False,
    }
    review = review_memory_item(item)
    return {
        **item,
        "entity_id": entity_id or None,
        "company_name": _clean(packet.get("company_name")) or None,
        "label_kind": _clean(label.get("kind")) or None,
        "label_value": label.get("value"),
        "conversion_outcome": (
            _clean(label.get("conversion_outcome")) or None
        ),
        "verification": (
            dict(packet.get("verification") or {})
            if isinstance(packet.get("verification"), Mapping)
            else {}
        ),
        "calibration_feedback": (
            dict(packet.get("calibration_feedback") or {})
            if isinstance(
                packet.get("calibration_feedback"),
                Mapping,
            )
            else {}
        ),
        "accepted_for_retrieval": review[
            "accepted_for_retrieval"
        ],
        "memory_blockers": review["blockers"],
        "model_weight_mutation_authorized": False,
        "execution_authority": "none",
    }


def build_economic_memory_snapshot(
    *,
    executive_evaluation: Mapping[str, Any] | None,
    department_work: Sequence[Mapping[str, Any]],
    cortex_learning: Mapping[str, Any] | None,
) -> dict[str, Any]:
    evaluation = dict(executive_evaluation or {})
    cortex = dict(cortex_learning or {})

    episodes = [
        _department_episode(row)
        for row in department_work
        if isinstance(row, Mapping)
    ]
    outcome_candidates = [
        memory
        for packet in (cortex.get("packets") or [])
        if isinstance(packet, Mapping)
        for memory in [_outcome_memory(packet)]
        if memory is not None
    ]
    outcome_memories = [
        row
        for row in outcome_candidates
        if row["accepted_for_retrieval"] is True
    ]

    source_packet_count = int(cortex.get("packet_count") or 0)
    source_learning_ready_count = int(
        cortex.get("learning_ready_count") or 0
    )

    return {
        "schema_version": "empire.economic_memory.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": _clean(evaluation.get("plan_id")) or None,
        "plan_evaluation_state": (
            _clean(evaluation.get("evaluation_state")) or None
        ),
        "department_episode_count": len(episodes),
        "retrievable_department_episode_count": sum(
            row["accepted_for_retrieval"] is True
            for row in episodes
        ),
        "source_learning_packet_count": source_packet_count,
        "source_learning_ready_count": source_learning_ready_count,
        "learning_not_ready_count": max(
            0,
            source_packet_count - source_learning_ready_count,
        ),
        "outcome_memory_candidate_count": len(outcome_candidates),
        "outcome_conditioned_memory_count": len(outcome_memories),
        "rejected_outcome_memory_count": (
            len(outcome_candidates) - len(outcome_memories)
        ),
        "department_episodes": episodes,
        "outcome_conditioned_memories": outcome_memories,
        "department_done_is_verified_outcome": False,
        "verified_outcomes_only_for_outcome_conditioned_memory": True,
        "forecast_used_as_outcome": False,
        "synthetic_outcomes_allowed": False,
        "model_weight_mutation_authorized": False,
        "commercial_authority": "none",
        "accounting_authority": "none",
        "execution_authority": "none",
    }


def refresh_economic_memory_snapshot(
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    evaluation = _read(root / EXECUTIVE_EVALUATION)
    plan_id = _clean(evaluation.get("plan_id"))
    payload = build_economic_memory_snapshot(
        executive_evaluation=evaluation,
        department_work=_department_work_rows(
            root,
            plan_id=plan_id,
        ),
        cortex_learning=_read(root / CORTEX_LEARNING),
    )
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
