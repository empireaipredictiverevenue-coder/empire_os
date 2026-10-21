"""Read-only, exact delta audit for the existing agency Research receipts.

Never rewrites canonical DONE receipts, enqueues jobs, signs an editorial
decision, or creates a duplicate Research queue. Uses the original agency
owner's plan generator in its own worktree and verifies immutable evidence.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Mapping

OWNER = Path("/home/ubuntu/empire_worktrees/agency_acquisition_conversion_20261020")
CANONICAL = Path("/srv/empire_os")
PLAN_ID = "agency_research_source_proof_v1"
KEY = "agency_source_evidence_review"
BUDGET = {"requested_model_tokens": 0, "requested_external_cost_cents": 0}


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "empire.research.agency_snapshot_delta.v1",
        "status": "HELD_AGENCY_RESEARCH_SNAPSHOT_RECONCILIATION",
        "reason": reason, "historical_receipts_matched": 0,
        "new_source_tasks_enqueued": 0, "old_receipts_mutated": False,
        "editorial_approvals_verified": 0, "source_rights_verified": 0,
        "execution_authority": "none", "rows": [],
    }


def compare_receipts(plan: Mapping[str, Any], *, canonical_root: Path) -> dict[str, Any]:
    """Return exact digest-linked receipt differences; never promote old work."""
    if (not isinstance(plan, Mapping)
            or plan.get("status") != "FIVE_EXISTING_AGENCY_RESEARCH_ACTIONS_PREPARED_NOT_ENQUEUED"
            or plan.get("plan_id") != PLAN_ID
            or plan.get("ready_for_internal_queue") is not True
            or not isinstance(plan.get("steps"), list)
            or len(plan["steps"]) != 5):
        return _hold("CURRENT_ORIGINAL_RESEARCH_PLAN_NOT_READY")
    root = canonical_root / "runtime/departments/work/done"
    if (canonical_root.is_symlink() or root.is_symlink()
            or not root.is_dir()):
        return _hold("CANONICAL_DONE_DIRECTORY_UNAVAILABLE")
    rows = []
    seen = set()
    for step in plan["steps"]:
        if not isinstance(step, Mapping):
            return _hold("INVALID_RESEARCH_STEP")
        expected = step.get("intelligence_request")
        step_id = step.get("step_id")
        if (not isinstance(expected, Mapping)
                or not isinstance(step_id, str)
                or not step_id.startswith("agency_review_")
                or step_id in seen
                or step.get("authority") != "observe"
                or step.get("action") != "verify_original_agency_source_evidence"
                or step.get("target_component") != KEY
                or step.get("department_keys") != ["marketing_growth"]
                or expected.get("budget") != BUDGET):
            return _hold("UNTRUSTED_CURRENT_PLAN_AUTHORITY")
        seen.add(step_id)
        task = expected.get(KEY)
        if not isinstance(task, Mapping):
            return _hold("CURRENT_SOURCE_CONTRACT_MISSING")
        work_id = "dept_work_" + sha256(
            (PLAN_ID + "|" + step_id).encode()
        ).hexdigest()[:24]
        receipt_file = root / (work_id + ".json")
        if receipt_file.is_symlink() or not receipt_file.is_file():
            return _hold("HISTORICAL_DONE_RECEIPT_MISSING")
        meta = receipt_file.stat()
        if (not stat.S_ISREG(meta.st_mode)
                or meta.st_mode & 0o077
                or not 100 <= meta.st_size <= 400000):
            return _hold("HISTORICAL_DONE_RECEIPT_CUSTODY_INVALID")
        original_bytes = receipt_file.read_bytes()
        try:
            item = json.loads(original_bytes)
        except (json.JSONDecodeError, UnicodeError):
            return _hold("HISTORICAL_DONE_RECEIPT_UNREADABLE")
        old = item.get("intelligence_request", {}).get(KEY, {})
        old_budget = item.get("intelligence_request", {}).get("budget")
        result = item.get("result")
        if (not isinstance(old, Mapping)
                or not isinstance(result, Mapping)
                or old_budget != BUDGET
                or item.get("id") != work_id
                or item.get("plan_id") != PLAN_ID
                or item.get("step_id") != step_id
                or item.get("status") != "DONE"
                or item.get("authority") != "observe"
                or item.get("target_component") != KEY
                or item.get("action") != "verify_original_agency_source_evidence"
                or item.get("department_keys") != ["marketing_growth"]
                or result.get("first_pass_analysis_completed") is not True
                or result.get("research_owner_accepted") is not False
                or result.get("source_rights_verified") != 0
                or result.get("editorial_signoffs_verified") != 0
                or result.get("outbound_sent") is not False
                or result.get("crm_writes") is not False
                or result.get("execution_authority") != "none"):
            return _hold("HISTORICAL_RECEIPT_AUTHORITY_UNVERIFIED")
        differences = sorted(k for k in set(old) | set(task)
                             if old.get(k) != task.get(k))
        if (differences != ["snapshot_fingerprint"]
                or old.get("source_health_fingerprint") != task.get("source_health_fingerprint")
                or result.get("source_health_fingerprint") != task.get("source_health_fingerprint")
                or result.get("agency") != task.get("agency")
                or result.get("existing_owner_review_key") != task.get("review_key")
                or result.get("status") != step.get("source_preflight_stage")):
            return _hold("DIFFERENCE_EXCEEDS_SNAPSHOT_VERSION_LINKAGE")
        rows.append({
            "agency": task["agency"],
            "original_work_id": work_id,
            "historical_status": "DONE_SOURCE_PREFLIGHT_ONLY",
            "historical_receipt_sha256": sha256(original_bytes).hexdigest(),
            "old_snapshot_fingerprint": old["snapshot_fingerprint"],
            "current_snapshot_fingerprint": task["snapshot_fingerprint"],
            "source_health_fingerprint": task["source_health_fingerprint"],
            "changed_fields": differences,
            "historical_receipt_is_current_approval": False,
        })
    if len({r["agency"] for r in rows}) != 5:
        return _hold("DUPLICATE_AGENCY_IDENTITY")
    return {
        **_hold(None),
        "status": "FIVE_IMMUTABLE_RECEIPTS_SNAPSHOT_DRIFT_VERIFIED",
        "reason": None, "historical_receipts_matched": 5,
        "rows": sorted(rows, key=lambda r: r["agency"]),
        "next_owner": "existing_search_and_market_intelligence",
        "next_action": "RECHECK_CURRENT_SOURCE_SNAPSHOT_AND_VERSION_NEW_RESEARCH_PREFLIGHT_WITH_AUTHENTIC_SIGNED_EDITORIAL_REVIEW",
    }


def load_existing_owner_plan() -> Mapping[str, Any]:
    """The existing owner's generator remains authoritative; no shadow planner."""
    if OWNER.is_symlink() or not OWNER.is_dir():
        raise ValueError("ORIGINAL_RESEARCH_OWNER_MISSING")
    statement = (
        "import json\n"
        "from pathlib import Path\n"
        "from scripts.review_agency_department_actions_20261020 import _current_snapshot\n"
        "from empire_os.agency_research_department_action_20261020 import plan_original_agency_research_actions\n"
        "root=Path.cwd()\n"
        "print(json.dumps(plan_original_agency_research_actions(root,snapshot_fingerprint=_current_snapshot(root) or '')))\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", statement],
        cwd=OWNER, text=True, capture_output=True, timeout=25,
        check=False,
    )
    if result.returncode or len(result.stdout) > 500000:
        raise ValueError("EXISTING_OWNER_PLAN_UNAVAILABLE")
    return json.loads(result.stdout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        outcome = compare_receipts(load_existing_owner_plan(), canonical_root=CANONICAL)
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        outcome = _hold("ORIGINAL_OWNER_OR_CANONICAL_RECEIPT_UNAVAILABLE")
    print(json.dumps(outcome, sort_keys=True))
    return 0 if outcome["status"] == "FIVE_IMMUTABLE_RECEIPTS_SNAPSHOT_DRIFT_VERIFIED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
