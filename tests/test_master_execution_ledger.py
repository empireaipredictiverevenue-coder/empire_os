from pathlib import Path

from empire_os.master_execution_ledger import (
    build_execution_ledger,
    parse_checklist,
    summarize_items,
)


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "docs/MASTER_REMAINING_CHECKLIST.md"


def test_parser_preserves_section_line_and_checkbox_truth(tmp_path):
    path = tmp_path / "checklist.md"
    path.write_text(
        "# Demo\n"
        "## Revenue\n"
        "- [x] Existing proven thing\n"
        "- [ ] Real payment proof\n",
        encoding="utf-8",
    )
    items = parse_checklist(path)
    assert len(items) == 2
    assert items[0].section == "Revenue"
    assert items[0].status == "DONE"
    assert items[1].status == "PENDING"
    assert items[1].line == 4


def test_summary_never_infers_runtime_completion():
    items = parse_checklist(CHECKLIST)
    summary = summarize_items(items)
    assert summary["total"] == summary["done"] + summary["pending"]
    assert summary["pending"] > 200
    assert "live production completion" in summary["completion_rule"]


def test_current_reconciliation_preserves_new_and_old_work():
    ledger = build_execution_ledger(CHECKLIST)
    by_item = {row["item"]: row for row in ledger["items"]}

    assert by_item[
        "Needle 3 shadow router installed and live-benchmarked"
    ]["status"] == "DONE"
    assert by_item[
        "Buyer Reply / Conversation Operations Agent"
    ]["status"] == "PENDING"
    assert by_item[
        "Temporal durable workflow layer for long-running commercial flows"
    ]["status"] == "PENDING"
    assert by_item[
        "Phase 18 — Full Autonomous Revenue OS"
    ]["status"] == "PENDING"

    assert ledger["authority"]["runtime_reconciliation_required"] is True
    assert ledger["authority"]["code_presence_is_not_completion"] is True
    assert ledger["authority"]["execution_authority"] == "none"


def test_existing_real_money_exit_gate_is_still_pending():
    ledger = build_execution_ledger(CHECKLIST)
    rows = {
        row["item"]: row["status"]
        for row in ledger["items"]
    }
    assert rows["Verified USDT/BSC payment"] == "PENDING"
    assert rows["Recognized revenue"] == "PENDING"
    assert rows["Realized GP"] == "PENDING"
