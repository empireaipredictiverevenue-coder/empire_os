"""Run one bounded department heartbeat and evaluate the Astra plan."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from empire_os.astra_department_evaluator import evaluate_executive_plan
from empire_os.department_worker import run_department_worker
from empire_os.completion_board_dispatcher import dispatch_completion_board
from empire_os.completion_reconciliation import (
    refresh_completion_reconciliation,
)
from empire_os.completion_task_monitor import (
    MonitorEvidenceError, refresh_completion_task_monitor,
)
from empire_os.marketing_agency import observe_marketing_agency
from empire_os.economic_memory import refresh_economic_memory_snapshot
from empire_os.completion_progress import refresh_completion_progress
from empire_os.completion_closure_reconciler import reconcile_completion_closure
from empire_os.completion_live_proof import run_completion_live_proof
from empire_os.live_queue_truth import build_live_queue_truth
from empire_os.business_optimization_automation import (
    run_business_optimization_cycle,
)
from empire_os.business_optimization_sources import (
    run_business_optimization_source_cycle,
)
from empire_os.business_optimization_policy_intelligence import (
    run_business_optimization_policy_intelligence,
)


OUTPUT = Path("runtime/astra/department_cycle_latest.json")
CANONICAL_HOOK_REVIEW_ROOT = Path("/srv/empire_os")


def review_revenue_first_hooks_in_cycle(root: Path) -> dict[str, Any]:
    """Passive evidence observation within the EXISTING department heartbeat.

    No extra timer, queue, content publishing or model invocation is added.
    Test/scratch worktrees never query production sources. A read failure
    cannot stop an unrelated department cycle.
    """
    if root != CANONICAL_HOOK_REVIEW_ROOT:
        return {
            "status": "NOT_CANONICAL_RUNTIME",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "candidate_count": 0,
            "hooks_dispatched": 0,
        }
    try:
        from scripts.review_revenue_first_hook_evidence import run
        review = run(root=root, include_public_website=False)
        return {
            "status": "REVIEW_ONLY_NO_DISPATCH",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "candidate_count": review["candidate_count"],
            "candidates": [
                {
                    "hook_key": row["hook_key"],
                    "priority": row["priority"],
                    "review_status": row["review_status"],
                }
                for row in review["existing_hook_candidates"]
            ],
            "seo_evidence_state": review["source_status"]["search_intelligence"]["interpretation"],
            "buyer_reply_evidence_state": review["source_status"]["buyer_replies"]["interpretation"],
            "conversion_evidence_state": review["source_status"]["conversion"]["interpretation"],
            "revenue_evidence_state": review["source_status"]["revenue_pulse"]["interpretation"],
            "hooks_dispatched": review["jobs_dispatched"],
            "models_invoked": review["models_invoked"],
            "outbound_sent": review["buyer_replies_sent"],
            "payments_executed": review["payments_executed"],
        }
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        return {
            "status": "HELD_SOURCE_UNAVAILABLE",
            "reason_code": type(exc).__name__,
            "mode": "OBSERVE",
            "execution_authority": "none",
            "candidate_count": 0,
            "hooks_dispatched": 0,
        }


def run_department_cycle(
    repo_root: str | Path,
    *,
    max_items: int = 4,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    completion_dispatch = dispatch_completion_board(root)
    worker = run_department_worker(
        root,
        max_items=max_items,
        timeout_seconds=timeout_seconds,
    )
    completion_reconciliation = refresh_completion_reconciliation(root)
    # No additional timer or agent loop: monitor the reconciled tasks during
    # the department cycle already responsible for this work.
    try:
        task_monitor = refresh_completion_task_monitor(root)
    except (MonitorEvidenceError, ValueError, OSError) as exc:
        # Monitoring source failure never expands builder authority or
        # prevents independent department activity; last valid report stays.
        task_monitor = {
            "status": "HELD",
            "reason": str(exc)[:120],
            "execution_authority": "none",
            "monitoring_not_dispatch": True,
        }
    evaluation = evaluate_executive_plan(root)
    economic_memory = refresh_economic_memory_snapshot(root)
    completion_live_proof = run_completion_live_proof(root)
    completion_closure = reconcile_completion_closure(root, apply=True)
    completion_progress = refresh_completion_progress(root)
    business_optimization_policy = (
        run_business_optimization_policy_intelligence(root)
    )
    business_optimization_sources = (
        run_business_optimization_source_cycle(root)
    )
    business_optimization = run_business_optimization_cycle(
        root,
        max_requests=24,
        benchmark_variable_limit=18,
    )
    live_queue_truth = build_live_queue_truth(root)
    payload = {
        "schema_version": "empire.department_cycle.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service_health": "completed",
        "work_ok": worker.get("ok") is not False,
        "completion_board_dispatch": {
            "status": completion_dispatch.get("status"),
            "source_pending_count": completion_dispatch.get(
                "source_pending_count"
            ),
            "packet_count": completion_dispatch.get("packet_count"),
            "queued_packet_count": completion_dispatch.get(
                "queued_packet_count"
            ),
            "existing_packet_count": completion_dispatch.get(
                "existing_packet_count"
            ),
            "consequential_actions_dispatched": completion_dispatch.get(
                "consequential_actions_dispatched"
            ),
            "founder_gates_preserved": completion_dispatch.get(
                "founder_gates_preserved"
            ),
        },
        "task_monitor": {
            "status": task_monitor.get("status"),
            "reason": task_monitor.get("reason"),
            "tracked_pending_count": task_monitor.get("tracked_pending_count"),
            "new_state_transition_count": task_monitor.get(
                "new_state_transition_count"
            ),
            "attention_count": task_monitor.get("attention_count"),
            "provider_blocked_count": task_monitor.get("provider_blocked_count"),
            "code_complete_not_live_count": task_monitor.get(
                "code_complete_not_live_count"
            ),
            "notifications_sent": False,
            "execution_authority": "none",
        },
        "completion_reconciliation": {
            "status": completion_reconciliation.get("status"),
            "reconciled_item_count": completion_reconciliation.get(
                "reconciled_item_count"
            ),
            "state_counts": completion_reconciliation.get(
                "state_counts"
            ) or {},
            "remediation_candidate_count": completion_reconciliation.get(
                "remediation_candidate_count"
            ),
            "live_proof_candidate_count": completion_reconciliation.get(
                "live_proof_candidate_count"
            ),
            "founder_gate_count": completion_reconciliation.get(
                "founder_gate_count"
            ),
            "automatic_checklist_mutation_allowed": (
                completion_reconciliation.get(
                    "automatic_checklist_mutation_allowed"
                )
            ),
        },
        "worker": {
            "ok": worker.get("ok"),
            "processed_count": worker.get("processed_count"),
            "done_count": worker.get("done_count"),
            "blocked_count": worker.get("blocked_count"),
            "failed_count": worker.get("failed_count"),
        },
        "evaluation": {
            "plan_id": evaluation.get("plan_id"),
            "evaluation_state": evaluation.get("evaluation_state"),
            "eligible_step_count": evaluation.get(
                "eligible_step_count"
            ),
            "status_counts": evaluation.get("status_counts") or {},
            "undispatched_step_ids": evaluation.get(
                "undispatched_step_ids"
            ) or [],
            "result_evidence_refs": evaluation.get(
                "result_evidence_refs"
            ) or [],
        },
        "completion_live_proof": {
            "status": completion_live_proof.get("status"),
            "pending_rule_match_count": completion_live_proof.get(
                "pending_rule_match_count"
            ),
            "live_proof_pass_count": completion_live_proof.get(
                "live_proof_pass_count"
            ),
            "live_proof_blocked_count": completion_live_proof.get(
                "live_proof_blocked_count"
            ),
            "checkpoints_written": completion_live_proof.get(
                "checkpoints_written"
            ) or [],
        },
        "completion_closure": {
            "status": completion_closure.get("status"),
            "eligible_exact_closure_count": completion_closure.get(
                "eligible_exact_closure_count"
            ),
            "applied_closure_count": completion_closure.get(
                "applied_closure_count"
            ),
            "state_counts": completion_closure.get("state_counts") or {},
            "synthetic_completion_evidence_used": (
                completion_closure.get(
                    "synthetic_completion_evidence_used"
                )
            ),
        },
        "completion_progress": {
            "status": completion_progress.get("status"),
            "master_checklist": completion_progress.get(
                "master_checklist"
            ) or {},
            "active_atomic_builder_count": completion_progress.get(
                "active_atomic_builder_count"
            ),
        },
        "live_queue_truth": {
            "status": live_queue_truth.get("status"),
            "canonical_checklist": live_queue_truth.get(
                "canonical_checklist"
            ) or {},
            "active_execution_backlog": live_queue_truth.get(
                "active_execution_backlog"
            ),
            "department_active_count": (
                dict(
                    live_queue_truth.get("department_work_queue") or {}
                ).get("active_count")
            ),
            "coder_active_pending_count": (
                dict(live_queue_truth.get("coder_queue") or {}).get(
                    "active_pending_count"
                )
            ),
            "coder_active_running_count": (
                dict(live_queue_truth.get("coder_queue") or {}).get(
                    "active_running_count"
                )
            ),
            "fastpath_plan_pending_count": (
                dict(live_queue_truth.get("coder_queue") or {}).get(
                    "fastpath_plan_pending_count"
                )
            ),
            "local_model_plan_pending_count": (
                dict(live_queue_truth.get("coder_queue") or {}).get(
                    "local_model_plan_pending_count"
                )
            ),
            "verify_pending_count": (
                dict(live_queue_truth.get("coder_queue") or {}).get(
                    "verify_pending_count"
                )
            ),
            "legacy_allocation_snapshot_stale": (
                dict(
                    live_queue_truth.get(
                        "legacy_completion_allocation_snapshot"
                    ) or {}
                ).get("stale")
            ),
        },
        "economic_memory": {
            "department_episode_count": economic_memory.get(
                "department_episode_count"
            ),
            "outcome_conditioned_memory_count": economic_memory.get(
                "outcome_conditioned_memory_count"
            ),
            "rejected_outcome_memory_count": economic_memory.get(
                "rejected_outcome_memory_count"
            ),
            "verified_outcomes_only": economic_memory.get(
                "verified_outcomes_only_for_outcome_conditioned_memory"
            ),
        },
        "business_optimization_policy": {
            "status": business_optimization_policy.get("status"),
            "workload_count": business_optimization_policy.get(
                "workload_count"
            ),
            "active_policy_count": business_optimization_policy.get(
                "active_policy_count"
            ),
            "ready_for_policy_materialization_count": (
                business_optimization_policy.get(
                    "ready_for_policy_materialization_count"
                )
            ),
            "partial_evidence_count": business_optimization_policy.get(
                "partial_evidence_count"
            ),
            "blocked_count": business_optimization_policy.get(
                "blocked_count"
            ),
            "synthetic_constraints_generated": (
                business_optimization_policy.get(
                    "synthetic_constraints_generated"
                )
            ),
            "synthetic_economics_generated": (
                business_optimization_policy.get(
                    "synthetic_economics_generated"
                )
            ),
            "automatic_business_action_allowed": (
                business_optimization_policy.get(
                    "automatic_business_action_allowed"
                )
            ),
        },
        "business_optimization_sources": {
            "status": business_optimization_sources.get("status"),
            "workload_count": business_optimization_sources.get(
                "workload_count"
            ),
            "source_adapter_implemented_count": (
                business_optimization_sources.get(
                    "source_adapter_implemented_count"
                )
            ),
            "automation_ready_count": business_optimization_sources.get(
                "automation_ready_count"
            ),
            "enqueued_count": business_optimization_sources.get(
                "enqueued_count"
            ),
            "automatic_business_action_allowed": (
                business_optimization_sources.get(
                    "automatic_business_action_allowed"
                )
            ),
            "third_party_service_called": (
                business_optimization_sources.get(
                    "third_party_service_called"
                )
            ),
        },
        "business_optimization_automation": {
            "status": business_optimization.get("status"),
            "automation_enabled": business_optimization.get(
                "automation_enabled"
            ),
            "claimed_request_count": business_optimization.get(
                "claimed_request_count"
            ),
            "processed_request_count": business_optimization.get(
                "processed_request_count"
            ),
            "recomputed_request_count": business_optimization.get(
                "recomputed_request_count"
            ),
            "decision_changed_count": business_optimization.get(
                "decision_changed_count"
            ),
            "queued_request_count_remaining": business_optimization.get(
                "queued_request_count_remaining"
            ),
            "processing_request_count_remaining": business_optimization.get(
                "processing_request_count_remaining"
            ),
            "automatic_business_action_allowed": business_optimization.get(
                "automatic_business_action_allowed"
            ),
            "third_party_service_called": business_optimization.get(
                "third_party_service_called"
            ),
        },
        "marketing_growth": observe_marketing_agency(root),
        # Existing department-cycle timer owns this passive revenue-first
        # observation. No extra daemon, provider call or dispatch is created.
        "revenue_first_hook_review": review_revenue_first_hooks_in_cycle(root),
        "external_execution_performed": False,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
