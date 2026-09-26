"""Governed Phase 12 demand-plan registry contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.demand_genesis import DemandPlan
from empire_os.demand_readiness import DemandReadiness


@dataclass(frozen=True)
class DemandRegistryRecord:
    plan: DemandPlan
    readiness: DemandReadiness
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        self.plan.validate()
        if self.readiness.plan_id != self.plan.plan_id:
            raise ValueError("readiness plan_id must match demand plan")
        if self.readiness.execution_authority != "none":
            raise ValueError("demand readiness cannot grant execution authority")
        if self.readiness.approval_required is not True:
            raise ValueError("demand registry requires operator approval")
        if not self.readiness.ready_for_review:
            raise ValueError("only review-ready demand plans may be registered")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("demand registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "plan": self.plan.as_dict(),
            "readiness": self.readiness.as_dict(),
            "evidence": dict(self.evidence),
            "mode": "OBSERVE",
            "execution_authority": "none",
            "publishing_enabled": False,
            "outbound_enabled": False,
            "ad_spend_enabled": False,
            "provider_activation_enabled": False,
        }
