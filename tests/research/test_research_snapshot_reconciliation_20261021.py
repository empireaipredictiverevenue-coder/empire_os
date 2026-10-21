"""Prove read-only comparison never forgives modified authority or evidence."""
from copy import deepcopy
from hashlib import sha256
import json

from scripts.review_agency_research_snapshot_drift_20261021 import compare_receipts


def _fixture(tmp_path):
    done = tmp_path / "runtime" / "departments" / "work" / "done"
    done.mkdir(parents=True)
    steps = []
    for index in range(5):
        agency = f"Agency {index}"
        review_key = f"{index:024x}"
        step_id = f"agency_review_{review_key}_review"
        task = {
            "agency": agency,
            "review_key": review_key,
            "snapshot_fingerprint": "b" * 64,
            "source_health_fingerprint": "c" * 64,
        }
        budget = {"requested_model_tokens": 0, "requested_external_cost_cents": 0}
        step = {
            "step_id": step_id, "authority": "observe",
            "action": "verify_original_agency_source_evidence",
            "target_component": "agency_source_evidence_review",
            "department_keys": ["marketing_growth"],
            "source_preflight_stage": "INTERNAL_AGENCY_SOURCE_PREFLIGHT_RESEARCH_REVIEW_REQUIRED",
            "intelligence_request": {
                "agency_source_evidence_review": task, "budget": budget
            },
        }
        steps.append(step)
        work_id = "dept_work_" + sha256(
            ("agency_research_source_proof_v1|" + step_id).encode()
        ).hexdigest()[:24]
        old_task = {**task, "snapshot_fingerprint": "a" * 64}
        item = {
            "id": work_id, "plan_id": "agency_research_source_proof_v1",
            "step_id": step_id, "status": "DONE", "authority": "observe",
            "action": step["action"], "target_component": step["target_component"],
            "department_keys": step["department_keys"],
            "intelligence_request": {
                "agency_source_evidence_review": old_task, "budget": budget,
            },
            "result": {
                "agency": agency, "existing_owner_review_key": review_key,
                "source_health_fingerprint": "c" * 64,
                "status": step["source_preflight_stage"],
                "first_pass_analysis_completed": True,
                "research_owner_accepted": False,
                "editorial_signoffs_verified": 0,
                "source_rights_verified": 0,
                "outbound_sent": False, "crm_writes": False,
                "execution_authority": "none",
            },
        }
        file = done / (work_id + ".json")
        file.write_text(json.dumps(item))
        file.chmod(0o600)
    plan = {
        "status": "FIVE_EXISTING_AGENCY_RESEARCH_ACTIONS_PREPARED_NOT_ENQUEUED",
        "ready_for_internal_queue": True,
        "plan_id": "agency_research_source_proof_v1",
        "steps": steps,
    }
    return plan, done


def test_five_immutable_done_receipts_differ_only_in_snapshot(tmp_path):
    plan, done = _fixture(tmp_path)
    before = {p.name: sha256(p.read_bytes()).hexdigest() for p in done.iterdir()}
    result = compare_receipts(plan, canonical_root=tmp_path)
    assert result["status"] == "FIVE_IMMUTABLE_RECEIPTS_SNAPSHOT_DRIFT_VERIFIED"
    assert result["historical_receipts_matched"] == 5
    assert not result["old_receipts_mutated"]
    assert result["new_source_tasks_enqueued"] == 0
    assert result["editorial_approvals_verified"] == 0
    assert all(r["changed_fields"] == ["snapshot_fingerprint"] for r in result["rows"])
    assert before == {p.name: sha256(p.read_bytes()).hexdigest() for p in done.iterdir()}


def test_changes_beyond_snapshot_are_never_reconciled(tmp_path):
    plan, _ = _fixture(tmp_path)
    altered = deepcopy(plan)
    altered["steps"][0]["intelligence_request"]["agency_source_evidence_review"]["review_key"] = "f" * 24
    result = compare_receipts(altered, canonical_root=tmp_path)
    assert result["status"] == "HELD_AGENCY_RESEARCH_SNAPSHOT_RECONCILIATION"
    assert result["reason"] == "DIFFERENCE_EXCEEDS_SNAPSHOT_VERSION_LINKAGE"


def test_invalid_authority_or_privacy_fails_closed(tmp_path):
    plan, done = _fixture(tmp_path)
    untrusted = deepcopy(plan)
    untrusted["steps"][1]["authority"] = "internal_write"
    assert compare_receipts(untrusted, canonical_root=tmp_path)["reason"] == "UNTRUSTED_CURRENT_PLAN_AUTHORITY"
    first = sorted(done.iterdir())[0]
    first.chmod(0o644)
    assert compare_receipts(plan, canonical_root=tmp_path)["reason"] == "HISTORICAL_DONE_RECEIPT_CUSTODY_INVALID"


def test_missing_work_and_unmodified_snapshots_do_not_count(tmp_path):
    plan, done = _fixture(tmp_path)
    sorted(done.iterdir())[0].unlink()
    assert compare_receipts(plan, canonical_root=tmp_path)["reason"] == "HISTORICAL_DONE_RECEIPT_MISSING"
    plan2, done2 = _fixture(tmp_path / "new")
    file = sorted(done2.iterdir())[0]
    item = json.loads(file.read_text())
    item["intelligence_request"]["agency_source_evidence_review"]["snapshot_fingerprint"] = "b" * 64
    file.write_text(json.dumps(item))
    file.chmod(0o600)
    assert compare_receipts(plan2, canonical_root=tmp_path / "new")["reason"] == "DIFFERENCE_EXCEEDS_SNAPSHOT_VERSION_LINKAGE"
