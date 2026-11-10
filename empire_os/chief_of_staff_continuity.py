"""Stateful review adapter for the *existing* EmpireOS Chief of Staff.

No separate agent, scheduler, database, queue or external authority is created.
Current EmpireOS founder directives are the canonical memory. Previous reports
are optional derived observations used only to suppress repeated attention.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping

from empire_os.executive_founder_status import read_executive_founder_status

SCHEMA = "empire.chief_of_staff.continuity.v1"
DIRECTIVES_SCHEMA = "empire.founder_directives.v1"
MAX_SIZE = 750_000
MAX_AGE = timedelta(hours=72)
MAX_PERSISTED_AGE = timedelta(days=365)
ID_RE = re.compile(r"^directive_[a-f0-9]{32}$")
ACTIVE = frozenset({
    "captured", "planning", "planned", "implementation_ready", "implementing",
    "implementation_failed", "verification_required", "verifying",
    "verification_failed", "founder_gate", "plan_failed",
})
ALL_STATUSES = ACTIVE | {"implemented", "rejected"}
ORDER = {
    "verification_failed": 0,
    "implementation_failed": 1,
    "plan_failed": 2,
    "founder_gate": 3,
    "verification_required": 4,
    "implementing": 5,
    "implementation_ready": 6,
    "verifying": 7,
    "planned": 8,
    "planning": 9,
    "captured": 10,
}
AREAS = {"revenue": 0, "search": 1, "product": 2, "design": 3}
NEXT = {
    "verification_failed": "RETURN_FAILED_VERIFICATION_TO_EXISTING_OWNER",
    "implementation_failed": "RETURN_FAILED_IMPLEMENTATION_TO_EXISTING_OWNER",
    "plan_failed": "RETURN_FAILED_PLAN_TO_EXISTING_OWNER",
    "founder_gate": "REVIEW_RECORDED_FOUNDER_GATE",
    "verification_required": "REQUEST_EXISTING_OWNER_VERIFICATION",
    "implementing": "CHECK_EXISTING_OWNER_PROGRESS",
    "implementation_ready": "CHECK_OWNER_AND_CURRENT_EXECUTION_AUTHORITY",
    "verifying": "CHECK_EXISTING_VERIFICATION_RESULT",
    "planned": "CHECK_EXISTING_OWNER_PLAN",
    "planning": "AWAIT_EXISTING_OWNER_PLAN",
    "captured": "CHECK_EXISTING_DIRECTIVE_INTAKE",
}


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _read_json(path: Path) -> Mapping[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        size = path.stat().st_size
        if not 0 < size <= MAX_SIZE:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _index(index: Mapping[str, Any] | None, now: datetime) -> list[dict[str, Any]] | None:
    if not index or index.get("schema_version") != DIRECTIVES_SCHEMA:
        return None
    if index.get("execution_mode") != "OBSERVE" or index.get("automatic_production_execution") is not False:
        return None
    stamp = _time(index.get("observed_at"))
    if stamp is None or not timedelta(0) <= now - stamp <= MAX_PERSISTED_AGE:
        return None
    rows = index.get("latest")
    count = index.get("directive_count")
    if not isinstance(rows, list) or len(rows) > 100 or type(count) is not int or count < len(rows):
        return None
    seen: set[str] = set()
    result = []
    for row in rows:
        if not isinstance(row, dict):
            return None
        ref, status = row.get("id"), row.get("status")
        if not isinstance(ref, str) or not ID_RE.fullmatch(ref) or ref in seen:
            return None
        if status not in ALL_STATUSES:
            return None
        if row.get("authority") not in {"internal_plan", "founder_gate"}:
            return None
        if status == "founder_gate" and row.get("authority") != "founder_gate":
            return None
        priority, category = row.get("priority"), row.get("category")
        if type(priority) is not int or not 0 <= priority <= 100:
            return None
        if not isinstance(category, str) or not re.fullmatch(r"[a-z_]{1,32}", category):
            return None
        title = row.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 20000:
            return None
        seen.add(ref)
        result.append({
            "directive_id": ref,
            "title": " ".join(title.split())[:125],
            "category": category,
            "priority": priority,
            "status": status,
            "authority": row["authority"],
        })
    return result


def _prior_states(previous: Mapping[str, Any] | None, now: datetime) -> dict[str, str] | None:
    if previous is None:
        return None
    if previous.get("schema_version") != SCHEMA or previous.get("mode") != "OBSERVE":
        return None
    stamp = _time(previous.get("generated_at"))
    if stamp is None or stamp > now:
        return None
    states = previous.get("observed_states")
    if not isinstance(states, dict) or len(states) > 100:
        return None
    if any(not isinstance(k, str) or not ID_RE.fullmatch(k) or v not in ALL_STATUSES
           for k, v in states.items()):
        return None
    return dict(states)


def build_continuity_review(
    repo_root: Path,
    *,
    as_of: datetime | None = None,
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine current canonical evidence with prior derived observations; never dispatch."""
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    now = now.astimezone(timezone.utc)
    root = Path(repo_root)
    executive = read_executive_founder_status(
        root / "runtime/astra/executive_latest.json", as_of=now
    )
    directives = _read_json(root / "runtime/founder_directives/latest.json")
    rows = _index(directives, now)
    source_stamp = _time(directives.get("observed_at")) if directives else None
    index_fresh = source_stamp is not None and now - source_stamp <= MAX_AGE
    baseline = _prior_states(previous, now)
    result = {
        "schema_version": SCHEMA,
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "execution_authority": "none",
        "source_of_truth": "existing_founder_directives_and_astra",
        "status": "EVIDENCE_HOLD",
        "directive_evidence": ("UNAVAILABLE" if rows is None else
                               "FRESH_INDEX" if index_fresh else "PERSISTED_INDEX_REVIEW"),
        "astra_evidence": executive["status"],
        "active_count_in_latest_window": None,
        "observed_states": {},
        "top_three_follow_ups": [],
        "changed_attention": [],
        "change_basis": "NO_PRIOR_BASELINE" if previous is None else "PRIOR_UNTRUSTED",
        "dispatch_attempted": False,
        "notifications_sent": False,
        "outbound_authorized": False,
        "production_release_authorized": False,
        "revenue_verified_by_this_review": False,
    }
    if rows is None or not executive.get("available"):
        return result
    states = {r["directive_id"]: r["status"] for r in rows}
    result["observed_states"] = states
    active = [r for r in rows if r["status"] in ACTIVE]
    active.sort(key=lambda r: (ORDER[r["status"]], AREAS.get(r["category"], 9),
                               -r["priority"], r["directive_id"]))
    result["top_three_follow_ups"] = [
        {**r, "next_action": NEXT[r["status"]],
         "owner": "EXISTING_OWNER_TO_VERIFY",
         "source_ref": f"founder_directives/latest.json#{r['directive_id']}",
         "dispatchable": False, "founder_approval_granted": False}
        for r in active[:3]
    ]
    result["active_count_in_latest_window"] = len(active)
    if previous is None:
        result["change_basis"] = "BASELINE_ONLY"
    elif baseline is None:
        # Invalid/missing previous reports must never trigger a notification burst.
        result["change_basis"] = "PRIOR_UNTRUSTED"
    else:
        result["change_basis"] = "VERIFIED_PRIOR_REPORT"
        changed = [
            {**r, "previous_status": baseline.get(r["directive_id"]),
             "next_action": NEXT[r["status"]], "dispatchable": False}
            for r in active
            if baseline.get(r["directive_id"]) != r["status"]
        ]
        result["changed_attention"] = changed[:3]
    result["status"] = ("REVIEW_WITH_PERSISTED_DIRECTIVES" if not index_fresh else
                        "REVIEW_ONLY" if executive["status"] == "REVIEW_ONLY_NO_RELEASE_AUTHORITY"
                        else "REVIEW_WITH_OPERATIONAL_EVIDENCE_HOLD")
    return result


def run_tick(repo_root: Path, *, as_of: datetime | None = None) -> dict[str, Any]:
    """One persistent, internally safe decision tick, suitable for existing owner scheduler.

    This updates only the derived Chief of Staff checkpoint. Never dispatches
    jobs, emails, notifications, or even writes canonical directives. A held
    report does not overwrite the last trusted checkpoint.
    """
    import fcntl
    import os
    from uuid import uuid4

    folder = Path(repo_root) / "runtime" / "chief_of_staff"
    if folder.is_symlink():
        raise ValueError("checkpoint parent is symlink")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    file = folder / "continuity_latest.json"
    lock = folder / ".continuity.lock"
    if file.is_symlink() or lock.is_symlink():
        raise ValueError("checkpoint or lock is symlink")
    # One writer per local checkpoint even when the existing timer overlaps.
    with lock.open("a+") as guard:
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        previous = _read_json(file)
        # Existing file becoming corrupt is not an alert opportunity.
        report = build_continuity_review(repo_root, as_of=as_of, previous=previous)
        if report["status"] not in {"REVIEW_ONLY", "REVIEW_WITH_OPERATIONAL_EVIDENCE_HOLD",
                                    "REVIEW_WITH_PERSISTED_DIRECTIVES"}:
            return report
        temp = folder / (".continuity." + uuid4().hex + ".tmp")
        try:
            with temp.open("x", encoding="utf-8") as stream:
                os.chmod(temp, 0o600)
                json.dump(report, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temp.replace(file)
        finally:
            temp.unlink(missing_ok=True)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Existing Chief of Staff continuity review (OBSERVE)")
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--previous", type=Path, help="Optional previous derived review for change detection")
    parser.add_argument("--tick", action="store_true", help="Run one durable internal observation tick (no dispatch)")
    args = parser.parse_args()
    if args.tick and args.previous:
        parser.error("--tick and --previous are mutually exclusive")
    if args.tick:
        result = run_tick(args.repo_root)
    else:
        previous = _read_json(args.previous) if args.previous else None
        if args.previous and previous is None:
            raise SystemExit("previous report unavailable or invalid; no changed-attention calculation")
        result = build_continuity_review(args.repo_root, previous=previous)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
