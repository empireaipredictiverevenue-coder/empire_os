"""Awin publisher programme review in the ORIGINAL EmpireOS Gmail cycle.

Read-only Gmail metadata and 0600 publisher receipt; no new accounts, writers to
EmpireDB, commission recognition, affiliate tracking links or outbound transport.
Official-looking email headers are candidates, NOT programme acceptance proof.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path
import json
import os
import re
import stat
import tempfile
from typing import Any

from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider

SCHEMA = "empire.awin_publisher_operations.review.v1"
SOURCE = Path("runtime/buyer_network_intelligence/awin_publisher_onboarding_email_evidence_20261027.json")
OUTPUT = Path("runtime/buyer_network_intelligence/awin_publisher_operations_review_latest.json")
PROGRAMMES = {"122556": "OVO Solar & Heating", "73922": "Glow Green"}
GMAIL_ID = re.compile(r"^[a-f0-9]{16,32}$")
ALLOWED_SENDERS = frozenset({"awin.com", "ovoenergy.com", "glowgreenltd.com"})
MAX_GMAIL_MATCHES = 35
WINDOW_DAYS = 30


class AwinReviewHold(ValueError):
    pass


def _private_receipt(path: Path) -> dict[str, Any]:
    if (path.is_symlink() or not path.is_file()
            or not 200 <= path.stat().st_size < 30000
            or stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise AwinReviewHold("AWIN_PRIVATE_RECEIPT_UNAVAILABLE")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise AwinReviewHold("AWIN_RECEIPT_UNREADABLE") from exc
    if (not isinstance(value, dict)
            or value.get("publisher_id") != "3136281"
            or value.get("publisher_account_approved") is not True
            or value.get("publisher_account_activated_per_awin_email") is not True
            or value.get("advertiser_decisions_verified_count") != 0
            or value.get("advertiser_tracking_links_issued") is not False
            or value.get("commission_earned_proven") is not False
            or value.get("commission_received_proven") is not False):
        raise AwinReviewHold("AWIN_RECEIPT_AUTHORITY_INVALID")
    programmes = value.get("advertiser_programmes")
    if (not isinstance(programmes, list) or len(programmes) != 2
            or {str(r.get("advertiser_id")): r.get("advertiser")
                for r in programmes if isinstance(r, dict)} != PROGRAMMES
            or any(r.get("advertiser_acceptance_evidence") is not False
                   or r.get("status") !=
                      "APPLICATION_SUBMITTED_FOUNDER_REPORTED_AWAITING_ADVERTISER_DECISION"
                   for r in programmes if isinstance(r, dict))):
        raise AwinReviewHold("AWIN_ADVERTISER_SOURCE_STATE_DRIFT")
    return value


def _headers(message: dict) -> dict[str, str]:
    payload = message.get("payload")
    if not isinstance(payload, dict):
        raise AwinReviewHold("AWIN_PROVIDER_HEADERS_INCOMPLETE")
    values = payload.get("headers")
    if not isinstance(values, list) or len(values) > 80:
        raise AwinReviewHold("AWIN_PROVIDER_HEADER_BOUNDS")
    result: dict[str, str] = {}
    for header in values:
        if (not isinstance(header, dict) or
                not isinstance(header.get("name"), str) or
                not isinstance(header.get("value"), str)):
            raise AwinReviewHold("AWIN_PROVIDER_HEADER_INVALID")
        key = header["name"].lower()
        if key in {"from", "subject"}:
            if key in result or len(header["value"]) > 500:
                raise AwinReviewHold("AWIN_PROVIDER_IDENTITY_AMBIGUOUS")
            result[key] = header["value"]
    return result


def _matches_programme(subject: str) -> tuple[str, ...]:
    if not isinstance(subject, str):
        return ()
    lower = subject.casefold()
    matches = []
    if "122556" in lower or re.search(r"\bovo\b", lower):
        matches.append("122556")
    if "73922" in lower or "glow green" in lower:
        matches.append("73922")
    return tuple(matches)


def scan_awin_candidates(service: Any, *, now: datetime) -> list[dict]:
    """Bounded Gmail metadata scan; no message bodies, links, or snippets persisted."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise AwinReviewHold("AWIN_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    start = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y/%m/%d")
    query = (f'after:{start} '
             f'(from:awin.com OR from:ovoenergy.com OR from:glowgreenltd.com) '
             f'(OVO OR "Glow Green" OR 122556 OR 73922) -in:trash')
    try:
        response = service.users().messages().list(
            userId="me", q=query, maxResults=MAX_GMAIL_MATCHES + 1,
            fields="messages(id),nextPageToken",
        ).execute()
        ids = response.get("messages", [])
        if (not isinstance(ids, list) or len(ids) > MAX_GMAIL_MATCHES
                or response.get("nextPageToken")):
            raise AwinReviewHold("AWIN_GMAIL_SCAN_BOUNDED_INCOMPLETE")
        checked = set()
        candidates = []
        for entry in ids:
            identifier = entry.get("id") if isinstance(entry, dict) else None
            if not isinstance(identifier, str) or not GMAIL_ID.fullmatch(identifier) or identifier in checked:
                raise AwinReviewHold("AWIN_GMAIL_ID_INVALID")
            checked.add(identifier)
            message = service.users().messages().get(
                userId="me", id=identifier, format="metadata",
                metadataHeaders=["From", "Subject"],
                fields="id,labelIds,internalDate,payload(headers)",
            ).execute()
            if not isinstance(message, dict) or message.get("id") != identifier:
                raise AwinReviewHold("AWIN_GMAIL_PROVIDER_MISMATCH")
            labels = message.get("labelIds")
            if not isinstance(labels, list) or any(
                    not isinstance(x, str) for x in labels):
                raise AwinReviewHold("AWIN_GMAIL_LABELS_INVALID")
            if set(labels) & {"SENT", "DRAFT", "TRASH"}:
                continue
            headers = _headers(message)
            sender = parseaddr(headers.get("from", ""))[1].casefold()
            domain = sender.rsplit("@", 1)[-1]
            if not any(domain == allowed or domain.endswith("." + allowed)
                       for allowed in ALLOWED_SENDERS):
                continue
            programme_ids = _matches_programme(headers.get("subject", ""))
            if not programme_ids:
                continue
            stamp = message.get("internalDate")
            if not isinstance(stamp, str) or not stamp.isdecimal() or len(stamp) not in (12, 13, 14):
                raise AwinReviewHold("AWIN_GMAIL_TIMESTAMP_MISSING")
            at = datetime.fromtimestamp(int(stamp) / 1000, timezone.utc)
            if at > now + timedelta(seconds=90) or at < now - timedelta(days=WINDOW_DAYS + 2):
                raise AwinReviewHold("AWIN_GMAIL_TIMESTAMP_UNTRUSTED")
            for programme_id in programme_ids:
                candidates.append({
                    "advertiser_id": programme_id,
                    "gmail_message_id": identifier,
                    "mailbox_observed_at": at.isoformat(),
                    "status": "INBOUND_HEADER_CANDIDATE_NEEDS_FOUNDER_REVIEW",
                    "programme_accepted": False,
                    "sender_authenticated_for_commercial_acceptance": False,
                })
        return sorted(candidates, key=lambda r: (r["mailbox_observed_at"], r["gmail_message_id"],r["advertiser_id"]))
    except AwinReviewHold:
        raise
    except Exception as exc:
        raise AwinReviewHold("AWIN_GMAIL_METADATA_UNAVAILABLE") from exc



def previous_seen_pairs(path: Path) -> set[tuple[str, str]]:
    """Read last private review; preserve seen IDs so repeated polls aren't new."""
    if not path.exists():
        return set()
    if (path.is_symlink() or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or not 100 < path.stat().st_size < 30000):
        raise AwinReviewHold("AWIN_PREVIOUS_SNAPSHOT_UNSAFE")
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise AwinReviewHold("AWIN_PREVIOUS_SNAPSHOT_INVALID") from exc
    if (not isinstance(prior, dict) or prior.get("schema_version") != SCHEMA
            or prior.get("publisher_id") != "3136281"
            or prior.get("execution_authority") != "NONE"
            or prior.get("outbound_sent") is not False
            or prior.get("database_writes") is not False
            or prior.get("affiliate_publication_authorized") is not False):
        raise AwinReviewHold("AWIN_PREVIOUS_SNAPSHOT_AUTHORITY_INVALID")
    programmes = prior.get("programmes")
    if (not isinstance(programmes, list) or len(programmes) != 2
            or {row.get("advertiser_id"): row.get("advertiser")
                for row in programmes if isinstance(row, dict)} != PROGRAMMES):
        raise AwinReviewHold("AWIN_PREVIOUS_PROGRAMME_MISMATCH")
    rows: set[tuple[str, str]] = set()
    for item in programmes:
        ids = item.get("inbound_gmail_message_ids")
        if (not isinstance(ids, list) or len(ids) > MAX_GMAIL_MATCHES
                or any(not isinstance(m, str) or not GMAIL_ID.fullmatch(m) for m in ids)
                or len(ids) != len(set(ids))):
            raise AwinReviewHold("AWIN_PREVIOUS_CANDIDATE_IDS_INVALID")
        rows.update((item["advertiser_id"], m) for m in ids)
    historical = prior.get("seen_programme_message_refs", [])
    if not isinstance(historical, list) or len(historical) > 250:
        raise AwinReviewHold("AWIN_PREVIOUS_SEEN_OVERFLOW")
    for pair in historical:
        if (not isinstance(pair, list) or len(pair) != 2
                or pair[0] not in PROGRAMMES or not isinstance(pair[1], str)
                or not GMAIL_ID.fullmatch(pair[1])):
            raise AwinReviewHold("AWIN_PREVIOUS_SEEN_INVALID")
        rows.add((pair[0], pair[1]))
    if len(rows) > 250:
        raise AwinReviewHold("AWIN_PREVIOUS_SEEN_OVERFLOW")
    return rows



def evaluate(source: dict, candidates: list[dict], *, now: datetime,
             previous_seen: set[tuple[str, str]] | None = None) -> dict:
    if not isinstance(source, dict) or not isinstance(candidates, list):
        raise AwinReviewHold("AWIN_SOURCE_INVALID")
    if source.get("publisher_id") != "3136281":
        raise AwinReviewHold("AWIN_PUBLISHER_ID_INVALID")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise AwinReviewHold("AWIN_CLOCK_INVALID")
    readiness = source.get("commercial_publication_readiness")
    if not isinstance(readiness, dict) or readiness.get("live_affiliate_traffic_authorized") is not False:
        raise AwinReviewHold("AWIN_PUBLISHING_STATUS_UNVERIFIED")
    if len(candidates) > MAX_GMAIL_MATCHES * 2:
        raise AwinReviewHold("AWIN_CANDIDATES_OVER_BOUNDS")
    if not isinstance(previous_seen, (set, type(None))):
        raise AwinReviewHold("AWIN_PREVIOUS_SEEN_INVALID")
    seen = set(previous_seen or ())
    if len(seen) > 250 or any(
            not isinstance(pair, tuple) or len(pair) != 2
            or pair[0] not in PROGRAMMES or not GMAIL_ID.fullmatch(str(pair[1]))
            for pair in seen):
        raise AwinReviewHold("AWIN_PREVIOUS_SEEN_INVALID")
    current = {(row["advertiser_id"], row["gmail_message_id"])
               for row in candidates}
    updated = seen | current
    if len(updated) > 250:
        raise AwinReviewHold("AWIN_SEEN_CANDIDATE_CAPACITY_HELD")
    newest = current - seen
    programmes = []
    for entry in source["advertiser_programmes"]:
        ident = entry["advertiser_id"]
        matching = [r for r in candidates if r["advertiser_id"] == ident]
        programmes.append({
            "advertiser_id": ident,
            "advertiser": entry["advertiser"],
            "application_status": entry["status"],
            "application_source": "FOUNDER_REPORTED_NOT_AWIN_API",
            "inbound_header_candidate_count": len(matching),
            "new_inbound_header_candidates": sum(
                (ident, r["gmail_message_id"]) in newest for r in matching),
            "inbound_gmail_message_ids": [r["gmail_message_id"] for r in matching],
            "next_action": "REVIEW_AWIN_MESSAGE_AND_CHECK_DASHBOARD" if matching
                           else "AWAIT_ADVERTISER_DECISION_NO_REPEAT_APPLICATION",
            "advertiser_acceptance_verified": False,
            "tracking_link_authorized": False,
            "payable_commission_verified": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": "AWIN_NETWORK_APPROVED_PROGRAMME_APPLICATIONS_PENDING_REVIEW",
        "mode": "OBSERVE",
        "scanned_at": now.astimezone(timezone.utc).isoformat(),
        "publisher_id": source["publisher_id"],
        "network_account_approved": True,
        "email_verification_confirmed": bool(source.get("email_verification_confirmed") is True),
        "programmes": programmes,
        "candidate_count": len(candidates),
        "new_candidate_count": len(newest),
        "seen_programme_message_refs": [list(pair) for pair in sorted(updated)],
        "source_limited_to_recent_gmail_metadata": True,
        "candidate_metadata_is_not_advertiser_approval": True,
        "website_owner_handoff_present": bool(readiness.get("owner_handoff_path")),
        "affiliate_publication_authorized": False,
        "tracking_links_issued_verified": False,
        "commission_earned_verified": False,
        "commission_paid_verified": False,
        "no_outreach_or_new_scheduler": True,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }


def _atomic_private_write(path: Path, value: dict) -> None:
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        raise AwinReviewHold("AWIN_SNAPSHOT_PATH_UNSAFE")
    if path.exists() and (not path.is_file() or
                          stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise AwinReviewHold("AWIN_SNAPSHOT_PREVIOUS_UNSAFE")
    fd, temp = tempfile.mkstemp(prefix=".awin_observer_", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def run(*, root: Path = Path("/srv/empire_os"), provider=None,
        write: bool = False, now: datetime | None = None) -> dict:
    safe = {
        "status": "HELD_AWIN_READ_ONLY_REVIEW_UNAVAILABLE",
        "programme_review_count": 0,
        "potential_inbound_headers": None,
        "snapshot_written": False,
        "outbound_sent": False, "database_writes": False,
        "execution_authority": "NONE",
    }
    try:
        if not isinstance(root, Path) or root.is_symlink():
            raise AwinReviewHold("AWIN_ROOT_UNSAFE")
        source = _private_receipt(root / SOURCE)
        provider = provider if provider is not None else GoogleWorkspaceMailboxProvider()
        if not provider.configured:
            raise AwinReviewHold("AWIN_WORKSPACE_READER_UNAVAILABLE")
        current = now or datetime.now(timezone.utc)
        previous_seen = previous_seen_pairs(root / OUTPUT)
        candidates = scan_awin_candidates(provider._service(), now=current)
        review = evaluate(source, candidates, now=current,
                          previous_seen=previous_seen)
        if write:
            _atomic_private_write(root / OUTPUT, review)
        return {
            "status": review["status"],
            "programme_review_count": len(review["programmes"]),
            "potential_inbound_headers": review["candidate_count"],
            "new_potential_inbound_headers": review["new_candidate_count"],
            "snapshot_written": write,
            "outbound_sent": False, "database_writes": False,
            "execution_authority": "NONE",
        }
    except (AwinReviewHold, OSError, ValueError, TypeError, KeyError):
        return safe
