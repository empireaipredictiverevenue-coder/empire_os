"""Conservative in-memory-only Brave Search, with durable request-count ledger.

No result persistence, caching, snippets, domain lists, company names,
model-learning, contact or CRM change. Meter reserves before an attempted
search; failures consume the local allowance too.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import contextlib
import fcntl
import json
import os
import tempfile

SCHEMA = "empire.a2a.brave_transient_budget_ledger.v1"
MAX_PER_MONTH = 100
MAX_PER_DAY = 2
PRESETS = {
    "tampa_roofing": "roofing contractors Tampa Florida",
    "little_rock_hvac": "HVAC contractors Little Rock Arkansas",
    "nyc_general_contractors": "general contractors New York City",
}


def _utc(now: datetime | None) -> datetime:
    at = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("UTC_AWARE_CLOCK_REQUIRED")
    return at.astimezone(timezone.utc)


def reserve_single_request(
    root: Path,
    *, now: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Atomic local request-counter preflight. Never returns source records."""
    at = _utc(now)
    if type(dry_run) is not bool:
        raise ValueError("INVALID_DRY_RUN")
    if root.is_symlink():
        raise ValueError("UNSAFE_BUDGET_DIRECTORY")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    ledger = root / "brave_transient_request_counters_v1.json"
    lockfile = root / ".brave_transient_request_counters_v1.lock"
    if ledger.is_symlink() or lockfile.is_symlink():
        raise ValueError("UNSAFE_BUDGET_LEDGER")
    with lockfile.open("a+", encoding="utf-8") as lock:
        os.chmod(lockfile, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        existing: dict[str,Any] = {}
        if ledger.exists():
            if ledger.stat().st_size > 5000:
                raise ValueError("CORRUPT_OR_OVERSIZED_REQUEST_LEDGER")
            existing = json.loads(ledger.read_text(encoding="utf-8"))
            if (not isinstance(existing, dict)
                    or existing.get("schema_version") != SCHEMA
                    or type(existing.get("monthly_requests")) is not int
                    or type(existing.get("daily_requests")) is not int
                    or not 0 <= existing["monthly_requests"] <= MAX_PER_MONTH
                    or not 0 <= existing["daily_requests"] <= MAX_PER_DAY):
                raise ValueError("UNTRUSTED_REQUEST_LEDGER")
        day = at.date().isoformat()
        month = day[:7]
        oldmonth = existing.get("utc_month")
        oldday = existing.get("utc_day")
        if oldmonth and (not isinstance(oldmonth,str) or oldmonth > month):
            raise ValueError("BUDGET_CLOCK_ROLLBACK_MONTH")
        if oldday and (not isinstance(oldday,str) or oldday > day):
            raise ValueError("BUDGET_CLOCK_ROLLBACK_DAY")
        monthly = existing["monthly_requests"] if oldmonth == month else 0
        daily = existing["daily_requests"] if oldday == day else 0
        allowed = monthly < MAX_PER_MONTH and daily < MAX_PER_DAY
        result = {
            "schema_version": SCHEMA,
            "utc_month": month,
            "utc_day": day,
            "monthly_requests": monthly + (1 if allowed and not dry_run else 0),
            "daily_requests": daily + (1 if allowed and not dry_run else 0),
            "monthly_limit": MAX_PER_MONTH,
            "daily_limit": MAX_PER_DAY,
            "request_reserved": allowed and not dry_run,
            "request_permitted": allowed,
            "dry_run": dry_run,
            "search_results_stored": False,
            "query_text_stored": False,
            "derived_buyer_leads_stored": False,
            "buyer_scout_dispatches": 0,
        }
        if not allowed:
            return result
        if dry_run:
            return result
        durable = {k:result[k] for k in ("schema_version","utc_month","utc_day",
                                         "monthly_requests","daily_requests")}
        fd, tmp = tempfile.mkstemp(prefix=".brave_counter_", dir=root)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(durable, output, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(tmp, ledger)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return result
