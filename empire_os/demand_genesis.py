"""Phase 12 Demand Genesis governed planning foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_CHANNELS = frozenset({
    "content",
    "aeo",
    "geo",
    "community",
    "partnership",
    "agent_distribution",
    "ads",
    "voice",
})


@dataclass(frozen=True)
class DemandPlan:
    plan_id: str
    channel: str
    objective: str
    audience: str
    evidence_refs: tuple[str, ...]
    success_metric: str
    execution_authority: str = "none"
    approval_required: bool = True

    def validate(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id required")
        if self.channel not in ALLOWED_CHANNELS:
            raise ValueError("unsupported demand channel")
        if not self.objective.strip() or not self.audience.strip():
            raise ValueError("objective and audience required")
        if not self.evidence_refs:
            raise ValueError("demand plan requires evidence")
        if not self.success_metric.strip():
            raise ValueError("success_metric required")
        if self.execution_authority != "none":
            raise ValueError("Phase 12 foundation cannot grant execution authority")
        if self.approval_required is not True:
            raise ValueError("demand execution must require approval")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
