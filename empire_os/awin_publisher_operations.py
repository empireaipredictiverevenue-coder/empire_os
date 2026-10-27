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
    query = f'after:{start} (OVO OR "Glow Green" OR 122556 OR 73922) -in:trash'
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


def evaluate(source: dict, candidates: list[dict], *, now: datetime) -> dict:
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
    programmes = []
    for entry in source["advertiser_programmes"]:
        ident = entry["advertiser_id"]
        matching = [r for r in candidates if r["advertiser_id"] == ident]
        programmes.append({
            "advertiser_id": ident,
            "advertiser": entry["advertiser"],
            "application_status": entry["status"],
            "application_source": "FOUNDER_REPORTED_NOT_AWIN_API",
            "new_inbound_header_candidates": len(matching),
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
        candidates = scan_awin_candidates(provider._service(), now=current)
        review = evaluate(source, candidates, now=current)
        if write:
            _atomic_private_write(root / OUTPUT, review)
        return {
            "status": review["status"],
            "programme_review_count": len(review["programmes"]),
            "potential_inbound_headers": review["candidate_count"],
            "snapshot_written": write,
            "outbound_sent": False, "database_writes": False,
            "execution_authority": "NONE",
        }
    except (AwinReviewHold, OSError, ValueError, TypeError, KeyError):
        return safe
