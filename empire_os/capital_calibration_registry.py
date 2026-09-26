"""Phase 15 append-only capital calibration history contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.capital_freshness import CapitalOutcomeCalibration


@dataclass(frozen=True)
class CapitalCalibrationRecord:
    calibration: CapitalOutcomeCalibration
    evidence: Mapping[str, Any]
    mode: str = "OBSERVE"
    recommendation_only: bool = True
    execution_authority: str = "none"
    funds_movement: bool = False
    budget_mutation: bool = False
    recommendation_mutation: bool = False
    model_weight_mutation: bool = False

    def validate(self) -> None:
        if not self.calibration.candidate_id.strip():
            raise ValueError("capital calibration candidate_id required")
        if not self.recommendation_only:
            raise ValueError("capital calibration must remain recommendation_only")
        if self.execution_authority != "none":
            raise ValueError("capital calibration cannot grant execution")
        if (
            self.funds_movement
            or self.budget_mutation
            or self.recommendation_mutation
            or self.model_weight_mutation
        ):
            raise ValueError("capital calibration cannot mutate or execute")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("capital calibration registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "calibration": self.calibration.as_dict(),
            "evidence": dict(self.evidence),
            "eligible_for_model_review": self.calibration.calibration_available,
            **{
                key: value
                for key, value in asdict(self).items()
                if key not in {"calibration", "evidence"}
            },
        }
