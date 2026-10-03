import empire_os.department_cycle as module


def test_department_cycle_runs_worker_then_evaluation(
    tmp_path, monkeypatch
):
    calls = []

    def fake_worker(root, *, max_items, timeout_seconds):
        calls.append(("worker", max_items, timeout_seconds))
        return {
            "ok": True,
            "processed_count": 3,
            "done_count": 2,
            "blocked_count": 1,
            "failed_count": 0,
        }

    def fake_evaluation(root):
        calls.append(("evaluation",))
        return {
            "plan_id": "astra_plan_test",
            "evaluation_state": "BLOCKED",
            "eligible_step_count": 3,
            "status_counts": {"DONE": 2, "BLOCKED": 1},
            "undispatched_step_ids": [],
            "result_evidence_refs": ["runtime:x"],
        }

    def fake_queue_truth(root):
        calls.append(("live_queue_truth",))
        return {
            "status": "AVAILABLE",
            "canonical_checklist": {
                "done": 10,
                "pending": 5,
                "total": 15,
            },
            "active_execution_backlog": 3,
            "department_work_queue": {"active_count": 1},
            "coder_queue": {
                "active_pending_count": 1,
                "active_running_count": 1,
                "fastpath_plan_pending_count": 0,
                "local_model_plan_pending_count": 1,
                "verify_pending_count": 0,
            },
            "legacy_completion_allocation_snapshot": {
                "stale": True,
            },
        }

    def fake_policy(root):
        calls.append(("business_optimization_policy",))
        return {
            "status": "AVAILABLE",
            "workload_count": 12,
            "active_policy_count": 1,
            "ready_for_policy_materialization_count": 0,
            "partial_evidence_count": 3,
            "blocked_count": 11,
            "synthetic_constraints_generated": False,
            "synthetic_economics_generated": False,
            "automatic_business_action_allowed": False,
        }

    def fake_sources(root):
        calls.append(("business_optimization_sources",))
        return {
            "status": "AVAILABLE",
            "workload_count": 12,
            "source_adapter_implemented_count": 2,
            "automation_ready_count": 1,
            "enqueued_count": 1,
            "automatic_business_action_allowed": False,
            "third_party_service_called": False,
        }

    def fake_optimization(root, *, max_requests, benchmark_variable_limit):
        calls.append((
            "business_optimization",
            max_requests,
            benchmark_variable_limit,
        ))
        return {
            "status": "AVAILABLE",
            "automation_enabled": True,
            "claimed_request_count": 2,
            "processed_request_count": 2,
            "recomputed_request_count": 1,
            "decision_changed_count": 1,
            "queued_request_count_remaining": 0,
            "processing_request_count_remaining": 0,
            "automatic_business_action_allowed": False,
            "third_party_service_called": False,
        }

    def fake_memory(root):
        calls.append(("economic_memory",))
        return {
            "department_episode_count": 3,
            "outcome_conditioned_memory_count": 1,
            "rejected_outcome_memory_count": 0,
            "verified_outcomes_only_for_outcome_conditioned_memory": True,
        }

    monkeypatch.setattr(module, "run_department_worker", fake_worker)
    monkeypatch.setattr(module, "evaluate_executive_plan", fake_evaluation)
    monkeypatch.setattr(
        module,
        "refresh_economic_memory_snapshot",
        fake_memory,
    )
    monkeypatch.setattr(
        module,
        "run_business_optimization_policy_intelligence",
        fake_policy,
    )
    monkeypatch.setattr(
        module,
        "build_live_queue_truth",
        fake_queue_truth,
    )
    monkeypatch.setattr(
        module,
        "run_business_optimization_source_cycle",
        fake_sources,
    )
    monkeypatch.setattr(
        module,
        "run_business_optimization_cycle",
        fake_optimization,
    )

    result = module.run_department_cycle(
        tmp_path,
        max_items=3,
        timeout_seconds=45,
    )
    assert calls == [
        ("worker", 3, 45),
        ("evaluation",),
        ("economic_memory",),
        ("business_optimization_policy",),
        ("business_optimization_sources",),
        ("business_optimization", 24, 18),
        ("live_queue_truth",),
    ]
    assert result["worker"]["done_count"] == 2
    assert result["evaluation"]["evaluation_state"] == "BLOCKED"
    assert result["economic_memory"]["department_episode_count"] == 3
    assert result["economic_memory"]["outcome_conditioned_memory_count"] == 1
    assert result["economic_memory"]["verified_outcomes_only"] is True
    assert result["business_optimization_policy"][
        "active_policy_count"
    ] == 1
    assert result["business_optimization_policy"][
        "synthetic_constraints_generated"
    ] is False
    assert result["business_optimization_sources"][
        "source_adapter_implemented_count"
    ] == 2
    assert result["business_optimization_sources"][
        "enqueued_count"
    ] == 1
    assert result["business_optimization_automation"][
        "automation_enabled"
    ] is True
    assert result["live_queue_truth"]["active_execution_backlog"] == 3
    assert result["live_queue_truth"][
        "legacy_allocation_snapshot_stale"
    ] is True
    assert result["business_optimization_automation"][
        "processed_request_count"
    ] == 2
    assert result["business_optimization_automation"][
        "automatic_business_action_allowed"
    ] is False
    assert result["external_execution_performed"] is False
    assert result["execution_authority"] == "none"


def test_department_cycle_persists_process_and_work_truth(
    tmp_path,
    monkeypatch,
):
    import empire_os.department_cycle as module

    monkeypatch.setattr(
        module,
        "run_department_worker",
        lambda *args, **kwargs: {
            "ok": False,
            "processed_count": 2,
            "done_count": 1,
            "blocked_count": 0,
            "failed_count": 1,
        },
    )

    monkeypatch.setattr(
        module,
        "evaluate_executive_plan",
        lambda root: {
            "plan_id": "test",
            "evaluation_state": "IN_PROGRESS",
            "eligible_step_count": 1,
            "status_counts": {"READY": 1},
            "undispatched_step_ids": [],
            "result_evidence_refs": [],
        },
    )

    monkeypatch.setattr(
        module,
        "refresh_economic_memory_snapshot",
        lambda root: {
            "department_episode_count": 1,
            "outcome_conditioned_memory_count": 0,
            "rejected_outcome_memory_count": 0,
            "verified_outcomes_only_for_outcome_conditioned_memory": True,
        },
    )
    monkeypatch.setattr(
        module,
        "run_business_optimization_policy_intelligence",
        lambda *args, **kwargs: {
            "status": "AVAILABLE",
            "workload_count": 12,
            "active_policy_count": 0,
            "ready_for_policy_materialization_count": 0,
            "partial_evidence_count": 0,
            "blocked_count": 12,
            "synthetic_constraints_generated": False,
            "synthetic_economics_generated": False,
            "automatic_business_action_allowed": False,
        },
    )
    monkeypatch.setattr(
        module,
        "run_business_optimization_source_cycle",
        lambda *args, **kwargs: {
            "status": "AVAILABLE",
            "workload_count": 12,
            "source_adapter_implemented_count": 2,
            "automation_ready_count": 0,
            "enqueued_count": 0,
            "automatic_business_action_allowed": False,
            "third_party_service_called": False,
        },
    )
    monkeypatch.setattr(
        module,
        "build_live_queue_truth",
        lambda *args, **kwargs: {
            "status": "AVAILABLE",
            "canonical_checklist": {},
            "active_execution_backlog": 0,
            "department_work_queue": {"active_count": 0},
            "coder_queue": {
                "active_pending_count": 0,
                "active_running_count": 0,
                "fastpath_plan_pending_count": 0,
                "local_model_plan_pending_count": 0,
                "verify_pending_count": 0,
            },
            "legacy_completion_allocation_snapshot": {"stale": False},
        },
    )
    monkeypatch.setattr(
        module,
        "run_business_optimization_cycle",
        lambda *args, **kwargs: {
            "status": "AVAILABLE",
            "automation_enabled": True,
            "claimed_request_count": 0,
            "processed_request_count": 0,
            "recomputed_request_count": 0,
            "decision_changed_count": 0,
            "queued_request_count_remaining": 0,
            "processing_request_count_remaining": 0,
            "automatic_business_action_allowed": False,
            "third_party_service_called": False,
        },
    )

    result = module.run_department_cycle(tmp_path)

    assert result["service_health"] == "completed"
    assert result["work_ok"] is False
    assert result["worker"]["failed_count"] == 1
