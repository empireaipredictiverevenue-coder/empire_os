"""Governed Phase 11 experiment registry contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ExperimentRegistryRecord:
    experiment_key: str
    hypothesis: str
    metric: str
    control_variant: str
    treatment_variants: tuple[str, ...]
    assignment_integrity_verified: bool
    exposure_integrity_verified: bool
    outcome_window_closed: bool
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        for name, value in (
            ("experiment_key", self.experiment_key),
            ("hypothesis", self.hypothesis),
            ("metric", self.metric),
            ("control_variant", self.control_variant),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} required")
        variants = tuple(
            str(v).strip() for v in self.treatment_variants if str(v).strip()
        )
        if not variants:
            raise ValueError("at least one treatment variant required")
        if self.control_variant in variants:
            raise ValueError("control cannot also be a treatment")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("evidence must be an object")
        if not self.evidence:
            raise ValueError("experiment registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "experiment_key": self.experiment_key,
            "hypothesis": self.hypothesis,
            "metric": self.metric,
            "control_variant": self.control_variant,
            "treatment_variants": list(self.treatment_variants),
            "assignment_integrity_verified": self.assignment_integrity_verified,
            "exposure_integrity_verified": self.exposure_integrity_verified,
            "outcome_window_closed": self.outcome_window_closed,
            "evidence": dict(self.evidence),
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
        }
