"""Read-only proposal/queue-truth bridge for Predictive Decision Control.

Reuses ASTRA's *existing* DepartmentWorkQueue identifiers and step contract.
Never constructs the queue, enqueues work, claims leases or calls any worker.
Creating a review packet does not confer the authority to execute it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import re

from empire_os.department_work_queue import DepartmentWorkQueue


SCHEMA_VERSION = "empire.predictive_decision_handoff.v1"
PLAN_ID = "predictive_review_v1"
MAX_ITEMS = 500
MAX_RECORD_BYTES = 128 * 1024
MAX_SOURCE_AGE = timedelta(minutes=5)
LANES = ("ready", "running", "review", "done", "blocked", "failed")
# Allowlisted mappings are *proposal destinations*, not executable adapters.
# A proposal cannot be added to a live queue by this module.
ALLOWED = {
    "verify_decision_maker": ("sales_research", "sales_revenue",
                              "identity_enrichment"),
    "prepare_buyer_review": ("sales", "sales_revenue", "buyer_review"),
    "research_more": ("sales_research", "market_intelligence",
                      "predictive_cloud_opportunity_loop"),
    "enrich_identity": ("sales_research", "sales_revenue",
                        "identity_enrichment"),
}
SAFE_KEY = re.compile(r"buyer-[0-9a-f]{20}\Z")


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def _held(reason: str, *, decision_status: str = "UNKNOWN") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "EVIDENCE_HOLD",
        "decision_status": decision_status,
        "reason": reason,
        "mode": "OBSERVE",
        "plan_id": PLAN_ID,
        "candidate_count": 0,
        "ready_for_review_count": 0,
        "existing_work_count": 0,
        "held_count": 0,
        "candidates": [],
        "execution_authority": "none",
        "queue_read_only": True,
        "queue_mutated": False,
        "work_dispatched": False,
        "external_action_performed": False,
        "revenue_recognized": False,
    }


def _current_queue_truth(root: Path, work_id: str, action: str, step_id: str) -> dict[str, Any]:
    """Read exactly six potential queue state files, without instantiating a queue."""
    queue_root = root / "runtime/departments/work"
    # Never traverse a redirected queue root or state lane. Normal queue
    # directories are regular private directories, not symlinks.
    if queue_root.is_symlink():
        return {"status": "UNTRUSTED_HELD", "reason": "queue_root_unsafe"}
    records: list[tuple[str, Mapping[str, Any]]] = []
    for lane in LANES:
        lane_root = queue_root / lane
        if lane_root.is_symlink():
            return {"status": "UNTRUSTED_HELD", "reason": "queue_lane_unsafe"}
        path = lane_root / f"{work_id}.json"
        if not path.exists() and not path.is_symlink():
            continue
        try:
            if path.is_symlink() or not path.is_file():
                return {"status": "UNTRUSTED_HELD", "reason": "queue_path_unsafe"}
            if not 0 < path.stat().st_size <= MAX_RECORD_BYTES:
                return {"status": "UNTRUSTED_HELD", "reason": "queue_file_size_invalid"}
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, TypeError):
            return {"status": "UNTRUSTED_HELD", "reason": "queue_record_unreadable"}
        if (not isinstance(data, dict)
                or data.get("id") != work_id
                or data.get("plan_id") != PLAN_ID
                or data.get("step_id") != step_id
                or data.get("action") != action
                or data.get("status") != lane.upper()
                or data.get("authority") != "observe"):
            return {"status": "UNTRUSTED_HELD", "reason": "queue_record_identity_mismatch"}
        records.append((lane, data))

    if len(records) > 1:
        return {"status": "CONFLICT_HELD", "reason": "same_work_in_multiple_queue_lanes"}
    if not records:
        return {"status": "NOT_QUEUED", "reason": "new_review_proposal"}
    lane, data = records[0]
    if lane == "done":
        # This is *not* commercial fulfilment or recognized revenue. Work status
        # alone is insufficient to make a claim about the outcome.
        refs = data.get("result_evidence_refs")
        refs_present = isinstance(refs, list) and bool(refs) and all(
            isinstance(ref, str) and ref.strip() for ref in refs
        )
        return {
            "status": "COMPLETED_REVIEW_REQUIRED",
            "reason": ("task_done_evidence_present_requires_independent_verification"
                       if refs_present else "task_done_missing_verified_outcome"),
            "evidence_refs_present": bool(refs_present),
            "verified_commercial_outcome": False,
        }
    if lane in ("blocked", "failed"):
        return {"status": "ESCALATE_HOLD", "reason": f"existing_work_{lane}_no_auto_reopen"}
    return {"status": "ALREADY_IN_QUEUE", "reason": f"existing_work_{lane}"}


def _make_packet(item: Mapping[str, Any], root: Path) -> dict[str, Any]:
    task_id = item.get("task_id")
    action = item.get("recommended_action")
    owner = item.get("department")
    if not isinstance(task_id, str) or SAFE_KEY.fullmatch(task_id) is None:
        return {"status": "EVIDENCE_HOLD", "reason": "invalid_task_identity"}
    if not isinstance(action, str) or action not in ALLOWED:
        return {"status": "EVIDENCE_HOLD", "reason": "action_not_in_handoff_allowlist"}
    expected_owner, dept_key, component = ALLOWED[action]
    if owner != expected_owner:
        return {"status": "EVIDENCE_HOLD", "reason": "department_owner_mismatch"}
    if (item.get("source") != "canonical_revenue_command_queue"
            or item.get("lane") != "INTERNAL_PREPARATION"
            or item.get("can_prepare_internal_work") is not True
            or item.get("can_execute") is not False
            or item.get("execution_authority") != "none"
            or item.get("founder_gate_required") is not False
            or item.get("waiting_external") is not False
            or item.get("source_freshness") != "FRESH"):
        return {"status": "EVIDENCE_HOLD", "reason": "recommendation_authority_mismatch"}
    refs = item.get("evidence_refs")
    if (not isinstance(refs, list) or not refs or len(refs) > 24
            or not all(isinstance(ref, str) and 0 < len(ref) <= 250
                       and not any(ord(c) < 32 for c in ref) for ref in refs)):
        return {"status": "EVIDENCE_HOLD", "reason": "canonical_evidence_refs_missing"}

    work_id = DepartmentWorkQueue.deterministic_id(PLAN_ID, task_id)
    queue_truth = _current_queue_truth(root, work_id, action, task_id)
    cross_plan = None
    if queue_truth["status"] == "NOT_QUEUED":
        from empire_os.predictive_decision_duplicate_guard import review_cross_plan_duplicates
        cross_plan = review_cross_plan_duplicates(
            root, action=action, evidence_refs=refs, own_plan_id=PLAN_ID,
        )
        if cross_plan["status"] != "NO_EXACT_CROSS_PLAN_MATCH":
            queue_truth = {
                "status": cross_plan["status"],
                "reason": cross_plan["reason"],
            }
    work_step = {
        "step_id": task_id,
        "goal_key": "review_verified_commercial_bottleneck",
        "department_keys": [dept_key],
        "target_component": component,
        "action": action,
        "authority": "observe",
        "auto_dispatch_eligible": False,
        "founder_gate_required": False,
        "evidence_refs": list(dict.fromkeys(refs)),
        "intelligence_request": {
            "task": "canonical_evidence_review_only",
            "decision_task_id": task_id,
            "no_external_execution": True,
            "automatic_enqueue": False,
        },
        "memory_query": {
            "retrieval_only": True,
            "evidence_refs": list(dict.fromkeys(refs)),
        },
        "success_condition": (
            "Human-reviewable, referenced identity or buyer evidence; "
            "no outbound, delivery or payment"
        ),
        "rationale": "Prepare current canonical decision evidence for departmental review",
    }
    return {
        "task_id": task_id,
        "work_id": work_id,
        "owner": dept_key,
        "source_action": action,
        "current_work_status": queue_truth["status"],
        "queue_observation_reason": queue_truth["reason"],
        "cross_plan_duplicate_review": cross_plan,
        "work_step": work_step,
        "review_only": True,
        "enqueuing_authorized": False,
        "safe_to_auto_dispatch": False,
        "commercial_outcome_verified": False,
    }


def build_predictive_decision_handoff(
    decision: Mapping[str, Any],
    repo_root: str | Path,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Review packets and queue-state visibility, with zero filesystem mutations."""
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    now = now.astimezone(timezone.utc)
    status = str(decision.get("status") or "UNKNOWN")
    guard = (
        decision.get("schema_version") == "empire.predictive_decision_control.v1"
        and decision.get("status") == "REVIEW_READY"
        and decision.get("mode") == "OBSERVE"
        and decision.get("execution_authority") == "none"
        and decision.get("task_dispatch_performed") is False
        and decision.get("outbound_authorized") is False
        and decision.get("payment_authorized") is False
        and decision.get("database_mutation_authorized") is False
        and isinstance(decision.get("items"), list)
        and isinstance(decision.get("sources"), Mapping)
    )
    if not guard:
        return _held("decision_control_contract_not_review_ready", decision_status=status)
    sources = decision["sources"]
    if (sources.get("buyer_next_best_action") != "FRESH"
            or sources.get("revenue_command_queue") != "TRUSTED"):
        return _held("canonical_buyer_sources_not_fresh", decision_status=status)
    stamp = _time(decision.get("generated_at"))
    if stamp is None or not timedelta(0) <= now - stamp <= MAX_SOURCE_AGE:
        return _held("decision_control_stale_or_future", decision_status=status)
    rows = decision["items"]
    if len(rows) > MAX_ITEMS or decision.get("truncated_count") != 0:
        return _held("decision_set_incomplete_or_unbounded", decision_status=status)

    root = Path(repo_root).resolve(strict=False)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, Mapping):
            return _held("non_object_decision_task", decision_status=status)
        if item.get("lane") != "INTERNAL_PREPARATION":
            continue
        packet = _make_packet(item, root)
        task_id = packet.get("task_id")
        if task_id in seen:
            return _held("duplicate_task_identity", decision_status=status)
        if isinstance(task_id, str):
            seen.add(task_id)
        candidates.append(packet)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "REVIEW_READY" if candidates else "NO_ELIGIBLE_INTERNAL_WORK",
        "decision_status": status,
        "reason": "canonical_decision_review_packets_only",
        "mode": "OBSERVE",
        "plan_id": PLAN_ID,
        "candidate_count": len(candidates),
        "ready_for_review_count": sum(
            x.get("current_work_status") == "NOT_QUEUED" for x in candidates
        ),
        "existing_work_count": sum(
            x.get("current_work_status") in ("ALREADY_IN_QUEUE", "COMPLETED_REVIEW_REQUIRED")
            for x in candidates
        ),
        "held_count": sum(
            x.get("status") == "EVIDENCE_HOLD" or
            x.get("current_work_status") in ("UNTRUSTED_HELD", "CONFLICT_HELD", "ESCALATE_HOLD", "POSSIBLE_DUPLICATE_REVIEW", "CROSS_PLAN_SCAN_INCOMPLETE_HOLD")
            for x in candidates
        ),
        "candidates": candidates,
        "execution_authority": "none",
        "queue_read_only": True,
        "queue_mutated": False,
        "work_dispatched": False,
        "external_action_performed": False,
        "revenue_recognized": False,
    }
