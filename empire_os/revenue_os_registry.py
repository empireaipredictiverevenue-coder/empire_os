"""Governed Phase 18 Revenue OS decision-packet registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.autonomous_revenue_os import RevenueDecisionPacket
from empire_os.revenue_os_readiness import RevenueOsReadiness


@dataclass(frozen=True)
class RevenueOsRegistryRecord:
    packet: RevenueDecisionPacket
    readiness: RevenueOsReadiness
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        self.packet.validate()
        if self.readiness.packet_key != self.packet.packet_key:
            raise ValueError("Revenue OS readiness packet mismatch")
        if self.readiness.mode != "OBSERVE":
            raise ValueError("Revenue OS registry must remain OBSERVE")
        if self.readiness.side_effects != "none":
            raise ValueError("Revenue OS registry cannot have side effects")
        if self.readiness.execution_authority != "none":
            raise ValueError("Revenue OS registry cannot grant execution")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("Revenue OS registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "packet": self.packet.as_dict(),
            "readiness": self.readiness.as_dict(),
            "evidence": dict(self.evidence),
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "spend_execution": False,
            "outreach_execution": False,
            "payment_execution": False,
            "allocation_execution": False,
            "deployment_execution": False,
        }
