"""Aggregate original Empire Coder job outcomes without exporting private records.

The canonical local Coder queue is the source for job state, kind and
verification verdict. Graphify receipts are a separate source of observations.
No causal graph improvement is claimed without a prospective control.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "empire.graphify.real_coder_outcome_evidence.v1"
STATES = ("pending", "running", "delegated", "completed", "failed")
KINDS = ("PLAN", "IMPLEMENT", "VERIFY", "NEXT_COMMAND")
VERDICTS = ("PASS", "PASS_WITH_WARNINGS", "FAIL")
_MAX_RECORD_SIZE = 262_144


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def classify_canonical_job(
    record: Mapping[str, Any], *, directory: str,
    earliest: datetime, latest: datetime,
) -> dict[str, Any] | None:
    """Classify only stable canonical fields; never return task/job identity."""
    if directory not in STATES or not isinstance(record, Mapping):
        return None
    kind = record.get("kind")
    status = record.get("status")
    if kind not in KINDS or status != directory.upper():
        return None
    updated = _when(record.get("updated_at"))
    if updated is None or not earliest <= updated <= latest:
        return None
    result = record.get("result")
    if not isinstance(result, Mapping):
        result = {}
    evidence = result.get("verification")
    verdict = (
        evidence.get("verdict")
        if isinstance(evidence, Mapping)
        else None
    )
    # An explicit verdict is evidence of Coder's own check, not proof of
    # external deployment or a causal Graphify benefit.
    if verdict not in VERDICTS:
        verdict = "UNKNOWN"
    applied = (
        result.get("applied") is True
        if kind == "IMPLEMENT" and directory == "completed" else False
    )
    return {
        "kind": kind,
        "status": directory,
        "verification_verdict": (
            verdict if kind in ("IMPLEMENT", "VERIFY")
            and directory == "completed" else "UNKNOWN"
        ),
        "implementation_applied_reported": applied,
        "created_time_present": _when(record.get("created_at")) is not None,
        "attempts_greater_than_one": (
            type(record.get("attempts")) is int
            and record["attempts"] > 1
        ),
    }


def summarize_canonical_coder_jobs(
    jobs_dir: str | Path, *, as_of: datetime,
    lookback_hours: int = 24,
    max_files: int = 100_000,
) -> dict[str, Any]:
    """Read original per-job JSON only, return anonymous aggregate counts."""
    if as_of.tzinfo is None:
        raise ValueError("an aware as_of timestamp is required")
    if type(lookback_hours) is not int or not 1 <= lookback_hours <= 24 * 90:
        raise ValueError("invalid observation window")
    if type(max_files) is not int or not 1 <= max_files <= 250_000:
        raise ValueError("invalid file cap")
    root = Path(jobs_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("trusted existing Coder job directory required")
    as_of = as_of.astimezone(timezone.utc)
    earliest = as_of - timedelta(hours=lookback_hours)
    totals = Counter()
    verdicts = Counter()
    statuses = Counter()
    skipped = Counter()
    seen: set[str] = set()
    examined = 0
    for directory in STATES:
        folder = root / directory
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("untrusted canonical job state directory")
        for item in folder.glob("*.json"):
            examined += 1
            if examined > max_files:
                raise ValueError("canonical job inventory exceeds review limit")
            try:
                if item.is_symlink() or not item.is_file():
                    skipped["unsafe_job_file"] += 1
                    continue
                size = item.stat().st_size
            except OSError:
                # Canonical worker may atomically move the job while a
                # read-only review is enumerating its former directory.
                skipped["concurrently_moved_job"] += 1
                continue
            if not 0 < size <= _MAX_RECORD_SIZE:
                skipped["invalid_job_file_length"] += 1
                continue
            try:
                record = json.loads(item.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                skipped["unreadable_job_file"] += 1
                continue
            if not isinstance(record, dict):
                skipped["invalid_record"] += 1
                continue
            # Identity used only in memory for double-count prevention;
            # never included in the output.
            identifier = record.get("id")
            if (not isinstance(identifier, str)
                    or len(identifier) > 160
                    or item.stem != identifier):
                skipped["invalid_canonical_identity"] += 1
                continue
            if identifier in seen:
                skipped["duplicate_job_identity"] += 1
                continue
            seen.add(identifier)
            item_time = _when(record.get("updated_at"))
            if item_time is None:
                skipped["unknown_time"] += 1
                continue
            if not earliest <= item_time <= as_of:
                continue
            classified = classify_canonical_job(
                record, directory=directory,
                earliest=earliest, latest=as_of,
            )
            if classified is None:
                skipped["unclassified_recent_job"] += 1
                continue
            kind = classified["kind"]
            state = classified["status"]
            totals[f"{kind}/{state}"] += 1
            statuses[state] += 1
            if kind in ("VERIFY", "IMPLEMENT") and state == "completed":
                verdicts[f"{kind}/{classified['verification_verdict']}"] += 1
            if classified["implementation_applied_reported"]:
                statuses["IMPLEMENT_APPLIED_REPORTED"] += 1
            if classified["attempts_greater_than_one"]:
                statuses["MULTI_ATTEMPT_RECORDS"] += 1
    verified = {
        key: value for key, value in sorted(verdicts.items())
    }
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "source": "EXISTING_CANONICAL_CODER_JOB_RECORDS",
        "as_of_utc": as_of.isoformat(),
        "lookback_hours": lookback_hours,
        "reviewed_job_files": examined,
        "classified_recent_jobs": sum(totals.values()),
        "status_by_kind": dict(sorted(totals.items())),
        "job_state_totals": dict(sorted(statuses.items())),
        "coder_verification_verdicts": verified,
        "excluded_or_unclassified": dict(sorted(skipped.items())),
        "prepatch_observation_join": "NO_JOB_LEVEL_LINK_IN_HISTORICAL_LOGS",
        "original_task_ids_exported": False,
        "customer_data_exported": False,
        "verified_graphify_engineering_uplift": None,
        "verified_graphify_commercial_uplift": None,
    }
