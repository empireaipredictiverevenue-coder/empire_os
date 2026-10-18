"""Bounded first-party Workspace Gmail thread monitor for six REAL sent anchors.

Reuses the EXISTING GoogleWorkspaceMailboxProvider authenticated identity and
Gmail readonly scope. No OAuth setup, send path, data movement, CRM writes,
message body/preview retention, tracking pixels, or prospect creation.
A Gmail thread is NOT a proven buyer reply, qualified lead or revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parseaddr
import re
from typing import Any, Mapping

SCHEMA = "empire.workspace_solar_outreach_tracking.v1"
ACCOUNT = "phil@mail.empire-ai.co.uk"
HEX = re.compile(r"^[a-f0-9]{16,32}$")
ANCHORS = (
    ("GB NRG", "gbnrg.co.uk", "info@gbnrg.co.uk", "1a14f24fdcaa1d01", "1a14f282abf361e4"),
    ("Perfect Sense Energy", "perfectsenseenergy.com", "contactus@perfectsenseenergy.com", "1a14f2505c538311", "1a14f28336a3968c"),
    ("Solar4Good", "solar4good.co.uk", "info@solar4good.co.uk", "1a14f250aa228b3e", "1a14f283948b5788"),
    ("Sustain Commercial Solar", "sustaincommercialsolar.com", "enquiries@sustaincommercialsolar.com", "1a14f2fddadfeb8a", "1a14f36a4bfdb0ec"),
    ("SOL PV Group", "solpvgroup.co.uk", "info@solpvgroup.co.uk", "1a14f2fe3468400e", "1a14f36accbf3a56"),
    ("100% Renewables", "100-renewables.co.uk", "info@100-renewables.co.uk", "1a14f2fe80133909", "1a14f36b276ff3c2"),
)
EXPECTED_THREADS = frozenset(row[3] for row in ANCHORS)
MAX_THREAD_MESSAGES = 80
HEADERS = ["From", "To", "Subject", "Message-ID", "In-Reply-To", "References"]
SENSITIVE = ("body", "snippet", "raw", "payload", "email", "to", "from")


class EvidenceHeld(ValueError):
    pass


def _headers(msg: Mapping[str, Any]) -> dict[str, str]:
    payload = msg.get("payload")
    if not isinstance(payload, Mapping):
        raise EvidenceHeld("MESSAGE_METADATA_MISSING")
    headers = payload.get("headers")
    if not isinstance(headers, list) or len(headers) > 45:
        raise EvidenceHeld("MESSAGE_HEADERS_UNAVAILABLE")
    result = {}
    for h in headers:
        if not isinstance(h, Mapping) or not isinstance(h.get("name"), str) or not isinstance(h.get("value"), str):
            raise EvidenceHeld("INVALID_PROVIDER_HEADER")
        if len(h["value"]) > 1024 or "\r" in h["value"] or "\n" in h["value"]:
            raise EvidenceHeld("UNSAFE_PROVIDER_HEADER")
        k = h["name"].lower()
        if k in ("from", "to") and k in result:
            raise EvidenceHeld("DUPLICATED_IDENTITY_HEADER")
        if k in ("from", "to", "subject"):
            result[k] = h["value"]
    return result


def _email_from(value: str) -> str:
    if not isinstance(value, str) or len(value) > 512 or "\r" in value or "\n" in value:
        raise EvidenceHeld("INVALID_SENDER_HEADER")
    email = parseaddr(value)[1].lower().strip()
    if not email or email.count("@") != 1 or not re.fullmatch(r"[a-z0-9._+%-]+@[a-z0-9.-]+\.[a-z]{2,24}", email):
        raise EvidenceHeld("INVALID_SENDER_ADDRESS")
    return email


def _to_has(headers: Mapping[str, str], recipient: str) -> bool:
    recipients = headers.get("to", "").split(",")
    if len(recipients) > 12:
        raise EvidenceHeld("TO_HEADER_TOO_LONG")
    return any(_email_from(x) == recipient for x in recipients if x.strip())


def _occurred(msg: Mapping[str, Any], *, now: datetime) -> datetime:
    raw = msg.get("internalDate")
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{12,14}", raw):
        raise EvidenceHeld("INVALID_GMAIL_TIMESTAMP")
    when = datetime.fromtimestamp(int(raw) / 1000, timezone.utc)
    if when > now.replace(microsecond=999999) or when.year < 2026:
        raise EvidenceHeld("UNTRUSTED_GMAIL_TIMESTAMP")
    return when


def _labels(message: Mapping[str, Any]) -> set[str]:
    labels = message.get("labelIds")
    if not isinstance(labels, list) or len(labels) > 50 or any(not isinstance(x, str) or len(x) > 70 for x in labels):
        raise EvidenceHeld("UNTRUSTED_GMAIL_LABELS")
    return set(labels)


def review_workspace_solar_threads(
    results: Mapping[str, Any], *, now: datetime
) -> dict[str, Any]:
    """Consume complete actual Gmail API metadata responses for ALL six anchors.

    No email bodies or subject text leave the function. Any missing anchor
    or incomplete thread holds the ENTIRE batch: no partial status promotion.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise EvidenceHeld("TRUSTED_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if not isinstance(results, Mapping) or set(results) != EXPECTED_THREADS:
        raise EvidenceHeld("INCOMPLETE_WORKSPACE_THREAD_SCAN")
    reviewed = []
    for company, domain, recipient, tid, sent_id in ANCHORS:
        thread = results[tid]
        if not isinstance(thread, Mapping) or thread.get("id") != tid:
            raise EvidenceHeld("GMAIL_THREAD_ID_MISMATCH")
        messages = thread.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_THREAD_MESSAGES:
            raise EvidenceHeld("INCOMPLETE_WORKSPACE_THREAD")
        seen = set()
        sent_when = None
        candidates = []
        anchored = False
        for msg in messages:
            if not isinstance(msg, Mapping):
                raise EvidenceHeld("UNTRUSTED_MESSAGE_METADATA")
            mid = msg.get("id")
            if not isinstance(mid, str) or not HEX.fullmatch(mid) or mid in seen:
                raise EvidenceHeld("INVALID_DUPLICATE_MESSAGE_ID")
            seen.add(mid)
            if msg.get("threadId") != tid:
                raise EvidenceHeld("MESSAGE_THREAD_MISMATCH")
            sender = _email_from(_headers(msg).get("from", ""))
            headers = _headers(msg)
            received_at = _occurred(msg, now=now)
            labels = _labels(msg)
            if mid == sent_id:
                if ("SENT" not in labels or "DRAFT" in labels or sender != ACCOUNT
                        or not _to_has(headers, recipient)):
                    raise EvidenceHeld("SENT_ANCHOR_NOT_PROVED_IN_WORKSPACE")
                sent_when = received_at
                anchored = True
                continue
            if "SENT" in labels or "DRAFT" in labels or "TRASH" in labels or "SPAM" in labels:
                continue
            if sender.split("@")[-1] != domain:
                continue
            candidates.append({"gmail_message_id": mid, "received_at": received_at.isoformat(),
                               "status": "INBOUND_PROVIDER_HEADER_CANDIDATE_NEEDS_HUMAN_REVIEW"})
        if not anchored or sent_when is None:
            raise EvidenceHeld("EXACT_SENT_MESSAGE_ANCHOR_MISSING")
        if any(datetime.fromisoformat(c["received_at"]) <= sent_when for c in candidates):
            raise EvidenceHeld("INBOUND_PRECEDES_SENT_ANCHOR")
        reviewed.append({
            "company": company, "gmail_thread_id": tid,
            "sent_message_id": sent_id, "sent_at": sent_when.isoformat(),
            "sent_verified_in_authenticated_mailbox": True,
            "inbound_header_candidates": sorted(candidates, key=lambda x: (x["received_at"], x["gmail_message_id"])),
            "inbound_corroborated_by_body": False,
            "buyer_intent_verified": False, "automatic_reply_authorized": False,
            "recognized_revenue": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "mailbox_class": "EXACT_WORKSPACE_ACCOUNT_VERIFIED_BY_PROVIDER",
        "status": "SIX_WORKSPACE_THREADS_SCANNED_REVIEW_ONLY",
        "scope": "six_founder_approved_uk_solar_outbound_threads",
        "scanned_at": now.isoformat(),
        "monitored_threads": len(reviewed),
        "verified_sent_anchors": len(reviewed),
        "inbound_header_candidate_count": sum(len(x["inbound_header_candidates"]) for x in reviewed),
        "threads": reviewed,
        "gmail_message_bodies_retained": False,
        "gmail_subjects_retained": False,
        "founder_crm_ingest_verified": False,
        "database_writes": False,
        "outbound_sent": False,
        "automatic_outbound_authorized": False,
        "payment_action": False,
        "recognized_revenue": False,
        "execution_authority": "none",
    }


def collect_workspace_solar_threads(service: Any, *, now: datetime) -> dict[str, Any]:
    """Exact six readonly calls after the existing provider validates identity."""
    results = {}
    for _, _, _, tid, _ in ANCHORS:
        thread = service.users().threads().get(
            userId="me", id=tid, format="metadata", metadataHeaders=HEADERS
        ).execute()
        results[tid] = thread
    return review_workspace_solar_threads(results, now=now)


def newly_observed_workspace_replies(
    current: Mapping[str, Any], previous: Mapping[str, Any] | None
) -> int:
    """Count newly seen header candidates without claiming buyer intent.

    Never rewrite/reinterpret a historical sent anchor, or silently lose
    formerly observed reply headers. Reads no bodies and grants no authority.
    """
    if (not isinstance(current, Mapping)
            or current.get("schema_version") != SCHEMA
            or current.get("status") != "SIX_WORKSPACE_THREADS_SCANNED_REVIEW_ONLY"):
        raise EvidenceHeld("INVALID_CURRENT_WORKSPACE_SOURCE_SNAPSHOT")
    rows = current.get("threads")
    if not isinstance(rows, list) or len(rows) != len(ANCHORS):
        raise EvidenceHeld("INVALID_CURRENT_THREAD_COVERAGE")
    known = {}
    if previous is not None:
        if (not isinstance(previous, Mapping)
                or previous.get("schema_version") != SCHEMA
                or previous.get("status") != "SIX_WORKSPACE_THREADS_SCANNED_REVIEW_ONLY"):
            raise EvidenceHeld("UNTRUSTED_PREVIOUS_WORKSPACE_SNAPSHOT")
        old_rows = previous.get("threads")
        if not isinstance(old_rows, list) or len(old_rows) != len(ANCHORS):
            raise EvidenceHeld("INCOMPLETE_PREVIOUS_WORKSPACE_SNAPSHOT")
        for row in old_rows:
            if not isinstance(row, Mapping) or row.get("gmail_thread_id") in known:
                raise EvidenceHeld("INVALID_PREVIOUS_THREAD_ID")
            old_id = row.get("gmail_thread_id")
            match = next((x for x in ANCHORS if x[3] == old_id), None)
            if (match is None or row.get("sent_message_id") != match[4]
                    or row.get("sent_verified_in_authenticated_mailbox") is not True):
                raise EvidenceHeld("PREVIOUS_SENT_ANCHOR_MISMATCH")
            candidates = row.get("inbound_header_candidates")
            if not isinstance(candidates, list):
                raise EvidenceHeld("INVALID_PREVIOUS_CANDIDATES")
            old_ids = [c.get("gmail_message_id") for c in candidates if isinstance(c, Mapping)]
            if len(old_ids) != len(candidates) or len(set(old_ids)) != len(old_ids):
                raise EvidenceHeld("DUPLICATE_PREVIOUS_CANDIDATES")
            known[old_id] = set(old_ids)
    now_ids = set()
    total_new = 0
    for row in rows:
        tid = row["gmail_thread_id"]
        match = next((x for x in ANCHORS if x[3] == tid), None)
        if (match is None or tid in now_ids
                or row.get("sent_message_id") != match[4]
                or row.get("sent_verified_in_authenticated_mailbox") is not True):
            raise EvidenceHeld("CURRENT_SENT_ANCHOR_MISMATCH")
        now_ids.add(tid)
        current_ids = {x["gmail_message_id"] for x in row["inbound_header_candidates"]}
        old_ids = known.get(tid, set())
        if not old_ids.issubset(current_ids):
            raise EvidenceHeld("PREVIOUS_INBOUND_OBSERVATION_MISSING")
        total_new += len(current_ids - old_ids)
    if now_ids != EXPECTED_THREADS:
        raise EvidenceHeld("INCOMPLETE_CURRENT_WORKSPACE_COVERAGE")
    return total_new
