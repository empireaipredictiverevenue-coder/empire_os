"""Media creative experiment contracts.

Experiment Intelligence remains the canonical analysis/causal-review owner.
This module only prepares and records media-specific experiment evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class MediaExperiment:
    experiment_id: str
    channel_id: str
    hypothesis: str
    variable: str
    control_ref: str
    candidate_ref: str
    primary_metric: str
    start_at: str | None = None
    end_at: str | None = None
    guardrail_metrics: tuple[str, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id is required")
        if not self.channel_id.strip():
            raise ValueError("channel_id is required")
        if not self.hypothesis.strip():
            raise ValueError("hypothesis is required")
        if self.variable not in {
            "title",
            "thumbnail",
            "hook",
            "intro",
            "length",
            "cta",
            "publish_time",
            "presenter_style",
            "visual_style",
            "format",
            "short_style",
        }:
            raise ValueError("unsupported media experiment variable")
        if not self.control_ref.strip() or not self.candidate_ref.strip():
            raise ValueError("control and candidate refs are required")
        if not self.primary_metric.strip():
            raise ValueError("primary_metric is required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "analysis_owner": "experiment_intelligence",
            "execution_authority": "none",
        }


def prepare_media_experiment(
    experiment: MediaExperiment,
) -> dict[str, Any]:
    row = experiment.as_dict()
    return {
        "schema_version": "empire.media.experiment_candidate.v1",
        "mode": "OBSERVE",
        "experiment": row,
        "state": "PROPOSAL_ONLY",
        "control_required": True,
        "candidate_required": True,
        "causal_claim_created": False,
        "public_mutation_authorized": False,
        "execution_authority": "none",
    }


def record_media_experiment_outcome(
    experiment: MediaExperiment,
    *,
    control_metrics: Mapping[str, Any],
    candidate_metrics: Mapping[str, Any],
    sample_sufficient: bool,
    confounders: tuple[str, ...] = (),
) -> dict[str, Any]:
    experiment.validate()
    return {
        "schema_version": "empire.media.experiment_outcome.v1",
        "mode": "OBSERVE",
        "experiment_id": experiment.experiment_id,
        "primary_metric": experiment.primary_metric,
        "control_metrics": dict(control_metrics),
        "candidate_metrics": dict(candidate_metrics),
        "sample_sufficient": bool(sample_sufficient),
        "confounders": list(confounders),
        "result_state": (
            "READY_FOR_EXPERIMENT_INTELLIGENCE_REVIEW"
            if sample_sufficient
            else "INSUFFICIENT_EVIDENCE"
        ),
        "winner_declared": False,
        "causal_claim_created": False,
        "analysis_owner": "experiment_intelligence",
        "execution_authority": "none",
    }
