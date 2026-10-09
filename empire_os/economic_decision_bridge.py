"""Canonical Opportunity -> Capital -> Department Work convergence bridge.

This module does not create economic truth or execution authority.

It translates an already-evidenced, recommendation-only capital review into a
shadow/OBSERVE DepartmentWork proposal while preserving canonical opportunity
and prediction lineage.

Capital recommendation != approval.
Portfolio selection != execution authority.
Prediction != execution authority.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from empire_os.capital_registry import CapitalReviewRecord
from empire_os.department_work_queue import DepartmentWorkQueue


SCHEMA_VERSION = "empire.economic_decision_bridge.v1"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} required")
    return value


def _optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _refs(values: Sequence[Any] | None, name: str) -> tuple[str, ...]:
    refs = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in (values or ())
            if str(value).strip()
        )
    )
    if not refs:
        raise ValueError(f"{name} required")
    return refs


def _proposal_ref(material: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(material),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    # DepartmentWorkQueue identifiers permit only alphanumeric, "_" and "-".
    return "economic_decision_" + sha256(encoded).hexdigest()[:24]


def build_economic_decision_work_proposal(
    *,
    capital_record: CapitalReviewRecord,
    tenant_id: str,
    opportunity_key: str,
    opportunity_id: str | None,
    prediction_ref: str,
    state_ref: str,
    source_ref: str,
    department_keys: Sequence[str],
    target_component: str,
    action: str,
    evidence_refs: Sequence[str],
    goal_key: str = "evaluate_economic_opportunity",
    success_condition: str = (
        "economic recommendation remains evidence-backed and non-authoritative"
    ),
    rationale: str = (
        "capital recommendation selected for governed shadow review"
    ),
) -> dict[str, Any]:
    """Build a non-authoritative DepartmentWork-compatible proposal.

    This function deliberately produces shadow_only=True and carries no
    selection_authority_ref. A capital recommendation is evidence, not
    authorization.
    """
    capital_record.validate()

    tenant = _text(tenant_id, "tenant_id")
    opportunity = _text(opportunity_key, "opportunity_key")
    opportunity_id = _optional_text(opportunity_id, "opportunity_id")
    prediction = _text(prediction_ref, "prediction_ref")
    state = _text(state_ref, "state_ref")
    source = _text(source_ref, "source_ref")
    target = _text(target_component, "target_component")
    action_name = _text(action, "action")
    goal = _text(goal_key, "goal_key")
    success = _text(success_condition, "success_condition")
    why = _text(rationale, "rationale")

    departments = _refs(department_keys, "department_keys")
    explicit_evidence = _refs(evidence_refs, "evidence_refs")
    capital_evidence = _refs(
        capital_record.candidate.evidence_refs,
        "capital candidate evidence_refs",
    )

    candidate_id = _text(
        capital_record.candidate.candidate_id,
        "candidate_id",
    )

    if candidate_id != opportunity:
        raise ValueError("capital candidate/opportunity mismatch")

    review = capital_record.review
    if review.candidate_id != opportunity:
        raise ValueError("capital review/opportunity mismatch")
    if review.recommendation_only is not True:
        raise ValueError("capital review must remain recommendation_only")
    if review.execution_authority != "none":
        raise ValueError("capital review cannot grant execution authority")
    if review.review_eligible is not True:
        raise ValueError("capital review is not review eligible")
    if review.blockers:
        raise ValueError("capital review contains blockers")

    record = capital_record.as_dict()
    if record.get("recommendation_only") is not True:
        raise ValueError("capital record must remain recommendation_only")
    if record.get("execution_authority") != "none":
        raise ValueError("capital record cannot grant execution authority")
    if record.get("funds_movement") is not False:
        raise ValueError("capital record cannot move funds")
    if record.get("budget_mutation") is not False:
        raise ValueError("capital record cannot mutate budget")

    all_evidence = tuple(
        dict.fromkeys(
            (
                *explicit_evidence,
                *capital_evidence,
                f"capital_review:{capital_record.review_key}",
            )
        )
    )

    material = {
        "tenant_id": tenant,
        "opportunity_key": opportunity,
        "opportunity_id": opportunity_id,
        "prediction_ref": prediction,
        "capital_review_key": capital_record.review_key,
        "state_ref": state,
        "source_ref": source,
        "department_keys": departments,
        "target_component": target,
        "action": action_name,
        "evidence_refs": all_evidence,
    }
    proposal_ref = _proposal_ref(material)

    return {
        "schema_version": SCHEMA_VERSION,
        "proposal_ref": proposal_ref,
        "mode": "OBSERVE",
        "recommendation_only": True,
        "shadow_only": True,
        "execution_authority": "none",
        "capital_execution": False,
        "funds_movement": False,
        "budget_mutation": False,
        "capital_review_key": capital_record.review_key,
        "capital_assessment": review.assessment.as_dict(),
        "work_step": {
            "step_id": proposal_ref,
            "goal_key": goal,
            "department_keys": list(departments),
            "target_component": target,
            "action": action_name,
            "authority": "observe",
            "auto_dispatch_eligible": False,
            "founder_gate_required": False,
            "intelligence_request": {
                "task": "economic_decision_review",
                "recommendation_only": True,
                "capital_review_key": capital_record.review_key,
                "prediction_ref": prediction,
            },
            "memory_query": {
                "retrieval_only": True,
                "opportunity_key": opportunity,
            },
            "evidence_refs": list(all_evidence),
            "success_condition": success,
            "rationale": why,
            "commercial_decision_provenance": {
                "tenant_id": tenant,
                "opportunity_key": opportunity,
                "opportunity_id": opportunity_id,
                "candidate_id": candidate_id,
                "prediction_ref": prediction,
                "state_ref": state,
                "source_ref": source,
                "shadow_only": True,
                "selection_authority_ref": None,
                "execution_authority": "none",
            },
        },
    }


def enqueue_economic_decision_work(
    repo_root: str | Path,
    *,
    plan_id: str,
    proposal: Mapping[str, Any],
    priority: int = 80,
):
    """Explicitly persist an already-built proposal into DepartmentWorkQueue.

    This does not claim or execute the work.
    """
    plan = _text(plan_id, "plan_id")

    if proposal.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("economic decision proposal schema invalid")
    if proposal.get("mode") != "OBSERVE":
        raise ValueError("economic decision proposal must remain OBSERVE")
    if proposal.get("recommendation_only") is not True:
        raise ValueError("economic decision proposal must remain recommendation_only")
    if proposal.get("shadow_only") is not True:
        raise ValueError("economic decision proposal must remain shadow_only")
    if proposal.get("execution_authority") != "none":
        raise ValueError("economic decision proposal cannot grant authority")
    if proposal.get("capital_execution") is not False:
        raise ValueError("economic decision proposal cannot execute capital")
    if proposal.get("funds_movement") is not False:
        raise ValueError("economic decision proposal cannot move funds")
    if proposal.get("budget_mutation") is not False:
        raise ValueError("economic decision proposal cannot mutate budget")

    step = proposal.get("work_step")
    if not isinstance(step, Mapping):
        raise ValueError("work_step required")

    provenance = step.get("commercial_decision_provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("commercial decision provenance required")
    if provenance.get("shadow_only") is not True:
        raise ValueError("economic decision work must remain shadow")
    if provenance.get("selection_authority_ref") is not None:
        raise ValueError("capital recommendation cannot create selection authority")
    if provenance.get("execution_authority") != "none":
        raise ValueError("commercial provenance cannot grant authority")

    queue = DepartmentWorkQueue(repo_root)
    return queue.enqueue_step(
        plan_id=plan,
        step=step,
        priority=priority,
    )
