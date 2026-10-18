"""Read-only cross-plan duplicate check for EmpireOS department work."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LANES = ("ready", "running", "review", "done", "blocked", "failed")
MAX_RECORDS = 5000
MAX_FILE_BYTES = 131072


def _hold(reason: str) -> dict[str, Any]:
    return {
        "status": "CROSS_PLAN_SCAN_INCOMPLETE_HOLD",
        "reason": reason,
        "matching_work_ids": [],
        "matching_count": 0,
        "cross_plan_scan_complete": False,
    }


def _identities(refs: Any) -> set[str]:
    if not isinstance(refs, list):
        return set()
    return {
        ref for ref in refs
        if isinstance(ref, str)
        and len(ref) <= 250
        and ref.startswith(("business_entity:", "prospect:"))
        and len(ref.split(":", 1)[1].strip()) > 0
    }


def review_cross_plan_duplicates(
    root: Path,
    *,
    action: str,
    evidence_refs: list[str],
    own_plan_id: str,
) -> dict[str, Any]:
    """Return held on unverified/incomplete queue scans; never mutate."""
    from itertools import islice

    identities = _identities(evidence_refs)
    if not identities or not action:
        return _hold("canonical_identity_required")
    base = root / "runtime/departments/work"
    if base.is_symlink():
        return _hold("queue_root_symlink")
    matches: list[str] = []
    seen_ids: set[str] = set()
    inspected = 0

    for lane in LANES:
        folder = base / lane
        if folder.is_symlink():
            return _hold("queue_lane_symlink")
        try:
            paths = list(islice(folder.glob("*.json"), MAX_RECORDS - inspected + 1))
            if len(paths) + inspected > MAX_RECORDS:
                return _hold("cross_plan_record_limit_exceeded")
            inspected += len(paths)
            for path in paths:
                if path.is_symlink() or not path.is_file():
                    return _hold("cross_plan_file_not_regular")
                size = path.stat().st_size
                if not 0 < size <= MAX_FILE_BYTES:
                    return _hold("cross_plan_file_size_invalid")
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    return _hold("cross_plan_record_invalid")
                if (data.get("status") != lane.upper()
                        or not isinstance(data.get("plan_id"), str)
                        or not isinstance(data.get("id"), str)
                        or path.stem != data.get("id")
                        or not isinstance(data.get("evidence_refs"), list)):
                    return _hold("cross_plan_record_shape_invalid")
                if data["plan_id"] == own_plan_id or data.get("action") != action:
                    continue
                if not identities.intersection(_identities(data["evidence_refs"])):
                    continue
                job_id = data["id"]
                if job_id in seen_ids:
                    return _hold("same_cross_plan_work_in_multiple_lanes")
                seen_ids.add(job_id)
                matches.append(job_id)
        except (OSError, ValueError, TypeError, UnicodeError):
            return _hold("cross_plan_queue_unreadable")

    return {
        "status": ("POSSIBLE_DUPLICATE_REVIEW" if matches
                   else "NO_EXACT_CROSS_PLAN_MATCH"),
        "reason": ("matching_action_and_identity_in_other_plan" if matches
                   else "no_matching_action_and_identity_in_bounded_queue"),
        "matching_work_ids": sorted(matches)[:20],
        "matching_count": len(matches),
        "cross_plan_scan_complete": True,
    }
