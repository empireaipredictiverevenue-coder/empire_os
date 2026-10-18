from empire_os.predictive_decision_duplicate_guard import _identities


def test_identity_refs():
    assert _identities(['business_entity:123', 'prospect:456']) == {'business_entity:123', 'prospect:456'}

import json
from pathlib import Path

from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.predictive_decision_duplicate_guard import (
    MAX_RECORDS, review_cross_plan_duplicates,
)
from empire_os.predictive_decision_handoff import build_predictive_decision_handoff
from test_predictive_decision_handoff import NOW, _decision


def _check(root: Path):
    return review_cross_plan_duplicates(
        root, action="verify_decision_maker",
        evidence_refs=["business_entity:entity-a", "prospect:prospect-a"],
        own_plan_id="predictive_review_v1",
    )


def _write_job(root, *, plan="another_astra_plan", action="verify_decision_maker",
               refs=None, state="ready"):
    queue = DepartmentWorkQueue(root)
    step = {
        "step_id": "same_customer_research",
        "goal_key": "buyer_review",
        "department_keys": ["sales_revenue"],
        "target_component": "identity_enrichment",
        "action": action,
        "authority": "observe",
        "evidence_refs": (["business_entity:entity-a"] if refs is None else refs),
    }
    item, _ = queue.enqueue_step(plan_id=plan, step=step)
    return item


def test_no_cross_plan_match_is_review_only(tmp_path):
    result = _check(tmp_path)
    assert result["status"] == "NO_EXACT_CROSS_PLAN_MATCH"
    assert result["cross_plan_scan_complete"] is True
    assert not (tmp_path / "runtime").exists()


def test_existing_other_plan_is_not_mislabeled_as_new(tmp_path):
    _write_job(tmp_path)
    result = _check(tmp_path)
    assert result["status"] == "POSSIBLE_DUPLICATE_REVIEW"
    assert result["matching_count"] == 1
    out = build_predictive_decision_handoff(_decision(), tmp_path, as_of=NOW)
    assert out["ready_for_review_count"] == 0
    assert out["held_count"] == 1
    packet = out["candidates"][0]
    assert packet["current_work_status"] == "POSSIBLE_DUPLICATE_REVIEW"
    assert packet["safe_to_auto_dispatch"] is False


def test_other_account_and_other_action_do_not_match(tmp_path):
    _write_job(tmp_path, refs=["business_entity:someone-else"])
    assert _check(tmp_path)["status"] == "NO_EXACT_CROSS_PLAN_MATCH"
    _write_job(tmp_path, plan="different_plan", action="hold",
               refs=["business_entity:entity-a"])
    assert _check(tmp_path)["status"] == "NO_EXACT_CROSS_PLAN_MATCH"


def test_untrusted_cross_plan_record_holds_instead_of_claiming_clear(tmp_path):
    queue = DepartmentWorkQueue(tmp_path)
    (queue.ready / "bad.json").write_text("{invalid")
    result = _check(tmp_path)
    assert result["status"] == "CROSS_PLAN_SCAN_INCOMPLETE_HOLD"
    out = build_predictive_decision_handoff(_decision(), tmp_path, as_of=NOW)
    assert out["held_count"] == 1
    assert out["ready_for_review_count"] == 0


def test_scan_limit_is_not_a_false_empty_queue(tmp_path, monkeypatch):
    import empire_os.predictive_decision_duplicate_guard as guard
    monkeypatch.setattr(guard, "MAX_RECORDS", 1)
    queue = DepartmentWorkQueue(tmp_path)
    for i in range(2):
        step = {
            "step_id": "other" + str(i),
            "goal_key": "other",
            "department_keys": ["strategy"],
            "target_component": "astra",
            "action": "unrelated",
            "authority": "observe",
            "evidence_refs": ["source:unrelated"],
        }
        queue.enqueue_step(plan_id="other", step=step)
    assert _check(tmp_path)["reason"] == "cross_plan_record_limit_exceeded"


def test_corrupt_or_symlink_other_plan_queue_is_held(tmp_path):
    queue = DepartmentWorkQueue(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.write_text("{}")
    (queue.ready / "linked.json").symlink_to(outside)
    assert _check(tmp_path)["status"] == "CROSS_PLAN_SCAN_INCOMPLETE_HOLD"
