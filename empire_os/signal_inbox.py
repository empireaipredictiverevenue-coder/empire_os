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
            str(raw.get("id") or raw.get("job__") or raw.get("permalink") or "")
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


def enqueue_signal(candidate: Any, *, quality: Any = None) -> dict[str, Any]:
    ROOT.mkdir(parents=True, exist_ok=True)
    LOCK.touch(exist_ok=True)
    row = _data(candidate)
    locale = resolve_locale(row)
    fp = _fingerprint(row)

    with LOCK.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            data = _load()
            existing = data.get(fp)
            if isinstance(existing, dict):
                existing["last_seen_at"] = _now()
                existing["seen_count"] = int(existing.get("seen_count") or 1) + 1
                decision = "matched"
                record = existing
            else:
                q = (
                    quality.to_evidence()
                    if quality is not None and hasattr(quality, "to_evidence")
                    else {}
                )
                record = {
                    "signal_id": fp,
                    "status": "unresolved",
                    "created_at": _now(),
                    "last_seen_at": _now(),
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
                    "next_resolution_at": _now(),
                    "execution_authority": "none",
                }
                data[fp] = record
                decision = "created"

            tmp = INBOX.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
            tmp.replace(INBOX)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return {
        "decision": decision,
        "signal_id": fp,
        "status": record.get("status"),
        "source": record.get("source"),
        "locale": record.get("locale"),
        "execution_authority": "none",
    }


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
