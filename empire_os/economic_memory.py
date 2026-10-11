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
from empire_os.decision_identity import (
    review_decision_identity,
)


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


def _canonical_causal_outcome_refs(values: Any) -> list[str]:
    rows = values if isinstance(values, (list, tuple, set)) else []
    return list(dict.fromkeys(
        ref for value in rows
        if (ref := _clean(value)).startswith("canonical:commercial_outcomes:")
        and ref.removeprefix("canonical:commercial_outcomes:").strip()
    ))


def _department_episode(
    row: Mapping[str, Any],
) -> dict[str, Any]:
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

    result = (
        dict(row.get("result") or {})
        if isinstance(
            row.get("result"),
            Mapping,
        )
        else {}
    )

    raw_identity = result.get(
        "decision_identity"
    )

    decision_identity = None
    decision_identity_blockers: list[str] = []

    if isinstance(
        raw_identity,
        Mapping,
    ):
        review = review_decision_identity(
            raw_identity
        )

        decision_identity_blockers = list(
            review.get("blockers")
            or []
        )

        if review.get("valid") is True:
            decision_identity = dict(
                review.get("identity")
                or {}
            )

    item = {
        "memory_type": "episodic",
        "ref":
            f"department_work:{work_id}"
            if work_id
            else "",
        "evidence_refs": refs,
        "verified_outcome": False,
        "synthetic": False,
    }

    review = review_memory_item(item)

    return {
        **item,
        "work_id":
            work_id or None,
        "tenant_id": row.get("tenant_id"),
        "opportunity_key": (row.get("commercial_decision_provenance") or {}).get("opportunity_key"),
        "plan_id":
            _clean(
                row.get("plan_id")
            )
            or None,
        "step_id":
            _clean(
                row.get("step_id")
            )
            or None,
        "goal_key":
            _clean(
                row.get("goal_key")
            )
            or None,
        "department_keys":
            list(
                row.get(
                    "department_keys"
                )
                or []
            ),
        "target_component":
            _clean(
                row.get(
                    "target_component"
                )
            )
            or None,
        "action":
            _clean(
                row.get("action")
            )
            or None,
        "status":
            _clean(
                row.get("status")
            ).upper()
            or None,
        "result":
            result,
        "causal_outcome_refs":
            _canonical_causal_outcome_refs(
                result.get(
                    "causal_outcome_refs"
                )
            ),
        "decision_identity":
            decision_identity,
        "decision_identity_valid":
            decision_identity is not None,
        "decision_identity_blockers":
            decision_identity_blockers,
        "error":
            _clean(
                row.get("error")
            )
            or None,
        "accepted_for_retrieval":
            review[
                "accepted_for_retrieval"
            ],
        "memory_blockers":
            review["blockers"],
        "department_done_is_verified_outcome":
            False,
        "execution_authority":
            "none",
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
    if label.get("value") == 1 and not all((packet.get("verification") or {}).get(key) is True
            for key in ("payment_verified", "fulfilment_verified", "recognized_revenue")):
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
        "tenant_id": packet.get("tenant_id"),
        "learning_lineage": dict(packet.get("learning_lineage") or {}),
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


def _plan_outcome_attributions(
    episodes: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_ref = {
        _clean(row.get("outcome_ref")): row
        for row in outcomes
        if _clean(row.get("outcome_ref"))
    }
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for episode in episodes:
        if _clean(episode.get("status")).upper() != "DONE":
            continue
        work_id = _clean(episode.get("work_id"))
        for outcome_ref in _canonical_causal_outcome_refs(
            episode.get("causal_outcome_refs")
        ):
            outcome = by_ref.get(outcome_ref)
            if outcome is None:
                continue
            lineage = outcome.get("learning_lineage") or {}
            if outcome.get("tenant_id") is not None and episode.get("tenant_id") != outcome["tenant_id"]:
                continue
            identity = episode.get("decision_identity") or {}
            if lineage.get("causal_lineage") is not None and lineage.get("opportunity_key") != episode.get("opportunity_key"):
                continue
            if any(lineage.get(key) is not None and lineage[key] != identity.get(key)
                   for key in ("decision_ref", "prediction_ref", "execution_ref")):
                continue
            key = (work_id, outcome_ref)
            if key in seen:
                continue
            seen.add(key)
            evidence_refs = list(dict.fromkeys([
                *[
                    _clean(value)
                    for value in (episode.get("evidence_refs") or [])
                    if _clean(value)
                ],
                *[
                    _clean(value)
                    for value in (outcome.get("evidence_refs") or [])
                    if _clean(value)
                ],
                outcome_ref,
            ]))
            rows.append({
                "plan_id": _clean(episode.get("plan_id")) or None,
                "step_id": _clean(episode.get("step_id")) or None,
                "work_id": work_id or None,
                "goal_key": _clean(episode.get("goal_key")) or None,
                "target_component": _clean(episode.get("target_component")) or None,
                "action": _clean(episode.get("action")) or None,
                "outcome_ref": outcome_ref,
                "tenant_id": outcome.get("tenant_id"),
                "opportunity_key": lineage.get("opportunity_key"),
                "entity_id": _clean(outcome.get("entity_id")) or None,
                "label_kind": _clean(outcome.get("label_kind")) or None,
                "label_value": outcome.get("label_value"),
                "conversion_outcome": _clean(outcome.get("conversion_outcome")) or None,
                "attribution_basis": "explicit_causal_outcome_ref",
                "causal_attribution_claimed": True,
                "evidence_refs": evidence_refs,
                "synthetic": False,
                "execution_authority": "none",
            })
    rows.sort(key=lambda row: (
        _clean(row.get("plan_id")),
        _clean(row.get("step_id")),
        _clean(row.get("work_id")),
        _clean(row.get("outcome_ref")),
    ))
    return rows



def _decision_outcome_attributions(
    episodes: Sequence[Mapping[str, Any]],
    plan_attributions: Sequence[
        Mapping[str, Any]
    ],
) -> list[dict[str, Any]]:
    episodes_by_work = {
        _clean(
            row.get("work_id")
        ): row
        for row in episodes
        if _clean(
            row.get("work_id")
        )
    }

    rows: list[dict[str, Any]] = []

    for attribution in plan_attributions:
        work_id = _clean(
            attribution.get("work_id")
        )

        episode = episodes_by_work.get(
            work_id
        )

        if episode is None:
            continue

        identity = episode.get(
            "decision_identity"
        )

        if not isinstance(
            identity,
            Mapping,
        ):
            continue

        if (
            identity.get(
                "causal_eligible"
            )
            is not True
        ):
            continue

        expected_execution_ref = (
            f"department_work:{work_id}"
        )

        if (
            _clean(
                identity.get(
                    "execution_ref"
                )
            )
            != expected_execution_ref
        ):
            continue

        outcome_ref = _clean(
            attribution.get(
                "outcome_ref"
            )
        )

        if not outcome_ref:
            continue

        evidence_refs = list(
            dict.fromkeys(
                value
                for value in (
                    *(
                        attribution.get(
                            "evidence_refs"
                        )
                        or []
                    ),
                    _clean(
                        identity.get(
                            "source_ref"
                        )
                    ),
                    _clean(
                        identity.get(
                            "selection_authority_ref"
                        )
                    ),
                    expected_execution_ref,
                    _clean(
                        identity.get(
                            "prediction_ref"
                        )
                    ),
                    outcome_ref,
                )
                if _clean(value)
            )
        )

        rows.append({
            "plan_id":
                attribution.get(
                    "plan_id"
                ),
            "step_id":
                attribution.get(
                    "step_id"
                ),
            "work_id":
                work_id,
            "tenant_id": attribution.get("tenant_id"),
            "opportunity_key": attribution.get("opportunity_key"),
            "decision_ref":
                _clean(
                    identity.get(
                        "decision_ref"
                    )
                ),
            "decision_kind":
                _clean(
                    identity.get(
                        "decision_kind"
                    )
                ),
            "task_key":
                _clean(
                    identity.get(
                        "task_key"
                    )
                ),
            "state_ref":
                _clean(
                    identity.get(
                        "state_ref"
                    )
                ),
            "provider_key":
                _clean(
                    identity.get(
                        "provider_key"
                    )
                )
                or None,
            "model_key":
                _clean(
                    identity.get(
                        "model_key"
                    )
                )
                or None,
            "candidate_id":
                _clean(
                    identity.get(
                        "candidate_id"
                    )
                )
                or None,
            "prediction_ref":
                _clean(
                    identity.get(
                        "prediction_ref"
                    )
                )
                or None,
            "selection_authority_ref":
                _clean(
                    identity.get(
                        "selection_authority_ref"
                    )
                ),
            "execution_ref":
                expected_execution_ref,
            "outcome_ref":
                outcome_ref,
            "entity_id":
                attribution.get(
                    "entity_id"
                ),
            "label_kind":
                attribution.get(
                    "label_kind"
                ),
            "label_value":
                attribution.get(
                    "label_value"
                ),
            "conversion_outcome":
                attribution.get(
                    "conversion_outcome"
                ),
            "attribution_basis":
                (
                    "executed_decision_plus_"
                    "explicit_causal_outcome_ref"
                ),
            "decision_execution_verified":
                True,
            "shadow_decision":
                False,
            "causal_attribution_claimed":
                True,
            "evidence_refs":
                evidence_refs,
            "synthetic":
                False,
            "model_weight_mutation_authorized":
                False,
            "execution_authority":
                "none",
        })

    rows.sort(
        key=lambda row: (
            _clean(
                row.get("plan_id")
            ),
            _clean(
                row.get("step_id")
            ),
            _clean(
                row.get("work_id")
            ),
            _clean(
                row.get("decision_ref")
            ),
            _clean(
                row.get("outcome_ref")
            ),
        )
    )

    return rows


def build_economic_memory_snapshot(
    *,
    executive_evaluation: Mapping[str, Any] | None,
    department_work: Sequence[Mapping[str, Any]],
    cortex_learning: Mapping[str, Any] | None,
    tenant_id: str | None = None,
    verified_feedback=(),
    calibration_reviews=(),
    as_of=None,
) -> dict[str, Any]:
    evaluation = dict(executive_evaluation or {})
    cortex = dict(cortex_learning or {})
    from empire_os.outcome_feedback import validate_verified_feedback
    from empire_os.predictive_calibration import review_commercial_prediction
    feedback_rows = list(verified_feedback)
    reviews = list(calibration_reviews)
    for feedback in feedback_rows:
        validate_verified_feedback(feedback, tenant_id=tenant_id, as_of=as_of)
    validated_packets = [row["cortex_packet"] for row in feedback_rows]
    for review in reviews:
        replayed = review_commercial_prediction(prediction=review["prediction"], feedback=review["feedback"],
                                               tenant_id=tenant_id, as_of=as_of)
        if replayed != review:
            raise ValueError("calibration replay mismatch")

    episodes = [
        _department_episode(row)
        for row in department_work
        if isinstance(row, Mapping)
        and (tenant_id is None or row.get("tenant_id") == tenant_id)
    ]
    # Resolve explicit outcome-owned execution links after the fact, without
    # modifying the immutable persisted selection/completion snapshot.
    from empire_os.decision_identity import causal_lineage_from_work
    raw_work = {row.get("id"): row for row in department_work if isinstance(row, Mapping)}
    for episode in episodes:
        work = raw_work.get(episode["work_id"])
        for feedback in feedback_rows:
            causal = feedback.get("causal_lineage")
            if not causal or causal.get("causal_eligible") is not True or causal.get("execution_ref") != episode["ref"]:
                continue
            try:
                expected = causal_lineage_from_work(work, tenant_id=tenant_id,
                    opportunity_key=causal["opportunity_key"], opportunity_id=causal["opportunity_id"])
            except ValueError:
                continue
            if expected == causal:
                episode["causal_outcome_refs"] = list(dict.fromkeys([
                    *episode["causal_outcome_refs"], feedback["outcome_ref"]]))
    outcome_candidates = [
        memory
        for packet in (cortex.get("packets") or [])
        if isinstance(packet, Mapping)
        and (tenant_id is None or packet.get("tenant_id") == tenant_id)
        and (tenant_id is None or packet in validated_packets)
        for memory in [_outcome_memory(packet)]
        if memory is not None
    ]
    outcome_memories = [
        row
        for row in outcome_candidates
        if row["accepted_for_retrieval"] is True
    ]
    plan_outcome_attributions = _plan_outcome_attributions(
        episodes, outcome_memories
    )

    decision_outcome_attributions = (
        _decision_outcome_attributions(
            episodes,
            plan_outcome_attributions,
        )
    )

    attributed_outcome_refs = {
        row["outcome_ref"] for row in plan_outcome_attributions
    }

    source_packet_count = int(cortex.get("packet_count") or 0)
    source_learning_ready_count = int(
        cortex.get("learning_ready_count") or 0
    )

    return {
        "schema_version": "empire.economic_memory.v1",
        "mode": "OBSERVE",
        "tenant_id": tenant_id,
        "verified_learning_feedback": feedback_rows,
        "calibration_evidence": reviews,
        "calibration_evidence_count": len(reviews),
        "learning_stage": "SHADOW_LEARNING",
        "promoted_learning": False,
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
        "plan_outcome_attribution_count": len(plan_outcome_attributions),
        "plan_outcome_attributions": plan_outcome_attributions,
        "decision_outcome_attribution_count": len(
            decision_outcome_attributions
        ),
        "decision_outcome_attributions": (
            decision_outcome_attributions
        ),
        "unattributed_verified_outcome_count": sum(
            _clean(row.get("outcome_ref")) not in attributed_outcome_refs
            for row in outcome_memories
        ),
        "causal_attribution_requires_explicit_outcome_ref": True,
        "decision_causal_attribution_requires_execution": True,
        "shadow_decisions_receive_causal_credit": False,
        "decision_identity_grants_execution_authority": False,
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
    *,
    repository=None,
    fulfilment_order_ids=(),
    tenant_id: str | None = None,
    original_predictions: Mapping[str, Any] | None = None,
    as_of=None,
    shadow_calibration: bool = False,
) -> dict[str, Any]:
    """Refresh canonical memory; optionally produce a separate shadow benchmark.

    The benchmark is opt-in and has no execution/model-weight authority.
    """
    if type(shadow_calibration) is not bool:
        raise ValueError("shadow_calibration must be boolean")
    root = Path(repo_root).resolve()
    evaluation = _read(root / EXECUTIVE_EVALUATION)
    plan_id = _clean(evaluation.get("plan_id"))
    work_rows = _department_work_rows(root, plan_id=plan_id)
    cortex = _read(root / CORTEX_LEARNING)
    feedback_rows = []
    reviews = []
    if repository is not None:
        if not tenant_id or as_of is None:
            raise ValueError("explicit tenant and as_of required for canonical outcome refresh")
        order_ids = sorted(set(fulfilment_order_ids))
        if len(order_ids) > 100:
            raise ValueError("canonical outcome refresh limited to 100 explicit orders")
        from empire_os.department_work_queue import DepartmentWorkQueue
        from empire_os.predictive_calibration import review_commercial_prediction
        for order_id in order_ids:
            feedback = repository.verified_outcome_feedback(order_id, tenant_id=tenant_id,
                repo_root=root, as_of=as_of)
            feedback_rows.append(feedback)
            causal = feedback.get("causal_lineage")
            if causal and causal.get("task_key"):
                work = DepartmentWorkQueue.read_completed_work(root, causal["task_key"])
                work_rows = [row for row in work_rows if row.get("id") != work["id"]] + [work]
            prediction = (original_predictions or {}).get(feedback.get("prediction_ref"))
            if prediction is not None:
                reviews.append(review_commercial_prediction(prediction=prediction, feedback=feedback,
                    tenant_id=tenant_id, as_of=as_of))
        cortex = {"packets": [row["cortex_packet"] for row in feedback_rows]}
    elif fulfilment_order_ids or original_predictions:
        raise ValueError("canonical read repository required for outcome runtime handoff")
    payload = build_economic_memory_snapshot(
        executive_evaluation=evaluation,
        department_work=work_rows,
        cortex_learning=cortex,
        tenant_id=tenant_id,
        verified_feedback=feedback_rows,
        calibration_reviews=reviews,
        as_of=as_of,
    )
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    if shadow_calibration:
        from empire_os.lead_shadow_calibration_benchmark import (
            refresh_shadow_calibration_snapshot,
        )
        refresh_shadow_calibration_snapshot(
            root, tenant_id=tenant_id,
            as_of=as_of if as_of is not None else datetime.now(timezone.utc),
            memory=payload,
        )
    return payload
