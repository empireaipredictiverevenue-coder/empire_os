"""Phase 18 review-readiness gate for OBSERVE-only revenue packets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.autonomous_revenue_os import RevenueDecisionPacket


@dataclass(frozen=True)
class RevenueOsReadiness:
    packet_key: str
    ready_for_operator_review: bool
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_revenue_os_readiness(
    packet: RevenueDecisionPacket,
) -> RevenueOsReadiness:
    packet.validate()
    blockers: list[str] = list(packet.enterprise_blockers)

    if not packet.recommended_workstream:
        blockers.append("astra_workstream_missing")
    if not packet.recommended_job_type:
        blockers.append("astra_job_type_missing")
    if not packet.forecast_direction:
        blockers.append("forecast_direction_missing")
    if not packet.capital_candidate_id:
        blockers.append("capital_candidate_missing")
    if not packet.demand_plan_ref:
        blockers.append("demand_plan_missing")

    ordered = tuple(sorted(set(blockers)))
    return RevenueOsReadiness(
        packet_key=packet.packet_key,
        ready_for_operator_review=not ordered,
        blockers=ordered,
    )
