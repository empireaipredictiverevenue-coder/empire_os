"""Durable pre-identity signal inbox for specialist acquisition sources.

Signals such as permits, Reddit demand posts, weather alerts and municipal
events are evidence of commercial opportunity, not canonical business
identities. This store retains them without creating fake prospects.

No outreach, payment, revenue recognition or authority expansion occurs here.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.locale_intelligence import resolve_locale
from empire_os.permit_source_revision import (
    trusted_permit_match, refresh_trusted_permit_event,
)
from empire_os.dobnow_event_revision import (
    trusted_dobnow_match, refresh_dobnow_event,
)

ROOT = Path("/srv/empire_os/runtime/acquisition")
INBOX = ROOT / "signal_inbox.json"
LOCK = ROOT / "signal_inbox.lock"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, Mapping):
        return dict(candidate)
    if is_dataclass(candidate):
        return asdict(candidate)
    return {
        key: getattr(candidate, key, None)
        for key in (
            "name", "email", "phone", "niche", "metro", "state",
            "country_code", "language_code", "source_language", "timezone",
            "details", "source", "lead_score", "url", "raw",
        )
    }


def _fingerprint(row: Mapping[str, Any]) -> str:
    raw = row.get("raw")
    material = {
        "source": str(row.get("source") or "").strip().lower(),
        "url": str(row.get("url") or "").strip(),
        "name": str(row.get("name") or "").strip().lower(),
        "metro": str(row.get("metro") or "").strip().lower(),
        "niche": str(row.get("niche") or "").strip().lower(),
        "raw_id": (
            str(raw.get("id") or raw.get("job__") or raw.get("job_filing_number")
                or raw.get("permalink") or "")
            if isinstance(raw, Mapping)
            else ""
        ),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load() -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(INBOX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


MAX_OBSERVE_BATCH = 400


def _merge_signal(data: dict, row: dict, quality: Any) -> dict[str, Any]:
    """One canonical signal mutation, shared by one-at-a-time and batch paths."""
    locale = resolve_locale(row)
    fp = _fingerprint(row)
    existing = data.get(fp)
    if not isinstance(existing, dict) and row.get("source") == "permits_nyc":
        existing = next(
            (prior for prior in data.values()
             if isinstance(prior, dict) and trusted_permit_match(prior, row)), None,
        )
    if not isinstance(existing, dict) and row.get("source") == "permits_nyc_dobnow":
        existing = next(
            (prior for prior in data.values()
             if isinstance(prior, dict) and trusted_dobnow_match(prior, row)), None,
        )
    revision = {"event_revision_added": False}
    if isinstance(existing, dict):
        seen_at = _now()
        existing["last_seen_at"] = seen_at
        existing["seen_count"] = int(existing.get("seen_count") or 1) + 1
        if row.get("source") == "permits_nyc":
            revision = refresh_trusted_permit_event(
                existing, row, observed_at=seen_at,
            )
        elif row.get("source") == "permits_nyc_dobnow":
            revision = refresh_dobnow_event(
                existing, row, observed_at=seen_at,
            )
        decision = "updated_source_event" if revision["event_revision_added"] else "matched"
        record = existing
    else:
        q = (quality.to_evidence()
             if quality is not None and hasattr(quality, "to_evidence")
             else {})
        stamp = _now()
        record = {
            "signal_id": fp,
            "status": "unresolved",
            "created_at": stamp,
            "last_seen_at": stamp,
            "seen_count": 1,
            "source": str(row.get("source") or "").strip(),
            "name": str(row.get("name") or "").strip(),
            "niche": str(row.get("niche") or "").strip(),
            "metro": str(row.get("metro") or "").strip(),
            "state": str(row.get("state") or "").strip(),
            "phone": str(row.get("phone") or "").strip(),
            "email": str(row.get("email") or "").strip(),
            "url": str(row.get("url") or "").strip(),
            "details": str(row.get("details") or "").strip(),
            "lead_score": row.get("lead_score"),
            "raw": row.get("raw"),
            "locale": locale.as_dict(),
            "quality": q,
            "entity_id": None,
            "prospect_id": None,
            "resolution_attempts": 0,
            "next_resolution_at": stamp,
            "execution_authority": "none",
        }
        data[fp] = record
        decision = "created"
    return {
        "decision": decision,
        "signal_id": record.get("signal_id") or fp,
        "source_event_revision_added": revision["event_revision_added"],
        "status": record.get("status"),
        "source": record.get("source"),
        "locale": record.get("locale"),
        "execution_authority": "none",
    }


def enqueue_signals_batch(candidates: list[Any], *,
                          qualities: list[Any] | None = None) -> list[dict[str, Any]]:
    """One existing inbox lock / one 0600 atomic file write for <=400 signals.

    This is not a database or sales writer. Results are returned in input order.
    """
    if not isinstance(candidates, list) or len(candidates) > MAX_OBSERVE_BATCH:
        raise ValueError("UNBOUNDED_SIGNAL_BATCH")
    if qualities is not None and (
        not isinstance(qualities, list) or len(qualities) != len(candidates)
    ):
        raise ValueError("INVALID_SIGNAL_BATCH_QUALITIES")
    if not candidates:
        return []
    rows = [_data(candidate) for candidate in candidates]
    if len(rows) > 1 and any(row.get("source") != "permits_nyc_dobnow" for row in rows):
        raise ValueError("BATCH_LIMITED_TO_DOBNOW_SOURCE_EVENTS")
    if INBOX.is_symlink() or LOCK.is_symlink():
        raise ValueError("UNSAFE_SIGNAL_INBOX_PATH")
    ROOT.mkdir(parents=True, exist_ok=True)
    LOCK.touch(exist_ok=True)
    with LOCK.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            # Fail closed on corrupt data; never truncate a shared live store.
            if INBOX.exists():
                data = json.loads(INBOX.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("UNTRUSTED_SIGNAL_INBOX_OBJECT")
            else:
                data = {}
            results = [
                _merge_signal(data, row, qualities[i] if qualities is not None else None)
                for i, row in enumerate(rows)
            ]
            import os
            import tempfile
            fd, temp = tempfile.mkstemp(prefix=".signal_inbox.",suffix=".tmp",
                                        dir=ROOT)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as writer:
                    os.fchmod(writer.fileno(), 0o600)
                    json.dump(data, writer, indent=2, sort_keys=True, default=str)
                    writer.write("\n")
                    writer.flush()
                    os.fsync(writer.fileno())
                os.replace(temp, INBOX)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
            return results
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def enqueue_signal(candidate: Any, *, quality: Any = None) -> dict[str, Any]:
    return enqueue_signals_batch([candidate], qualities=[quality])[0]



def snapshot() -> dict[str, Any]:
    data = _load()
    statuses: dict[str, int] = {}
    sources: dict[str, int] = {}
    for row in data.values():
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "unknown")
        source = str(row.get("source") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        sources[source] = sources.get(source, 0) + 1
    return {
        "total": len(data),
        "by_status": statuses,
        "by_source": sources,
        "execution_authority": "none",
    }
