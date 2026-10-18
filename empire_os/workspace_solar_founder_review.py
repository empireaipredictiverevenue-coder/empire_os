"""Private Founder Console Workspace outreach evidence projection.

Reads the EXISTING authenticated, bounded, metadata-only six-thread snapshot.
Contains NO message bodies, recipient addresses, subject lines or Google tokens.
Does not imply canonical CRM identity, buyer interest or a sale.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import re
import stat

from empire_os.workspace_solar_reply_tracking import ANCHORS, SCHEMA

SNAPSHOT = Path(
    "/srv/empire_os/runtime/buyer_network_intelligence/"
    "workspace_solar_outreach_reply_review_latest.json"
)
MAX_SIZE = 25000
MAX_AGE_SECONDS = 20 * 60
ALLOWED_RFC_RELATIONS = frozenset((
    "DIRECT_PARENT_MATCH", "ORIGINAL_MESSAGE_REFERENCED_ONLY", "NOT_PROVEN",
))
ALLOWED_RECIPIENT_ROUTES = frozenset((
    "EXPECTED_WORKSPACE_TO", "RECIPIENT_ROUTE_UNVERIFIED",
))
HEX = re.compile(r"^[a-f0-9]{16,32}$")


class WorkspaceReviewHeld(ValueError):
    """Invalid, inaccessible or stale evidence. No partial review rows."""


def _when(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise WorkspaceReviewHeld("INVALID_" + label)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise WorkspaceReviewHeld("INVALID_" + label) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkspaceReviewHeld("INVALID_" + label)
    return parsed.astimezone(timezone.utc)


def project_workspace_review(
    snapshot: Mapping[str, Any], *, now: datetime,
) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise WorkspaceReviewHeld("TRUSTED_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if not isinstance(snapshot, Mapping):
        raise WorkspaceReviewHeld("INVALID_WORKSPACE_SNAPSHOT")
    if (snapshot.get("schema_version") != SCHEMA
            or snapshot.get("status") != "SIX_WORKSPACE_THREADS_SCANNED_REVIEW_ONLY"
            or snapshot.get("monitored_threads") != 6
            or snapshot.get("verified_sent_anchors") != 6
            or snapshot.get("outbound_sent") is not False
            or snapshot.get("database_writes") is not False
            or snapshot.get("founder_crm_ingest_verified") is not False
            or snapshot.get("gmail_message_bodies_retained") is not False
            or snapshot.get("gmail_subjects_retained") is not False):
        raise WorkspaceReviewHeld("UNVERIFIED_WORKSPACE_SNAPSHOT")
    scanned_at = _when(snapshot.get("scanned_at"), label="SCAN_TIME")
    age = (now-scanned_at).total_seconds()
    if not 0 <= age <= MAX_AGE_SECONDS:
        raise WorkspaceReviewHeld("STALE_OR_FUTURE_WORKSPACE_SCAN")
    records = snapshot.get("threads")
    if not isinstance(records, list) or len(records) != len(ANCHORS):
        raise WorkspaceReviewHeld("INCOMPLETE_WORKSPACE_REVIEW")
    seen_threads = set()
    seen_messages = set()
    cards = []
    total = 0
    for row in records:
        if not isinstance(row, Mapping):
            raise WorkspaceReviewHeld("INVALID_WORKSPACE_RECORD")
        tid = row.get("gmail_thread_id")
        anchor = next((a for a in ANCHORS if a[3] == tid), None)
        if (anchor is None or tid in seen_threads
                or row.get("company") != anchor[0]
                or row.get("sent_message_id") != anchor[4]
                or row.get("sent_verified_in_authenticated_mailbox") is not True
                or row.get("buyer_intent_verified") is not False
                or row.get("automatic_reply_authorized") is not False
                or row.get("inbound_corroborated_by_body") is not False
                or row.get("recognized_revenue") is not False):
            raise WorkspaceReviewHeld("WORKSPACE_ANCHOR_OR_AUTHORITY_CONFLICT")
        seen_threads.add(tid)
        candidates = row.get("inbound_header_candidates")
        if not isinstance(candidates, list) or len(candidates) > 79:
            raise WorkspaceReviewHeld("INVALID_REPLY_CANDIDATE_COUNT")
        incoming = []
        sent_at = _when(row.get("sent_at"), label="SENT_TIME")
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise WorkspaceReviewHeld("INVALID_REPLY_CANDIDATE")
            cid = candidate.get("gmail_message_id")
            if (not isinstance(cid, str) or not HEX.fullmatch(cid)
                    or cid == anchor[4] or cid in seen_messages
                    or candidate.get("status")
                    != "INBOUND_PROVIDER_HEADER_CANDIDATE_NEEDS_HUMAN_REVIEW"):
                raise WorkspaceReviewHeld("UNTRUSTED_REPLY_CANDIDATE")
            seen_messages.add(cid)
            relation = candidate.get("rfc_parent_relation", "NOT_PROVEN")
            if relation not in ALLOWED_RFC_RELATIONS:
                raise WorkspaceReviewHeld("UNTRUSTED_RFC_CHAIN_CLASSIFICATION")
            routing = candidate.get("recipient_routing", "RECIPIENT_ROUTE_UNVERIFIED")
            if routing not in ALLOWED_RECIPIENT_ROUTES:
                raise WorkspaceReviewHeld("UNTRUSTED_RECIPIENT_ROUTING")
            received = _when(candidate.get("received_at"), label="INBOUND_TIME")
            if received <= sent_at or received > scanned_at:
                raise WorkspaceReviewHeld("INBOUND_TIME_CONFLICT")
            incoming.append({
                "gmail_message_id": cid,
                "received_at": received.isoformat(),
                "state": "HEADER_CANDIDATE_REQUIRES_FOUNDER_REVIEW",
                "contact_identity_verified": False,
                "commercial_intent_verified": False,
                "rfc_parent_relation": relation,
                "recipient_routing": routing,
            })
        incoming.sort(key=lambda x: (x["received_at"], x["gmail_message_id"]))
        total += len(incoming)
        cards.append({
            "company": anchor[0],
            "gmail_thread_id": tid,
            "gmail_thread_url": "https://mail.google.com/mail/u/?authuser=phil%40empire-ai.co.uk#all/" + tid,
            "sent_verified": True,
            "inbound_candidate_count": len(incoming),
            "inbound_candidates": incoming,
            "founder_action": (
                "REVIEW_ACTUAL_GMAIL_MESSAGE_THEN_CANONICAL_IDENTITY"
                if incoming else "WAIT_FOR_GENUINE_REPLY"
            ),
            "crm_conversation_created": False,
            "tenant_and_contact_binding_verified": False,
        })
    if seen_threads != {a[3] for a in ANCHORS}:
        raise WorkspaceReviewHeld("INCOMPLETE_WORKSPACE_REVIEW")
    if total != snapshot.get("inbound_header_candidate_count"):
        raise WorkspaceReviewHeld("REPLY_COUNT_MISMATCH")
    cards.sort(key=lambda x: x["company"])
    return {
        "schema_version": "empire.founder_workspace_reply_review.v1",
        "status": "FRESH_WORKSPACE_REVIEW_QUEUE",
        "mode": "OBSERVE",
        "source": "six_exact_authenticated_workspace_gmail_threads",
        "scanned_at": scanned_at.isoformat(),
        "monitored_threads": len(cards),
        "sent_anchors_verified": len(cards),
        "inbound_header_candidate_count": total,
        "items": cards,
        "emails_or_bodies_disclosed": False,
        "founder_review_required": total > 0,
        "crm_identity_and_tenant_unverified": True,
        "crm_conversation_created": False,
        "crm_mutation": False,
        "outbound_sent": False,
        "payment_execution": False,
        "execution_authority": "none",
    }


def read_workspace_review(
    path: Path = SNAPSHOT, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Private exact-path read. Fail closed before any partial disclosure."""
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise WorkspaceReviewHeld("WORKSPACE_SNAPSHOT_UNAVAILABLE")
    info = path.stat()
    if (not info.st_size or info.st_size > MAX_SIZE
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise WorkspaceReviewHeld("UNSAFE_WORKSPACE_SNAPSHOT")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise WorkspaceReviewHeld("WORKSPACE_SNAPSHOT_UNREADABLE") from None
    return project_workspace_review(
        data, now=now or datetime.now(timezone.utc)
    )
