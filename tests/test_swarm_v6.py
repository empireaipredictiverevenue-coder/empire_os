from pathlib import Path

from empire_os.swarm_v6 import LANES, run_swarm_cycle


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "runtime").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "docs").mkdir(parents=True)
    (root / "docs/BLUEPRINT_V6.md").write_text("# Blueprint\n")
    (root / "empire_os").mkdir()
    (root / "tests").mkdir()
    for lane in LANES:
        for rel in lane.reviewed_files:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# test target\n")
        for rel in lane.tests:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("def test_ok():\n    assert True\n")
    return root


def test_swarm_declares_six_bounded_specialist_lanes():
    assert all(lane.changed_files == lane.reviewed_files for lane in LANES)
    assert [lane.key for lane in LANES] == [
        "revenue_payments",
        "closer_outreach",
        "growth_conversion",
        "search_opportunity",
        "platform_saas",
        "integration_qa",
    ]


def test_enqueue_only_creates_one_verify_job_per_lane(tmp_path):
    root = _workspace(tmp_path)

    result = run_swarm_cycle(
        root,
        max_workers=2,
        execute_verify=False,
    )

    assert result["mode"] == "OBSERVE_TESTS_ONLY"
    assert result["commander"] == "astra"
    assert len(result["queued"]) == len(LANES)
    assert result["queue_after"]["pending"] == len(LANES)
    assert result["executions"] == []
    assert result["implementation_assignments"] == []
    assert result["implementation_authority_source"] == "EXPLICIT_EXECUTION_PLANE_ONLY"
    from empire_os.coder.jobs import LocalJobQueue
    queue = LocalJobQueue(root)
    for queued in result["queued"]:
        job = queue.get(queued["job_id"])
        assert job.kind.value == "VERIFY"
        assert job.payload["verification_scope"] == "TEST_EXECUTION_ONLY"
        assert job.payload["implementation_authority"] == "NONE"
        assert "changed_files" not in job.payload
        assert job.payload["reviewed_files"]
    assert result["authority"] == {
        "production_mutation": False,
        "outbound_send": False,
        "commercial_terms_acceptance": False,
        "fund_movement": False,
        "payment_confirmation": False,
        "fulfilment": False,
        "revenue_recognition": False,
        "authority_expansion": False,
    }


def test_swarm_review_jobs_execute_only_as_tests_and_never_implement(tmp_path):
    import subprocess

    from empire_os.coder.jobs import JobStatus, LocalJobQueue
    from empire_os.coder.verify_fastpath import drain_verify_jobs

    root = _workspace(tmp_path)
    subprocess.run(("git", "init", "-q"), cwd=root, check=True)
    cycle = run_swarm_cycle(root, execute_verify=False)
    queue = LocalJobQueue(root)

    assert queue.claim_next(kind=None) is None
    evidence = drain_verify_jobs(queue, max_jobs=len(LANES), timeout_seconds=120)
    assert evidence["completed_count"] == len(LANES)
    assert evidence["failed_count"] == 0
    for row in cycle["queued"]:
        job = queue.get(row["job_id"])
        assert job.status is JobStatus.COMPLETED
        assert job.result["verification"]["verdict"] == "TESTS_ONLY"
        assert job.result["verification"]["implementation_verified"] is False
        assert job.result["task_completed"] is False
        assert job.result["changed_files_inferred"] is False


def test_existing_queue_is_not_duplicated(tmp_path):
    root = _workspace(tmp_path)
    first = run_swarm_cycle(root, execute_verify=False)
    second = run_swarm_cycle(root, execute_verify=False)

    assert len(first["queued"]) == len(LANES)
    assert second["queued"] == []
    assert second["queue_before"]["pending"] == len(LANES)
    assert second["queue_after"]["pending"] == len(LANES)
