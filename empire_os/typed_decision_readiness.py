"""Readiness board for typed-decision / Jev evaluation tasks.

Decision support only. It cannot select providers or promote routing.
"""
from __future__ import annotations
from typing import Any, Iterable, Mapping


REQUIRED_TASKS = (
    "reply_classification",
    "keyword_intent",
    "source_quality",
    "buyer_corridor_fit",
    "agent_routing",
    "guardrail_classification",
)


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _bool(v: Any) -> bool:
    return v is True


def review_task_readiness(raw: Mapping[str, Any]) -> dict[str, Any]:
    task_key=str(raw.get("task_key") or "").strip()
    blockers=[]
    if task_key not in REQUIRED_TASKS:
        blockers.append("unsupported_task")

    real_labels=_int(raw.get("real_labeled_case_count"))
    provider_outputs=_int(raw.get("provider_output_count"))
    shadow_records=_int(raw.get("shadow_record_count"))
    independent_reviews=_int(raw.get("independent_review_count"))
    minimum_real_labels=max(1,_int(raw.get("minimum_real_labels") or 100))
    minimum_provider_outputs=max(1,_int(raw.get("minimum_provider_outputs") or 100))
    minimum_shadow_records=max(1,_int(raw.get("minimum_shadow_records") or 100))

    if real_labels < minimum_real_labels:
        blockers.append("insufficient_real_labels")
    if provider_outputs < minimum_provider_outputs:
        blockers.append("insufficient_provider_outputs")
    if shadow_records < minimum_shadow_records:
        blockers.append("insufficient_shadow_records")
    if independent_reviews < 1:
        blockers.append("independent_review_required")
    if not _bool(raw.get("calibration_observed")):
        blockers.append("calibration_not_observed")
    if not _bool(raw.get("fallback_tested")):
        blockers.append("fallback_not_tested")
    if not _bool(raw.get("drift_monitor_defined")):
        blockers.append("drift_monitor_not_defined")
    if not _bool(raw.get("schema_failure_measured")):
        blockers.append("schema_failure_not_measured")
    if raw.get("synthetic_cases_present") is True:
        blockers.append("synthetic_cases_present")

    return {
        "schema_version":"typed_decision_task_readiness.v1",
        "task_key":task_key or None,
        "offline_eval_ready":(
            real_labels >= minimum_real_labels
            and independent_reviews >= 1
            and raw.get("synthetic_cases_present") is not True
        ),
        "shadow_eval_ready":(
            real_labels >= minimum_real_labels
            and provider_outputs >= minimum_provider_outputs
            and _bool(raw.get("fallback_tested"))
        ),
        "promotion_review_ready":not blockers,
        "blockers":blockers,
        "evidence":{
            "real_labeled_case_count":real_labels,
            "provider_output_count":provider_outputs,
            "shadow_record_count":shadow_records,
            "independent_review_count":independent_reviews,
            "calibration_observed":_bool(raw.get("calibration_observed")),
            "fallback_tested":_bool(raw.get("fallback_tested")),
            "drift_monitor_defined":_bool(raw.get("drift_monitor_defined")),
            "schema_failure_measured":_bool(raw.get("schema_failure_measured")),
        },
        "provider_selected":False,
        "production_routing_enabled":False,
        "execution_authority":"none",
    }


def build_readiness_board(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    reviewed=[]
    seen=set()
    for raw in rows:
        item=review_task_readiness(raw)
        task=item["task_key"]
        if task:
            if task in seen:
                raise ValueError("duplicate task_key")
            seen.add(task)
        reviewed.append(item)

    missing=[task for task in REQUIRED_TASKS if task not in seen]
    ready=sum(1 for item in reviewed if item["promotion_review_ready"])
    return {
        "schema_version":"typed_decision_readiness_board.v1",
        "tasks":reviewed,
        "missing_tasks":missing,
        "task_count":len(reviewed),
        "promotion_review_ready_count":ready,
        "all_core_tasks_ready":(
            not missing
            and len(reviewed)==len(REQUIRED_TASKS)
            and ready==len(REQUIRED_TASKS)
        ),
        "provider_selected":False,
        "production_routing_enabled":False,
        "execution_authority":"none",
    }


def next_evidence_actions(board: Mapping[str, Any]) -> dict[str, Any]:
    actions=[]
    for item in board.get("tasks") or []:
        task=item.get("task_key")
        for blocker in item.get("blockers") or []:
            actions.append({
                "task_key":task,
                "blocker":blocker,
                "action":{
                    "insufficient_real_labels":"collect_and_review_real_labels",
                    "insufficient_provider_outputs":"collect_offline_provider_outputs",
                    "insufficient_shadow_records":"run_zero_side_effect_shadow",
                    "independent_review_required":"assign_independent_reviewer",
                    "calibration_not_observed":"compute_calibration_metrics",
                    "fallback_not_tested":"test_failover_path",
                    "drift_monitor_not_defined":"define_drift_monitor",
                    "schema_failure_not_measured":"measure_schema_failure_rate",
                    "synthetic_cases_present":"separate_synthetic_from_real_dataset",
                    "unsupported_task":"fix_task_contract",
                }.get(blocker,"investigate"),
            })
    for task in board.get("missing_tasks") or []:
        actions.append({
            "task_key":task,
            "blocker":"task_missing_from_board",
            "action":"create_task_evidence_record",
        })
    return {
        "schema_version":"typed_decision_next_evidence_actions.v1",
        "actions":actions,
        "action_count":len(actions),
        "automatic_execution":False,
        "execution_authority":"none",
    }
