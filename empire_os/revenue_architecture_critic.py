"""Fresh-context deterministic critic for Autonomous Revenue OS.

This critic has no execution authority and does not inspect mutable agent context.
It independently evaluates the release contract presented to it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RevenueArchitectureCriticReview:
    passed: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_revenue_architecture(
    contract: Mapping[str, Any],
) -> RevenueArchitectureCriticReview:
    blockers: list[str] = []

    if contract.get("single_control_plane") != "autonomous_revenue_os":
        blockers.append("duplicate_or_unknown_control_plane")
    if contract.get("timer_driven") is not False:
        blockers.append("timer_led_orchestration_not_allowed")
    if contract.get("unknown_price_stays_null") is not True:
        blockers.append("unknown_price_truth_guard_missing")
    if contract.get("real_sources_only") is not True:
        blockers.append("synthetic_or_unverified_source_risk")
    if contract.get("usdt_bsc_only") is not True:
        blockers.append("canonical_payment_rail_not_enforced")

    try:
        lead_batch = int(contract.get("lead_generation_batch") or 0)
    except (TypeError, ValueError):
        lead_batch = 0
    if not 1 <= lead_batch <= 50:
        blockers.append("lead_generation_batch_unbounded")

    try:
        qualification_batch = int(contract.get("qualification_batch") or 0)
    except (TypeError, ValueError):
        qualification_batch = 0
    if not 1 <= qualification_batch <= 25:
        blockers.append("qualification_batch_unbounded")

    for key in (
        "external_send",
        "call_execution",
        "booking_execution",
        "binding_terms",
        "fund_movement",
        "revenue_recognition",
    ):
        if contract.get(key) is not False:
            blockers.append(f"{key}_must_remain_gated")

    required_stages = (
        "RAW_LEAD",
        "PREQUALIFIED_LEAD",
        "QUALIFIED_CALL",
        "BOOKED_APPOINTMENT",
        "CPA_OUTCOME",
    )
    if tuple(contract.get("inventory_stages") or ()) != required_stages:
        blockers.append("inventory_stage_contract_mismatch")

    return RevenueArchitectureCriticReview(
        passed=not blockers,
        blockers=tuple(blockers),
    )
