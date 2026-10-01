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

    result = module.run_department_cycle(
        tmp_path,
        max_items=3,
        timeout_seconds=45,
    )
    assert calls == [
        ("worker", 3, 45),
        ("evaluation",),
        ("economic_memory",),
    ]
    assert result["worker"]["done_count"] == 2
    assert result["evaluation"]["evaluation_state"] == "BLOCKED"
    assert result["economic_memory"]["department_episode_count"] == 3
    assert result["economic_memory"]["outcome_conditioned_memory_count"] == 1
    assert result["economic_memory"]["verified_outcomes_only"] is True
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

    result = module.run_department_cycle(tmp_path)

    assert result["service_health"] == "completed"
    assert result["work_ok"] is False
    assert result["worker"]["failed_count"] == 1
