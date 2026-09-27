"""Media workflow evolution and skill-candidate compiler.

Recovered Empire skill-library patterns are treated as salvage knowledge only.
This module does not create a second live skill registry and cannot mutate
production workflows.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class WorkflowExecutionEvidence:
    execution_id: str
    workflow_name: str
    workflow_version: str
    input_shape_hash: str
    step_signature: tuple[str, ...]
    outcome_state: str
    quality_score: float | None
    accuracy_passed: bool
    failure_modes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.execution_id.strip():
            raise ValueError("execution_id is required")
        if not self.workflow_name.strip():
            raise ValueError("workflow_name is required")
        if not self.workflow_version.strip():
            raise ValueError("workflow_version is required")
        if not self.step_signature:
            raise ValueError("step_signature is required")
        if not self.evidence_refs:
            raise ValueError("workflow evidence_refs are required")
        if self.quality_score is not None and not (
            0.0 <= float(self.quality_score) <= 1.0
        ):
            raise ValueError("quality_score must be within 0..1")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def compile_media_skill_candidate(
    executions: Iterable[WorkflowExecutionEvidence],
    *,
    minimum_repeats: int = 3,
    minimum_quality: float = 0.75,
) -> dict[str, Any]:
    rows = [row.as_dict() for row in executions]
    if not rows:
        raise ValueError("workflow execution evidence is required")

    names = {row["workflow_name"] for row in rows}
    versions = {row["workflow_version"] for row in rows}
    signatures = {tuple(row["step_signature"]) for row in rows}

    consistent = (
        len(names) == 1
        and len(versions) == 1
        and len(signatures) == 1
    )
    passing = [
        row
        for row in rows
        if row["accuracy_passed"] is True
        and row["outcome_state"] == "SUCCESS"
        and (
            row["quality_score"] is not None
            and float(row["quality_score"]) >= minimum_quality
        )
    ]

    if consistent and len(passing) >= max(1, int(minimum_repeats)):
        state = "SKILL_CANDIDATE"
    else:
        state = "HOLD_FOR_MORE_EVIDENCE"

    failures = sorted({
        failure
        for row in rows
        for failure in row.get("failure_modes") or []
    })

    return {
        "schema_version": "empire.media.skill_candidate.v1",
        "mode": "OBSERVE",
        "workflow_name": next(iter(names)) if len(names) == 1 else None,
        "workflow_version": (
            next(iter(versions))
            if len(versions) == 1
            else None
        ),
        "execution_count": len(rows),
        "passing_execution_count": len(passing),
        "consistent_procedure": consistent,
        "step_signature": (
            list(next(iter(signatures)))
            if len(signatures) == 1
            else None
        ),
        "failure_modes": failures,
        "state": state,
        "required_promotion_path": [
            "extract_procedure",
            "identify_deterministic_components",
            "capture_reasoning_points",
            "capture_failure_modes",
            "generate_tests",
            "replay",
            "shadow_validation",
            "version",
            "register_with_canonical_skill_infrastructure",
        ],
        "production_self_modification_authorized": False,
        "automatic_registration_authorized": False,
        "execution_authority": "none",
    }


def workflow_promotion_review(
    *,
    candidate_ref: str,
    tests_passed: bool,
    replay_passed: bool,
    shadow_passed: bool,
    quality_improved: bool,
    accuracy_regressed: bool,
    cost_regressed_materially: bool,
    failure_rate_regressed: bool,
) -> dict[str, Any]:
    if not str(candidate_ref or "").strip():
        raise ValueError("candidate_ref is required")

    blockers = []
    for condition, label in (
        (not tests_passed, "tests_not_passed"),
        (not replay_passed, "replay_not_passed"),
        (not shadow_passed, "shadow_not_passed"),
        (not quality_improved, "quality_not_improved"),
        (accuracy_regressed, "accuracy_regressed"),
        (cost_regressed_materially, "material_cost_regression"),
        (failure_rate_regressed, "failure_rate_regressed"),
    ):
        if condition:
            blockers.append(label)

    return {
        "schema_version": "empire.media.workflow_promotion_review.v1",
        "mode": "OBSERVE",
        "candidate_ref": candidate_ref,
        "blockers": blockers,
        "state": (
            "PROMOTION_CANDIDATE"
            if not blockers
            else "HOLD_OR_REJECT"
        ),
        "controlled_experiment_required": True,
        "automatic_production_promotion": False,
        "production_self_modification_authorized": False,
        "execution_authority": "none",
    }
