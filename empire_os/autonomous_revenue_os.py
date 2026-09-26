"""Phase 18 Full Autonomous Revenue OS observe-only integration packet."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RevenueDecisionPacket:
    packet_key: str
    recommended_workstream: str | None
    recommended_job_type: str | None
    forecast_direction: str | None
    capital_candidate_id: str | None
    demand_plan_ref: str | None
    enterprise_blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"

    def validate(self) -> None:
        if not self.packet_key.strip():
            raise ValueError("packet_key required")
        if self.mode != "OBSERVE":
            raise ValueError("Phase 18 integration packet must remain OBSERVE")
        if self.side_effects != "none":
            raise ValueError("Phase 18 integration packet cannot have side effects")
        if self.execution_authority != "none":
            raise ValueError("Phase 18 integration packet cannot grant execution authority")
        if not self.evidence_refs:
            raise ValueError("integration packet requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
def compose_revenue_decision_packet(
    *,
    packet_key: str,
    astra_decision: Mapping[str, Any] | None,
    predictive_forecast: Mapping[str, Any] | None,
    capital_recommendation: Mapping[str, Any] | None,
    demand_plan_ref: str | None,
    enterprise_blockers: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...],
) -> RevenueDecisionPacket:
    astra = dict(astra_decision or {})
    forecast = dict(predictive_forecast or {})
    capital = dict(capital_recommendation or {})

    packet = RevenueDecisionPacket(
        packet_key=str(packet_key or "").strip(),
        recommended_workstream=(
            str(astra["workstream"]).strip()
            if astra.get("workstream") is not None
            else None
        ),
        recommended_job_type=(
            str(astra["recommended_job_type"]).strip()
            if astra.get("recommended_job_type") is not None
            else None
        ),
        forecast_direction=(
            str(forecast["direction"]).strip()
            if forecast.get("direction") is not None
            else None
        ),
        capital_candidate_id=(
            str(capital["candidate_id"]).strip()
            if capital.get("candidate_id") is not None
            else None
        ),
        demand_plan_ref=(
            str(demand_plan_ref).strip()
            if demand_plan_ref is not None
            else None
        ),
        enterprise_blockers=tuple(
            sorted({str(item).strip() for item in enterprise_blockers if str(item).strip()})
        ),
        evidence_refs=tuple(
            str(item).strip() for item in evidence_refs if str(item).strip()
        ),
    )
    packet.validate()
    return packet
