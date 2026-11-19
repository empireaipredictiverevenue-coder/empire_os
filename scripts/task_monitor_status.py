#!/usr/bin/env python3
"""Inspect the existing, read-only completion-task monitor snapshot."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from empire_os.completion_task_monitor import OUTPUT, SCHEMA, _stamp


def _productivity_summary(monitor: dict) -> dict:
    """Expose ONLY exact, read-only candidates from the original monitor.

    An invalid review must not become an apparent assignment or grant.
    Existing monitor validity remains independent of advisory ranking.
    """
    driver = monitor.get("productivity_driver")
    if driver is None:
        return {
            "status": "UNAVAILABLE",
            "reason": "productivity_review_not_present",
            "execution_authority": "none",
            "work_dispatched": False,
        }
    if (not isinstance(driver, dict)
            or driver.get("schema_version") != "empire.productivity-driver.v1"
            or driver.get("status") != "READY_FOR_EXISTING_OWNER_REVIEW"
            or driver.get("mode") != "OBSERVE"
            or driver.get("execution_authority") != "none"
            or driver.get("work_dispatched") is not False
            or driver.get("founder_gates_preserved") is not True
            or driver.get("commercial_outcome_verified") is not False
            or driver.get("source_observed_at") != monitor.get("generated_at")
            or type(driver.get("review_candidate_count")) is not int
            or driver.get("review_candidate_count") != monitor.get("tracked_pending_count")
            or driver.get("identity_held_pending_count") != monitor.get("invalid_task_identity_hold_count", 0)):
        return {
            "status": "HELD",
            "reason": "productivity_review_contract_not_trusted",
            "execution_authority": "none",
            "work_dispatched": False,
        }
    items = monitor.get("items")
    reviews = driver.get("review_candidates")
    if (not isinstance(items, list)
            or len(items) != monitor.get("tracked_pending_count")
            or not isinstance(reviews, list) or len(reviews) > 12):
        return {
            "status": "HELD",
            "reason": "productivity_review_items_untrusted",
            "execution_authority": "none",
            "work_dispatched": False,
        }
    by_key = {
        row.get("task_key"): row for row in items if isinstance(row, dict)
    }
    if len(by_key) != len(items):
        return {
            "status": "HELD",
            "reason": "productivity_review_identity_untrusted",
            "execution_authority": "none",
            "work_dispatched": False,
        }
    selected = []
    seen = set()
    for row in reviews[:5]:
        if not isinstance(row, dict):
            return {"status": "HELD", "reason": "review_row_invalid", "execution_authority": "none", "work_dispatched": False}
        key = row.get("task_key")
        original = by_key.get(key)
        if (not isinstance(key, str) or key in seen or original is None
                or original.get("line") != row.get("checklist_line")
                or original.get("department") != row.get("owner")
                or original.get("state") != row.get("state")
                or row.get("approved_for_external_execution") is not False
                or row.get("customer_outcome_independently_verified") is not False
                or not isinstance(row.get("gate"), str)
                or not isinstance(row.get("required_proof"), str)):
            return {
                "status": "HELD", "reason": "review_identity_or_gate_untrusted",
                "execution_authority": "none", "work_dispatched": False,
            }
        seen.add(key)
        selected.append({
            "task_key": key,
            "checklist_line": original["line"],
            "task": original["task"],
            "existing_owner": original["department"],
            "state": original["state"],
            "required_proof": row["required_proof"],
            "gate": row["gate"],
            "priority_is_heuristic": True,
            "approved_for_external_execution": False,
        })
    return {
        "status": "AVAILABLE",
        "ranked_review_count": driver["review_candidate_count"],
        "invalid_task_identity_hold_count": driver["identity_held_pending_count"],
        "next_owner_reviews": selected,
        "claimed_customer_outcomes": 0,
        "work_dispatched": False,
        "execution_authority": "none",
    }


def inspect(root: Path, *, now: datetime | None = None) -> dict:
    clock = now or datetime.now(timezone.utc)
    path = root / OUTPUT
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        generated = _stamp(data.get("generated_at"))
    except (OSError, ValueError, TypeError, AttributeError):
        return {
            "status": "UNAVAILABLE",
            "reason": "task_monitor_missing_or_invalid",
            "execution_authority": "none",
        }
    if (data.get("schema_version") != SCHEMA
            or data.get("status") != "AVAILABLE"
            or data.get("execution_authority") != "none"
            or data.get("monitoring_not_dispatch") is not True
            or generated > clock + timedelta(minutes=2)
            or clock - generated > timedelta(minutes=20)):
        return {
            "status": "STALE_OR_UNTRUSTED",
            "last_observed_at": data.get("generated_at"),
            "execution_authority": "none",
        }
    return {
        "status": "AVAILABLE",
        "generated_at": data["generated_at"],
        "checklist": data["checklist"],
        "state_counts": data["state_counts"],
        "attention_count": data["attention_count"],
        "productivity_driver": _productivity_summary(data),
        "state_changes_this_cycle": data["new_state_transition_count"],
        "recent_transitions": data["recent_transitions"][-10:],
        "top_attention": [
            {
                "line": row["line"], "task": row["task"],
                "department": row["department"], "state": row["state"],
                "reason": row["attention_reason"],
                "next_evidence_step": row["next_evidence_step"],
            } for row in data["top_attention"][:10]
        ],
        "monitoring_not_dispatch": True,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    summary = inspect(Path(args.repo_root))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "AVAILABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
