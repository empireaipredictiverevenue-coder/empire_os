"""Jev / typed-decision model evaluation planning for Empire.

This is provider-neutral strategy code. It does not call TypeSafe/Jev, create
credentials, send data externally, or activate any provider.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


CANDIDATE_TASKS = {
    "agent_routing",
    "model_routing",
    "reply_classification",
    "keyword_intent",
    "evidence_quality",
    "content_quality_gate",
    "research_triage",
    "coder_task_routing",
    "company_ops_triage",
    "policy_risk_triage",
}

RISK_CLASSES = {"low", "medium", "high", "consequential"}


def _text(v: Any) -> str:
    return str(v or "").strip()


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def review_jev_use_case(raw: Mapping[str, Any]) -> dict[str, Any]:
    task_key = _text(raw.get("task_key"))
    risk_class = _text(raw.get("risk_class")).lower()
    blockers = []

    if task_key not in CANDIDATE_TASKS:
        blockers.append("unsupported_task_key")
    if risk_class not in RISK_CLASSES:
        blockers.append("unsupported_risk_class")
    if not _text(raw.get("decision_schema_ref")):
        blockers.append("decision_schema_ref_required")
    if not _text(raw.get("baseline_ref")):
        blockers.append("baseline_ref_required")
    if not raw.get("evaluation_dataset_refs"):
        blockers.append("evaluation_dataset_refs_required")

    deterministic_possible = raw.get("deterministic_possible") is True
    open_ended_generation = raw.get("open_ended_generation") is True
    requires_exact_math = raw.get("requires_exact_math") is True
    consequential_authority = raw.get("consequential_authority") is True

    if open_ended_generation:
        blockers.append("open_ended_generation_not_jev_primary_use")
    if requires_exact_math:
        blockers.append("exact_math_should_use_quant_or_code")
    if deterministic_possible:
        blockers.append("compare_against_deterministic_baseline")
    if consequential_authority:
        blockers.append("jev_cannot_authorize_consequential_action")

    return {
        "schema_version": "jev_use_case_review.v1",
        "task_key": task_key or None,
        "risk_class": risk_class or None,
        "review_ready": (
            task_key in CANDIDATE_TASKS
            and risk_class in RISK_CLASSES
            and "decision_schema_ref_required" not in blockers
            and "baseline_ref_required" not in blockers
            and "evaluation_dataset_refs_required" not in blockers
        ),
        "warnings": blockers,
        "offline_eval_required": True,
        "shadow_required": True,
        "provider_activation": False,
        "external_data_send": False,
        "authority_expansion": False,
        "execution_authority": "none",
    }


def build_jev_eval_plan(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    use_cases = []
    seen = set()
    for raw in rows:
        item = review_jev_use_case(raw)
        key = item["task_key"]
        if key:
            if key in seen:
                raise ValueError("duplicate task_key")
            seen.add(key)
        use_cases.append(item)

    ready = [x["task_key"] for x in use_cases if x["review_ready"]]
    return {
        "schema_version": "jev_eval_plan.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "use_cases": use_cases,
        "ready_for_offline_eval": ready,
        "provider_activation": False,
        "credentials_required_now": False,
        "external_data_send": False,
    }


def compare_decision_providers(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Rank already-observed private eval results; does not run providers."""
    reviewed = []
    for raw in rows:
        provider_key = _text(raw.get("provider_key"))
        if not provider_key:
            raise ValueError("provider_key required")
        accuracy = _num(raw.get("accuracy"))
        brier = _num(raw.get("brier_score"))
        latency = _num(raw.get("p95_latency_ms"))
        cost = _num(raw.get("cost_per_million_input_tokens"))
        failure_rate = _num(raw.get("operational_failure_rate"))
        evidence_refs = [_text(x) for x in raw.get("evidence_refs", ()) if _text(x)]
        missing = []
        for name, value in (
            ("accuracy", accuracy),
            ("brier_score", brier),
            ("p95_latency_ms", latency),
            ("cost_per_million_input_tokens", cost),
            ("operational_failure_rate", failure_rate),
        ):
            if value is None:
                missing.append(name)
        if not evidence_refs:
            missing.append("evidence_refs")

        score = None
        if not missing:
            if not 0 <= accuracy <= 1:
                raise ValueError("accuracy must be between 0 and 1")
            if not 0 <= brier <= 1:
                raise ValueError("brier_score must be between 0 and 1")
            if latency < 0 or cost < 0 or not 0 <= failure_rate <= 1:
                raise ValueError("invalid provider eval metrics")
            calibration = 1 - brier
            reliability = 1 - failure_rate
            latency_eff = 1 / (1 + latency / 1000)
            cost_eff = 1 / (1 + cost / 1.0)
            score = (
                .35 * accuracy
                + .25 * calibration
                + .15 * reliability
                + .15 * latency_eff
                + .10 * cost_eff
            )

        reviewed.append({
            "provider_key": provider_key,
            "available": not missing,
            "score": round(score, 6) if score is not None else None,
            "missing": missing,
            "evidence_refs": evidence_refs,
        })

    reviewed.sort(
        key=lambda x: (
            x["available"],
            x["score"] if x["score"] is not None else -1,
            x["provider_key"],
        ),
        reverse=True,
    )
    for i, row in enumerate(reviewed, 1):
        row["rank"] = i

    return {
        "schema_version": "typed_decision_provider_comparison.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "providers": reviewed,
        "provider_activation": False,
        "recommendation_only": True,
    }
