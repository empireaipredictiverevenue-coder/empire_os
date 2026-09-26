"""Bounded promotion of strong public-record signals into canonical prospects.

Only source-specific evidence contracts may promote. Ambiguous court/community
signals remain in the inbox. No outreach, payment or revenue authority exists.
"""
from __future__ import annotations

import fcntl
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.lead_sources import LeadCandidate
from empire_os.locale_intelligence import resolve_locale
from empire_os.signal_inbox import INBOX, LOCK, ROOT


Reader = Callable[[str, dict[str, str]], Any]
Writer = Callable[[dict[str, Any]], dict[str, Any]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _permit_candidate(signal: Mapping[str, Any]) -> LeadCandidate | None:
    if str(signal.get("source") or "") != "permits_nyc":
        return None
    raw = signal.get("raw")
    if not isinstance(raw, Mapping):
        return None

    business = str(raw.get("permittee_s_business_name") or "").strip()
    phone = str(raw.get("permittee_s_phone__") or "").strip()
    license_no = str(raw.get("permittee_s_license__") or "").strip()
    license_type = str(raw.get("permittee_s_license_type") or "").strip()
    if not (business and phone and license_no and license_type):
        return None

    first = str(raw.get("permittee_s_first_name") or "").strip()
    last = str(raw.get("permittee_s_last_name") or "").strip()
    contact = " ".join(part for part in (first, last) if part)
    metro = str(signal.get("metro") or "NYC").strip()
    state = str(signal.get("state") or "NY").strip()
    locale = resolve_locale({
        "country_code": "US",
        "state": state,
        "metro": metro,
        "source_language": "en-US",
    })
    job = str(raw.get("job__") or "").strip()
    address = " ".join(
        part for part in (
            str(raw.get("house__") or "").strip(),
            str(raw.get("street_name") or "").strip(),
        )
        if part
    )

    return LeadCandidate(
        name=business,
        phone=phone,
        niche="general_contractor",
        metro=metro,
        state=state,
        country_code=locale.country_code or "US",
        language_code=locale.language_code or "en-US",
        source_language="en-US",
        timezone=locale.timezone or "America/New_York",
        details=(
            f"NYC permittee identity; license {license_type} {license_no}; "
            f"permit {job}; contact {contact or 'not stated'}"
            + (f"; site {address}" if address else "")
        ),
        source="permits_nyc_resolved",
        lead_score=82,
        url=str(signal.get("url") or "").strip(),
        raw={
            "resolved_from_signal_id": signal.get("signal_id"),
            "identity_source": "nyc_permit_public_record",
            "permittee_business_name": business,
            "permittee_phone": phone,
            "permittee_license": license_no,
            "permittee_license_type": license_type,
            "permittee_contact_name": contact,
            "permit_job": job,
            "original": dict(raw),
        },
    )


def candidate_from_signal(signal: Mapping[str, Any]) -> tuple[LeadCandidate | None, str]:
    source = str(signal.get("source") or "").strip()
    if source == "permits_nyc":
        candidate = _permit_candidate(signal)
        return (
            (candidate, "permittee_identity_complete")
            if candidate is not None
            else (None, "permittee_identity_incomplete")
        )
    if source == "courtlistener":
        return None, "court_party_requires_external_identity_resolution"
    if source in {"reddit_intent", "linkedin_intent"}:
        return None, "community_signal_requires_external_identity_resolution"
    return None, "unsupported_signal_resolution_source"


def _load(path: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def run_signal_resolution(
    limit: int = 10,
    *,
    inbox: Path = INBOX,
    lock: Path = LOCK,
    reader: Reader | None = None,
    writer: Writer | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if limit < 1 or limit > 25:
        raise ValueError("signal resolution limit must be 1-25")
    current = (now or _now()).astimezone(timezone.utc)

    if reader is None or writer is None:
        from empire_os.crawler_runner import _canonical_reader, _canonical_writer
        reader = reader or _canonical_reader
        writer = writer or _canonical_writer

    from empire_os.crawler_runner import ingest_candidate

    inbox.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(exist_ok=True)

    # Claim only the bounded rows under the file lock. Network/database work
    # happens after the lock is released so the live crawler can keep enqueueing.
    claimed: list[tuple[str, dict[str, Any]]] = []
    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            data = _load(inbox)
            eligible = []
            for key, row in data.items():
                if not isinstance(row, dict) or row.get("status") != "unresolved":
                    continue
                next_at = _parse_time(row.get("next_resolution_at"))
                if next_at is not None and next_at > current:
                    continue
                eligible.append((key, row))
            eligible.sort(
                key=lambda item: str(item[1].get("created_at") or "")
            )

            for key, row in eligible[:limit]:
                attempts = int(row.get("resolution_attempts") or 0) + 1
                row["resolution_attempts"] = attempts
                row["last_resolution_at"] = current.isoformat()
                # Lease the row so a second resolver cannot duplicate the same
                # canonical work while this batch is in flight.
                row["next_resolution_at"] = (
                    current + timedelta(minutes=15)
                ).isoformat()
                claimed.append((key, dict(row)))

            tmp = inbox.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
            tmp.replace(inbox)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    resolved = matched = deferred = review = failed = 0
    results: list[dict[str, Any]] = []
    updates: dict[str, dict[str, Any]] = {}

    for key, row in claimed:
        attempts = int(row.get("resolution_attempts") or 1)
        candidate, reason = candidate_from_signal(row)
        update: dict[str, Any] = {
            "resolution_reason": reason,
        }

        if candidate is None:
            deferred += 1
            update["next_resolution_at"] = (
                current + timedelta(hours=min(24, 6 * attempts))
            ).isoformat()
            updates[key] = update
            results.append({
                "signal_id": key,
                "source": row.get("source"),
                "decision": "deferred",
                "reason": reason,
            })
            continue

        try:
            outcome = ingest_candidate(
                candidate,
                reader=reader,
                writer=writer,
            )
        except Exception as exc:
            failed += 1
            failure_reason = (
                f"canonical_ingest_failed:{type(exc).__name__}"
            )
            updates[key] = {
                "resolution_reason": failure_reason,
                "next_resolution_at": (
                    current + timedelta(hours=6)
                ).isoformat(),
            }
            results.append({
                "signal_id": key,
                "decision": "failed",
                "reason": failure_reason,
            })
            continue

        decision = str(outcome.get("decision") or "")
        prospect = outcome.get("prospect")
        prospect_id = (
            str(prospect.get("id") or "")
            if isinstance(prospect, Mapping)
            else ""
        )
        if decision in {"created", "matched"} and prospect_id:
            updates[key] = {
                "status": "resolved",
                "prospect_id": prospect_id,
                "resolved_at": current.isoformat(),
                "next_resolution_at": None,
                "resolution_reason": (
                    "canonical_prospect_created"
                    if decision == "created"
                    else "canonical_prospect_matched"
                ),
            }
            resolved += 1
            matched += int(decision == "matched")
        elif decision == "ambiguous":
            updates[key] = {
                "status": "needs_review",
                "next_resolution_at": None,
                "resolution_reason": str(
                    outcome.get("reason") or "ambiguous_identity"
                ),
            }
            review += 1
        else:
            updates[key] = {
                "next_resolution_at": (
                    current + timedelta(hours=6)
                ).isoformat(),
            }
            deferred += 1

        results.append({
            "signal_id": key,
            "decision": decision or "deferred",
            "prospect_id": prospect_id or None,
            "reason": updates[key].get("resolution_reason"),
        })

    if updates:
        with lock.open("r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                data = _load(inbox)
                for key, update in updates.items():
                    row = data.get(key)
                    if isinstance(row, dict):
                        row.update(update)
                tmp = inbox.with_suffix(".json.tmp")
                tmp.write_text(
                    json.dumps(
                        data,
                        indent=2,
                        sort_keys=True,
                        default=str,
                    ) + "\n",
                    encoding="utf-8",
                )
                tmp.replace(inbox)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return {
        "schema_version": "empire.signal-resolution.v1",
        "mode": "INTERNAL_MATERIALIZE",
        "execution_authority": "canonical_prospect_ingest_only",
        "attempted": len(results),
        "resolved": resolved,
        "matched_existing": matched,
        "needs_review": review,
        "deferred": deferred,
        "failed": failed,
        "outbound_sent": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "results": results,
        "ok": failed == 0,
    }
