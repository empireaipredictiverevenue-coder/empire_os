"""Governed Phase 17 enterprise readiness registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_review import EnterpriseReadinessReview


@dataclass(frozen=True)
class EnterpriseReadinessRecord:
    readiness_key: str
    controls: tuple[ControlEvidence, ...]
    slos: tuple[SloObservation, ...]
    review: EnterpriseReadinessReview
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.readiness_key or "").strip():
            raise ValueError("readiness_key required")
        if not self.controls:
            raise ValueError("enterprise registry requires control evidence")
        if not self.slos:
            raise ValueError("enterprise registry requires SLO evidence")
        for row in self.controls:
            row.validate()
        if self.review.execution_authority != "none":
            raise ValueError("enterprise registry cannot grant execution")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("enterprise registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "readiness_key": self.readiness_key,
            "controls": [row.as_dict() for row in self.controls],
            "slos": [
                {
                    "service_key": row.service_key,
                    "metric": row.metric,
                    "target": row.target,
                    "observed": row.observed,
                    "window": row.window,
                    "observed_at": row.observed_at,
                    "source": row.source,
                    "meets_target": row.meets_target,
                }
                for row in self.slos
            ],
            "review": self.review.as_dict(),
            "evidence": dict(self.evidence),
            "mode": "OBSERVE",
            "execution_authority": "none",
            "control_mutation": False,
            "infrastructure_mutation": False,
            "identity_mutation": False,
            "backup_mutation": False,
            "slo_target_mutation": False,
            "compliance_mutation": False,
        }
