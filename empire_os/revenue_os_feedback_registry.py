"""Phase 18 append-only learning feedback registry contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.revenue_os_learning import RevenueOsLearningReadiness


@dataclass(frozen=True)
class RevenueOsLearningRecord:
    readiness: RevenueOsLearningReadiness
    evidence: Mapping[str, Any]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"
    model_weight_mutation: bool = False
    capital_reallocation: bool = False
    spend_execution: bool = False
    outreach_execution: bool = False
    payment_execution: bool = False
    allocation_execution: bool = False
    deployment_execution: bool = False

    def validate(self) -> None:
        if not self.readiness.packet_key.strip():
            raise ValueError("learning feedback packet_key required")
        if self.readiness.mode != "OBSERVE":
            raise ValueError("learning feedback must remain OBSERVE")
        if self.readiness.side_effects != "none":
            raise ValueError("learning feedback cannot have side effects")
        if self.readiness.execution_authority != "none":
            raise ValueError("learning feedback cannot grant execution")
        if (
            self.readiness.model_weight_mutation
            or self.readiness.capital_reallocation
            or self.readiness.spend_execution
            or self.readiness.outreach_execution
            or self.readiness.payment_execution
            or self.readiness.allocation_execution
            or self.readiness.deployment_execution
        ):
            raise ValueError("learning feedback cannot mutate or execute")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("learning feedback registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "readiness": self.readiness.as_dict(),
            "evidence": dict(self.evidence),
            "eligible_for_model_review": self.readiness.learning_ready,
            **{
                key: value
                for key, value in asdict(self).items()
                if key not in {"readiness", "evidence"}
            },
        }
