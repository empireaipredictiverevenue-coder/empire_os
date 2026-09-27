"""AGI orchestration over EmpireOS specialist intelligence systems.

This is a governed general-intelligence coordination layer, not a claim of
human-level AGI. It composes specialist algorithm outputs, evidence gaps,
memory routing and verification requirements into an auditable next cognitive
workstream.

It does not execute tools, send outreach, move funds, alter commercial terms,
recognize revenue, mutate model weights, or persist private chain-of-thought.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from empire_os.agi_memory import build_memory_query


SCHEMA_VERSION = "empire.agi_orchestration.v1"

SPECIALISTS = (
    "predictive_revenue",
    "predictive_cloud",
    "future_trend",
    "quantum_optimization",
    "economic_memory",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _packet(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _status(packet: Mapping[str, Any]) -> str:
    value = _text(packet.get("status")).upper()
    if value:
        return value
    if packet:
        return "OBSERVED"
    return "UNAVAILABLE"


def _missing_from_packet(packet: Mapping[str, Any]) -> list[str]:
    fields = list(packet.get("missing_fields") or [])
    if packet.get("reason") and not fields:
        fields.append(f"reason:{_text(packet.get('reason'))}")
    return [str(field) for field in fields if str(field).strip()]


def _specialist_review(
    name: str,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    status = _status(packet)
    missing = _missing_from_packet(packet)
    review: dict[str, Any] = {
        "specialist": name,
        "status": status,
        "missing_fields": missing,
        "available": status in {"AVAILABLE", "OBSERVED", "CLEAR"},
    }

    if name == "predictive_revenue":
        review.update({
            "predicted_revenue_cents": packet.get(
                "predicted_revenue_cents"
            ),
            "expected_revenue_value_cents": packet.get(
                "expected_revenue_value_cents"
            ),
            "weakest_factor": packet.get("weakest_factor"),
            "actual_revenue": packet.get("actual_revenue"),
        })
    elif name == "predictive_cloud":
        constraints = packet.get("constraints")
        constraints = (
            constraints if isinstance(constraints, Mapping) else {}
        )
        forward = packet.get("forward_outlook")
        forward = forward if isinstance(forward, Mapping) else {}
        review.update({
            "cloud_operating_score": packet.get(
                "cloud_operating_score"
            ),
            "weakest_cloud_factor": packet.get(
                "weakest_cloud_factor"
            ),
            "constraint_state": constraints.get("state"),
            "forward_outlook_status": forward.get("status"),
            "actual_revenue": packet.get("actual_revenue"),
        })
    elif name == "future_trend":
        review.update({
            "direction": packet.get("direction"),
            "trend_confidence": packet.get("trend_confidence"),
            "future_opportunity_status": packet.get(
                "future_opportunity_status"
            ),
            "trend_opportunity_alignment": packet.get(
                "trend_opportunity_alignment"
            ),
            "causal_claim": packet.get("causal_claim"),
        })
    elif name == "quantum_optimization":
        review.update({
            "qaoa_ready": packet.get("qaoa_ready"),
            "model_type": packet.get("model_type"),
            "external_solver_called": packet.get(
                "external_solver_called"
            ),
            "quantum_advantage_claimed": packet.get(
                "quantum_advantage_claimed"
            ),
        })
    elif name == "economic_memory":
        review.update({
            "verified_outcomes_only": packet.get(
                "verified_outcomes_only_for_outcome_conditioned_memory"
            ),
            "outcome_conditioned_memory_count": packet.get(
                "outcome_conditioned_memory_count"
            ),
            "model_weight_mutation_authorized": packet.get(
                "model_weight_mutation_authorized"
            ),
        })

    return review


def _candidate_workstreams(
    *,
    reviews: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    evidence_gaps = [
        {
            "specialist": name,
            "missing_fields": row.get("missing_fields") or [],
        }
        for name, row in reviews.items()
        if row.get("status") == "UNAVAILABLE"
        or row.get("missing_fields")
    ]
    if evidence_gaps:
        candidates.append({
            "workstream": "close_evidence_gaps",
            "priority": 100,
            "reason": "one_or_more_specialists_lack_required_evidence",
            "evidence_gaps": evidence_gaps,
            "side_effect_class": "none",
        })

    cloud = reviews["predictive_cloud"]
    if cloud.get("constraint_state") == "BLOCKED":
        candidates.append({
            "workstream": "resolve_governance_or_capacity_constraints",
            "priority": 95,
            "reason": "predictive_cloud_constraints_blocked",
            "side_effect_class": "none",
        })

    quantum = reviews["quantum_optimization"]
    if (
        quantum.get("qaoa_ready") is True
        and quantum.get("external_solver_called") is not True
    ):
        candidates.append({
            "workstream": "benchmark_quantum_candidate",
            "priority": 70,
            "reason": "quantum_ready_problem_requires_classical_benchmark",
            "side_effect_class": "none",
        })

    trend = reviews["future_trend"]
    if (
        trend.get("status") in {"AVAILABLE", "OBSERVED"}
        and trend.get("future_opportunity_status") == "UNAVAILABLE"
    ):
        candidates.append({
            "workstream": "improve_forward_trend_evidence",
            "priority": 65,
            "reason": "trend_observed_but_forward_structure_incomplete",
            "side_effect_class": "none",
        })

    revenue = reviews["predictive_revenue"]
    if (
        revenue.get("status") == "AVAILABLE"
        and cloud.get("status") == "AVAILABLE"
        and cloud.get("constraint_state") in {None, "CLEAR", "UNKNOWN"}
    ):
        candidates.append({
            "workstream": "prepare_verified_next_best_action_review",
            "priority": 50,
            "reason": "revenue_and_cloud_intelligence_available",
            "side_effect_class": "none",
        })

    if not candidates:
        candidates.append({
            "workstream": "observe_and_refresh_world_state",
            "priority": 10,
            "reason": "no_higher_priority_cognitive_workstream_available",
            "side_effect_class": "none",
        })

    candidates.sort(
        key=lambda row: (-int(row["priority"]), row["workstream"])
    )
    return candidates


def build_agi_orchestration_packet(
    *,
    task_id: str,
    goal: str,
    world_state_ref: str,
    evidence_refs: Sequence[str],
    predictive_revenue: Mapping[str, Any] | None = None,
    predictive_cloud: Mapping[str, Any] | None = None,
    future_trend: Mapping[str, Any] | None = None,
    quantum_optimization: Mapping[str, Any] | None = None,
    economic_memory: Mapping[str, Any] | None = None,
    entity_refs: Sequence[str] = (),
    topic_keys: Sequence[str] = (),
) -> dict[str, Any]:
    """Build one auditable AGI orchestration packet."""
    task_id = _text(task_id)
    goal = _text(goal)
    world_state_ref = _text(world_state_ref)
    evidence = list(dict.fromkeys(
        _text(ref) for ref in evidence_refs if _text(ref)
    ))
    if not task_id:
        raise ValueError("task_id required")
    if not goal:
        raise ValueError("goal required")
    if not world_state_ref:
        raise ValueError("world_state_ref required")
    if not evidence:
        raise ValueError("evidence_refs required")

    packets = {
        "predictive_revenue": _packet(predictive_revenue),
        "predictive_cloud": _packet(predictive_cloud),
        "future_trend": _packet(future_trend),
        "quantum_optimization": _packet(quantum_optimization),
        "economic_memory": _packet(economic_memory),
    }
    reviews = {
        name: _specialist_review(name, packets[name])
        for name in SPECIALISTS
    }
    workstreams = _candidate_workstreams(reviews=reviews)

    memory_query = build_memory_query(
        task_type="planning",
        task_id=task_id,
        entity_refs=entity_refs,
        topic_keys=topic_keys,
        max_items_per_type=20,
    )

    unresolved_unknowns = [
        {
            "specialist": name,
            "missing_fields": row["missing_fields"],
        }
        for name, row in reviews.items()
        if row["status"] == "UNAVAILABLE"
        or row["missing_fields"]
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "architecture": "general_intelligence_orchestration_layer",
        "human_level_agi_claimed": False,
        "asi_claimed": False,
        "mode": "OBSERVE",
        "task_id": task_id,
        "goal": goal,
        "world_state_ref": world_state_ref,
        "evidence_refs": evidence,
        "specialist_reviews": reviews,
        "specialist_count": len(reviews),
        "unresolved_unknowns": unresolved_unknowns,
        "unknown_is_zero": False,
        "candidate_workstreams": workstreams,
        "recommended_cognitive_workstream": workstreams[0],
        "memory_query": memory_query,
        "verification_requirements": {
            "independent_verifier": True,
            "evidence_check": True,
            "freshness_check": True,
            "policy_check": True,
            "regression_eval": True,
            "verified_outcome_required_for_learning": True,
            "classical_reference_required_for_quantum_claim": True,
        },
        "private_chain_of_thought_persisted": False,
        "audit_summary_only": True,
        "model_weight_mutation": False,
        "policy_mutation": False,
        "permission_expansion": False,
        "external_action_performed": False,
        "commercial_authority": "none",
        "financial_authority": "none",
        "accounting_authority": "none",
        "execution_ready": False,
        "execution_authority": "none",
    }
