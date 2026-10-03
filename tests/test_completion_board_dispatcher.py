from datetime import datetime, timezone

from empire_os.completion_board_dispatcher import dispatch_completion_board
from empire_os.department_work_queue import DepartmentWorkQueue


NOW = datetime(2026, 10, 2, 23, 30, tzinfo=timezone.utc)


def _checklist(tmp_path):
    path = tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
# Test
## Buyer acquisition / commercial loop
- [ ] Buyer review creation
- [ ] Continue real outbound
- [x] Existing done item

## Predictive Cloud convergence
- [ ] Build unified predictive analytics
- [ ] Real production evidence through the full loop

## Phase exit / real-money proof
- [ ] Founder approval for mainnet payment
""".strip() + "\n",
        encoding="utf-8",
    )


def test_dispatch_reads_live_checklist_not_legacy_snapshot(tmp_path):
    _checklist(tmp_path)
    result = dispatch_completion_board(tmp_path, now=NOW)

    assert result["status"] == "AVAILABLE"
    assert result["canonical_total_count"] == 6
    assert result["canonical_done_count"] == 1
    assert result["source_pending_count"] == 5
    assert result["legacy_allocation_snapshot_used"] is False
    assert result["consequential_actions_dispatched"] is False
    assert result["execution_authority"] == "none"
    assert DepartmentWorkQueue(tmp_path).counts()["ready"] > 0


def test_dispatch_is_idempotent_for_same_live_checklist(tmp_path):
    _checklist(tmp_path)
    first = dispatch_completion_board(tmp_path, now=NOW)
    second = dispatch_completion_board(tmp_path, now=NOW)

    assert first["queued_packet_count"] > 0
    assert second["queued_packet_count"] == 0
    assert second["existing_packet_count"] == first["packet_count"]


def test_founder_gate_never_becomes_external_action(tmp_path):
    _checklist(tmp_path)
    result = dispatch_completion_board(tmp_path, now=NOW)
    gates = [
        row for row in result["packets"]
        if row["execution_class"] == "founder_gate"
    ]

    assert gates
    assert all(
        row["action"] == "prepare_to_gate_and_verify_prerequisites"
        for row in gates
    )
    assert all(
        row["external_execution_allowed"] is False
        for row in gates
    )


def test_packet_materializes_exact_verify_contract_when_repo_tests_exist(tmp_path):
    _checklist(tmp_path)
    module = tmp_path / "empire_os/intelligence_probe.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("VALUE = 1\n", encoding="utf-8")
    test = tmp_path / "tests/test_intelligence_probe.py"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(
        "def test_probe():\n    assert True\n",
        encoding="utf-8",
    )

    result = dispatch_completion_board(tmp_path, now=NOW)

    assert any(
        row["verification_contract_ready"] is True
        for row in result["packets"]
    )

def test_builder_language_routes_to_builder_required(tmp_path):
    path = tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Demo\n"
        "## Agent & Tool Execution Plane — ACTIVE BUILD\n"
        "- [ ] Wire verified outcomes into Economic Memory\n"
        "- [ ] Build Founder Console execution surface\n",
        encoding="utf-8",
    )

    result = dispatch_completion_board(tmp_path, now=NOW)
    builder = [
        row for row in result["packets"]
        if row["execution_class"] == "builder_required"
    ]

    assert result["source_pending_count"] == 2
    assert sum(row["item_count"] for row in builder) == 1
    evidence = [
        row for row in result["packets"]
        if row["execution_class"] == "evidence_required"
    ]
    assert sum(row["item_count"] for row in evidence) == 1
    assert all(row["external_execution_allowed"] is False for row in builder)
