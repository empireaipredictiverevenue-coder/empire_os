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
        for rel in lane.changed_files:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# test target\n")
        for rel in lane.tests:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("def test_ok():\n    assert True\n")
    return root


def test_swarm_declares_six_bounded_specialist_lanes():
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

    assert result["mode"] == "INTERNAL_VERIFY"
    assert result["commander"] == "astra"
    assert len(result["queued"]) == len(LANES)
    assert result["queue_after"]["pending"] == len(LANES)
    assert result["executions"] == []
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


def test_existing_queue_is_not_duplicated(tmp_path):
    root = _workspace(tmp_path)
    first = run_swarm_cycle(root, execute_verify=False)
    second = run_swarm_cycle(root, execute_verify=False)

    assert len(first["queued"]) == len(LANES)
    assert second["queued"] == []
    assert second["queue_before"]["pending"] == len(LANES)
    assert second["queue_after"]["pending"] == len(LANES)
