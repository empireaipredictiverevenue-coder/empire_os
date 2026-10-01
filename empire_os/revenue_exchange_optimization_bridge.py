"""Governed Revenue Exchange -> Hybrid Optimization bridge.

Consumes only allocation proposals that are explicitly ready for operator match
review and carry evidenced economics. Produces recommendation-only optimization
previews. It never allocates inventory, changes pricing, accepts terms, moves
funds, or recognizes revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping, Sequence

from empire_os.hybrid_optimization import build_hybrid_optimization_plan
from empire_os.quantum_optimization import build_allocation_optimization_problem


SCHEMA_VERSION = "empire.revenue_exchange_optimization_bridge.v1"


@dataclass(frozen=True)
class RevenueExchangeOptimizationPreview:
    status: str
    optimization_problem: Mapping[str, Any]
    hybrid_plan: Mapping[str, Any]
    proposals_considered: int
    proposals_blocked: int
    schema_version: str = SCHEMA_VERSION
    recommendation_only: bool = True
    allocation_execution: bool = False
    pricing_mutation: bool = False
    terms_acceptance: bool = False
    payment_action: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        raw = asdict(value)
        return raw if isinstance(raw, Mapping) else None
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        raw = as_dict()
        return raw if isinstance(raw, Mapping) else None
    return None


def _extract(
    proposals: Sequence[Any],
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    options: list[dict[str, Any]] = []
    capacities: dict[str, int] = {}
    blocked: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for value in proposals:
        raw = _mapping(value)
        if raw is None:
            blocked.append({"reason": "not_a_mapping"})
            continue

        inventory_id = str(raw.get("inventory_id") or "").strip()
        buyer_id = str(raw.get("buyer_id") or "").strip()

        if raw.get("ready_for_operator_match_review") is not True:
            blocked.append({
                "inventory_id": inventory_id or None,
                "buyer_id": buyer_id or None,
                "reason": "not_ready_for_operator_match_review",
            })
            continue

        expected = raw.get("expected_value_cents")

        refs = tuple(dict.fromkeys(
            str(ref).strip()
            for ref in (raw.get("evidence_refs") or ())
            if str(ref).strip()
        ))

        missing: list[str] = []
        if not inventory_id:
            missing.append("inventory_id")
        if not buyer_id:
            missing.append("buyer_id")
        if expected is None:
            missing.append("expected_value_cents")
        if not refs:
            missing.append("evidence_refs")
        if missing:
            blocked.append({
                "inventory_id": inventory_id or None,
                "buyer_id": buyer_id or None,
                "missing_fields": missing,
                "reason": "unknown_allocation_economics_preserved",
            })
            continue

        try:
            expected_number = float(expected)
        except (TypeError, ValueError):
            blocked.append({
                "inventory_id": inventory_id,
                "buyer_id": buyer_id,
                "reason": "invalid_expected_value_cents",
            })
            continue
        if expected_number < 0:
            blocked.append({
                "inventory_id": inventory_id,
                "buyer_id": buyer_id,
                "reason": "negative_expected_value_not_allowed",
            })
            continue

        key = (inventory_id, buyer_id)
        if key in seen:
            blocked.append({
                "inventory_id": inventory_id,
                "buyer_id": buyer_id,
                "reason": "duplicate_assignment_option",
            })
            continue
        seen.add(key)

        capacity = raw.get("buyer_capacity_remaining")
        if capacity is None:
            blocked.append({
                "inventory_id": inventory_id,
                "buyer_id": buyer_id,
                "missing_fields": ["buyer_capacity_remaining"],
                "reason": "buyer_capacity_unknown",
            })
            continue
        try:
            capacity_number = int(capacity)
        except (TypeError, ValueError):
            blocked.append({
                "inventory_id": inventory_id,
                "buyer_id": buyer_id,
                "reason": "invalid_buyer_capacity_remaining",
            })
            continue
        if capacity_number < 0:
            blocked.append({
                "inventory_id": inventory_id,
                "buyer_id": buyer_id,
                "reason": "invalid_buyer_capacity_remaining",
            })
            continue

        previous_capacity = capacities.get(buyer_id)
        if (
            previous_capacity is not None
            and previous_capacity != capacity_number
        ):
            blocked.append({
                "inventory_id": inventory_id,
                "buyer_id": buyer_id,
                "reason": "conflicting_buyer_capacity_evidence",
                "observed_capacities": sorted({
                    previous_capacity,
                    capacity_number,
                }),
            })
            options = [
                option
                for option in options
                if option.get("buyer_id") != buyer_id
            ]
            capacities.pop(buyer_id, None)
            continue

        capacities[buyer_id] = capacity_number
        options.append({
            "prospect_id": inventory_id,
            "buyer_id": buyer_id,
            "expected_value_cents": expected_number,
            "evidence_refs": refs,
        })

    return options, capacities, blocked


def build_revenue_exchange_optimization_preview(
    *,
    allocation_proposals: Sequence[Any],
    exact_variable_limit: int = 24,
) -> RevenueExchangeOptimizationPreview:
    options, capacities, bridge_blocked = _extract(allocation_proposals)
    problem = build_allocation_optimization_problem(
        options=options,
        buyer_capacities=capacities,
    )

    merged_problem = dict(problem)
    merged_problem["blocked_options"] = [
        *bridge_blocked,
        *(problem.get("blocked_options") or []),
    ]
    plan = build_hybrid_optimization_plan(
        merged_problem,
        exact_variable_limit=exact_variable_limit,
    )

    available = (
        str(merged_problem.get("status") or "").upper() == "AVAILABLE"
        and str(plan.get("status") or "").upper() == "AVAILABLE"
    )
    return RevenueExchangeOptimizationPreview(
        status="AVAILABLE" if available else "UNAVAILABLE",
        optimization_problem=merged_problem,
        hybrid_plan=plan,
        proposals_considered=len(options),
        proposals_blocked=len(merged_problem["blocked_options"]),
    )
