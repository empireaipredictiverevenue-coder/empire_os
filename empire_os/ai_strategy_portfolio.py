"""AI capability portfolio analysis for Empire Strategy.

This module manages strategic AI capability choices without activating
providers, promoting models, changing secrets, or expanding execution authority.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.strategy_operating_system import review_ai_capability
from empire_os.quant_brain import portfolio_concentration


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded(value: Any, name: str) -> float | None:
    x = _number(value)
    if x is None:
        return None
    if not 0 <= x <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


def review_ai_portfolio_item(raw: Mapping[str, Any]) -> dict[str, Any]:
    strategic = review_ai_capability(raw)
    blockers = list(strategic["blockers"])

    capability_key = _text(raw.get("capability_key"))
    owner = _text(raw.get("owner"))
    task_class = _text(raw.get("task_class"))
    current_provider = _text(raw.get("current_provider")) or None
    current_model = _text(raw.get("current_model")) or None
    evaluation_ref = _text(raw.get("evaluation_ref")) or None
    cost_per_1k_tasks_cents = _number(raw.get("cost_per_1k_tasks_cents"))
    observed_quality = _bounded(raw.get("observed_quality"), "observed_quality")
    switching_cost = _bounded(raw.get("switching_cost"), "switching_cost")
    dependency_weight = _bounded(raw.get("dependency_weight"), "dependency_weight")

    if not owner:
        blockers.append("owner_required")
    if not task_class:
        blockers.append("task_class_required")
    if cost_per_1k_tasks_cents is not None and cost_per_1k_tasks_cents < 0:
        blockers.append("cost_per_1k_tasks_cents_must_be_nonnegative")
    if strategic["review_ready"] and not evaluation_ref:
        blockers.append("evaluation_ref_required_for_portfolio_decision")
    if current_provider and dependency_weight is None:
        blockers.append("dependency_weight_required_when_provider_present")

    readiness = {
        "evaluation_present": evaluation_ref is not None,
        "observed_quality_present": observed_quality is not None,
        "cost_present": cost_per_1k_tasks_cents is not None,
        "switching_cost_present": switching_cost is not None,
    }

    return {
        "schema_version": "ai_portfolio_item.v1",
        "capability_key": capability_key or None,
        "owner": owner or None,
        "task_class": task_class or None,
        "strategy_review": strategic,
        "current_provider": current_provider,
        "current_model": current_model,
        "evaluation_ref": evaluation_ref,
        "observed_quality": observed_quality,
        "cost_per_1k_tasks_cents": cost_per_1k_tasks_cents,
        "switching_cost": switching_cost,
        "dependency_weight": dependency_weight,
        "portfolio_review_ready": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "readiness": readiness,
        "provider_activation": False,
        "model_promotion": False,
        "secret_mutation": False,
        "execution_authority": "none",
    }


def build_ai_capability_portfolio(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = []
    seen: set[str] = set()
    provider_weights: dict[str, float] = {}
    build_modes: dict[str, int] = {
        "BUILD": 0,
        "BUY": 0,
        "OPEN_SOURCE": 0,
        "HYBRID": 0,
        "WATCH": 0,
        "UNDECIDED": 0,
    }

    for raw in rows:
        item = review_ai_portfolio_item(raw)
        key = item["capability_key"]
        if key:
            if key in seen:
                raise ValueError("duplicate capability_key")
            seen.add(key)

        mode = item["strategy_review"]["recommended_mode"] or "UNDECIDED"
        build_modes[mode] = build_modes.get(mode, 0) + 1

        provider = item["current_provider"]
        weight = item["dependency_weight"]
        if provider and weight is not None:
            provider_weights[provider] = provider_weights.get(provider, 0.0) + weight

        items.append(item)

    concentration = portfolio_concentration(provider_weights) if provider_weights else {
        "available": False,
        "reason": "no_provider_dependency_weights",
    }

    dependency_risks = []
    if concentration.get("available"):
        if concentration["largest_weight"] >= 0.6:
            dependency_risks.append("single_provider_dependency_high")
        if concentration["herfindahl_index"] >= 0.5:
            dependency_risks.append("provider_concentration_high")

    unresolved = [
        item["capability_key"]
        for item in items
        if not item["portfolio_review_ready"]
    ]

    return {
        "schema_version": "ai_capability_portfolio.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "items": items,
        "build_mode_counts": build_modes,
        "provider_concentration": concentration,
        "dependency_risks": dependency_risks,
        "unresolved_capabilities": unresolved,
        "provider_activation": False,
        "model_promotion": False,
        "budget_commitment": False,
    }


def ai_portfolio_gaps(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    portfolio = build_ai_capability_portfolio(rows)
    gaps = []

    for item in portfolio["items"]:
        if not item["portfolio_review_ready"]:
            gaps.append({
                "capability_key": item["capability_key"],
                "gap_type": "decision_evidence",
                "details": item["blockers"],
            })
            continue

        mode = item["strategy_review"]["recommended_mode"]
        if mode in {"BUILD", "HYBRID"} and not item["evaluation_ref"]:
            gaps.append({
                "capability_key": item["capability_key"],
                "gap_type": "evaluation",
                "details": ["evaluation_ref_required"],
            })

        if (
            item["current_provider"]
            and item["dependency_weight"] is not None
            and item["dependency_weight"] >= 0.6
            and (item["switching_cost"] is None or item["switching_cost"] >= 0.6)
        ):
            gaps.append({
                "capability_key": item["capability_key"],
                "gap_type": "strategic_dependency",
                "details": ["high_provider_dependency_and_switching_cost"],
            })

    return {
        "schema_version": "ai_portfolio_gaps.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "gaps": gaps,
        "provider_concentration": portfolio["provider_concentration"],
        "dependency_risks": portfolio["dependency_risks"],
    }


def compare_ai_options(
    *,
    capability_key: str,
    options: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    capability_key = _text(capability_key)
    if not capability_key:
        raise ValueError("capability_key required")

    reviewed = []
    for raw in options:
        option_key = _text(raw.get("option_key"))
        if not option_key:
            raise ValueError("option_key required")
        quality = _bounded(raw.get("observed_quality"), "observed_quality")
        reliability = _bounded(raw.get("observed_reliability"), "observed_reliability")
        privacy = _bounded(raw.get("privacy_fit"), "privacy_fit")
        switching = _bounded(raw.get("switching_flexibility"), "switching_flexibility")
        cost = _number(raw.get("cost_per_1k_tasks_cents"))
        latency = _number(raw.get("p95_latency_ms"))
        evidence_refs = [_text(x) for x in raw.get("evidence_refs", ()) if _text(x)]

        missing = []
        for name, value in (
            ("observed_quality", quality),
            ("observed_reliability", reliability),
            ("privacy_fit", privacy),
            ("switching_flexibility", switching),
            ("cost_per_1k_tasks_cents", cost),
            ("p95_latency_ms", latency),
        ):
            if value is None:
                missing.append(name)
        if not evidence_refs:
            missing.append("evidence_refs")

        score = None
        if not missing:
            if cost < 0 or latency < 0:
                raise ValueError("cost and latency must be nonnegative")
            cost_efficiency = 1 / (1 + cost / 100000)
            latency_efficiency = 1 / (1 + latency / 5000)
            score = (
                .30 * quality
                + .20 * reliability
                + .15 * privacy
                + .10 * switching
                + .15 * cost_efficiency
                + .10 * latency_efficiency
            )

        reviewed.append({
            "option_key": option_key,
            "available": not missing,
            "score": round(score, 6) if score is not None else None,
            "missing": missing,
            "observed_quality": quality,
            "observed_reliability": reliability,
            "privacy_fit": privacy,
            "switching_flexibility": switching,
            "cost_per_1k_tasks_cents": cost,
            "p95_latency_ms": latency,
            "evidence_refs": evidence_refs,
        })

    reviewed.sort(
        key=lambda row: (
            row["available"],
            row["score"] if row["score"] is not None else -1,
            row["option_key"],
        ),
        reverse=True,
    )
    for idx, row in enumerate(reviewed, 1):
        row["rank"] = idx

    return {
        "schema_version": "ai_option_comparison.v1",
        "capability_key": capability_key,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "options": reviewed,
        "provider_activation": False,
        "model_promotion": False,
        "recommendation_only": True,
    }
