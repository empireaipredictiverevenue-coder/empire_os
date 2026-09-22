"""Machine-verifiable Phase 3F engineering closeout.

Phase 3F may be engineering-complete while real-world evidence dependencies
remain unresolved. This evaluator never converts missing commercial evidence
into success. It distinguishes:
- engineering blockers that must stop phase advancement; from
- genuine evidence dependencies that are carried forward until real outcomes
  exist.

This module is read-only except for its local runtime snapshot. It grants no
commercial, payment, accounting, revenue-recognition or execution authority.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.commercial_recovery_audit import (
    build_recovery_implementation_audit,
)


OUTPUT = Path("runtime/phase_closeout/phase_3f_latest.json")
EXECUTIVE = Path("runtime/astra/executive_latest.json")
EVALUATION = Path("runtime/astra/executive_evaluation_latest.json")
PREDICTIVE = Path("runtime/predictive_intelligence/latest.json")
ECONOMIC_MEMORY = Path("runtime/economic_memory/latest.json")
OPPORTUNITY_VALUE = Path("runtime/opportunity_factory/value_latest.json")

ALLOWED_EVIDENCE_BLOCKERS = frozenset({
    "insufficient_verified_outcome_cohort",
})


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _current_plan_blockers(
    root: Path,
    plan_id: str,
) -> list[dict[str, Any]]:
    blocked = root / "runtime/departments/work/blocked"
    rows: list[dict[str, Any]] = []
    for path in sorted(blocked.glob("*.json")):
        row = _read(path)
        if str(row.get("plan_id") or "") != plan_id:
            continue
        rows.append({
            "work_id": row.get("id"),
            "step_id": row.get("step_id"),
            "target_component": row.get("target_component"),
            "action": row.get("action"),
            "blocker": row.get("error"),
        })
    return rows


def build_phase_3f_closeout(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    executive = _read(root / EXECUTIVE)
    evaluation = _read(root / EVALUATION)
    predictive = _read(root / PREDICTIVE)
    memory = _read(root / ECONOMIC_MEMORY)
    opportunity_value = _read(root / OPPORTUNITY_VALUE)
    recovery = build_recovery_implementation_audit(root)

    plan_id = str(
        evaluation.get("plan_id")
        or executive.get("plan_id")
        or ""
    ).strip()

    blockers = _current_plan_blockers(root, plan_id)
    blocker_counts = Counter(
        str(row.get("blocker") or "unknown")
        for row in blockers
    )
    evidence_only_blockers = bool(blockers) and all(
        str(row.get("blocker") or "") in ALLOWED_EVIDENCE_BLOCKERS
        for row in blockers
    )

    status_counts = evaluation.get("status_counts")
    status_counts = (
        dict(status_counts)
        if isinstance(status_counts, Mapping)
        else {}
    )
    undispatched = list(evaluation.get("undispatched_step_ids") or [])

    required_artifacts = {
        "predictive_intelligence": bool(predictive),
        "economic_memory": bool(memory),
        "opportunity_value": bool(opportunity_value),
        "recovery_audit": recovery.get("product_count", 0) > 0,
    }
    all_required_artifacts = all(required_artifacts.values())

    active_internal_work = sum(
        int(status_counts.get(name) or 0)
        for name in ("READY", "RUNNING", "REVIEW")
    )
    failed_internal_work = int(status_counts.get("FAILED") or 0)

    truth_contracts = {
        "predictive_prediction_only": (
            predictive.get("prediction_only") is True
        ),
        "predictive_no_llm_probability": (
            predictive.get("llm_probability_used") is False
        ),
        "predictive_no_search_score_probability": (
            predictive.get("search_scores_used") is False
        ),
        "economic_memory_verified_outcomes_only": (
            memory.get(
                "verified_outcomes_only_for_outcome_conditioned_memory"
            )
            is True
        ),
        "department_done_not_promoted_to_verified_outcome": (
            memory.get("department_done_is_verified_outcome") is False
        ),
        "model_weight_mutation_not_authorized": (
            memory.get("model_weight_mutation_authorized") is False
        ),
        "opportunity_value_prediction_only": (
            opportunity_value.get("prediction_only") is True
        ),
        "opportunity_value_not_actual_revenue": (
            opportunity_value.get("actual_revenue") is False
        ),
        "recovery_registry_not_production_proof": (
            recovery.get("registry_state_is_production_proof") is False
        ),
        "recovery_runtime_not_revenue_proof": (
            recovery.get("runtime_artifact_is_revenue_proof") is False
        ),
    }
    truth_contracts_pass = all(truth_contracts.values())

    engineering_ready = (
        bool(plan_id)
        and all_required_artifacts
        and not undispatched
        and active_internal_work == 0
        and failed_internal_work == 0
        and truth_contracts_pass
        and (
            not blockers
            or evidence_only_blockers
        )
    )

    source_outcomes = int(predictive.get("source_outcome_count") or 0)
    probability_ready = int(
        predictive.get("probability_ready_product_count") or 0
    )
    timing_ready = int(
        predictive.get("timing_ready_product_count") or 0
    )

    if not engineering_ready:
        closeout_state = "ENGINEERING_INCOMPLETE"
    elif blockers:
        closeout_state = "ENGINEERING_READY_EVIDENCE_GATED"
    else:
        closeout_state = "ENGINEERING_READY"

    revenue_expansion = {
        "opportunity_value_scoring": {
            "foundation_present": bool(opportunity_value),
            "candidate_count": int(
                opportunity_value.get("candidate_count") or 0
            ),
            "value_available_count": int(
                opportunity_value.get("value_available_count") or 0
            ),
            "commercialization_ready": (
                int(opportunity_value.get("value_available_count") or 0) > 0
            ),
        },
        "outcome_based_product_development": {
            "foundation_present": bool(memory),
            "verified_outcome_memory_count": int(
                memory.get("outcome_conditioned_memory_count") or 0
            ),
            "learning_ready": (
                int(memory.get("outcome_conditioned_memory_count") or 0) > 0
            ),
        },
        "commercial_diagnostics_foundation": {
            "foundation_present": any(
                row.get("key") == "revenue_leak_audit"
                and row.get("implementation_state")
                != "NO_REPO_EVIDENCE"
                for row in recovery.get("products") or []
                if isinstance(row, Mapping)
            ),
            "sellable_claimed": False,
        },
    }

    carried_forward: list[dict[str, Any]] = []
    if source_outcomes == 0:
        carried_forward.append({
            "dependency": "genuine_verified_commercial_outcomes",
            "reason": (
                "Predictive probability, confidence, uncertainty and "
                "outcome-conditioned learning require real terminal outcomes."
            ),
            "engineering_blocker": False,
        })
    if probability_ready == 0:
        carried_forward.append({
            "dependency": "verified_outcome_cohort_threshold",
            "reason": (
                "No product has yet reached the minimum verified terminal "
                "outcome cohort for probability estimation."
            ),
            "engineering_blocker": False,
        })
    if timing_ready == 0:
        carried_forward.append({
            "dependency": "verified_time_to_revenue_cohort",
            "reason": (
                "No product has yet reached the verified timing sample "
                "threshold; the staged timing read-model migration remains a "
                "separate production database gate."
            ),
            "engineering_blocker": False,
        })

    return {
        "schema_version": "empire.phase_3f_closeout.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": plan_id or None,
        "closeout_state": closeout_state,
        "engineering_ready": engineering_ready,
        "phase_can_advance": engineering_ready,
        "production_proof_complete": False,
        "required_artifacts": required_artifacts,
        "all_required_artifacts_present": all_required_artifacts,
        "evaluation_state": evaluation.get("evaluation_state"),
        "status_counts": status_counts,
        "undispatched_step_ids": undispatched,
        "active_internal_work_count": active_internal_work,
        "failed_internal_work_count": failed_internal_work,
        "current_plan_blocker_count": len(blockers),
        "current_plan_blocker_counts": dict(sorted(blocker_counts.items())),
        "current_plan_blockers": blockers,
        "evidence_only_blockers": evidence_only_blockers,
        "truth_contracts": truth_contracts,
        "truth_contracts_pass": truth_contracts_pass,
        "source_outcome_count": source_outcomes,
        "probability_ready_product_count": probability_ready,
        "timing_ready_product_count": timing_ready,
        "upgrade_and_enhance": {
            "machine_verifiable_closeout": True,
            "current_plan_filtering": True,
            "historical_blocked_work_preserved": True,
            "evidence_dependencies_separated_from_engineering_failures": True,
            "unknown_stays_unknown": True,
        },
        "revenue_expansion": revenue_expansion,
        "carried_forward_dependencies": carried_forward,
        "database_migration_applied_by_closeout": False,
        "external_execution_performed": False,
        "actual_revenue": False,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }


def refresh_phase_3f_closeout(
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    payload = build_phase_3f_closeout(root)
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
