"""Fail-closed six-Gmail-send historical evidence manifest, not outbound intent.

No database access, no message bodies or subjects, no sends. This module
creates a bounded private proof package from an ALREADY independently
provider-verified six-thread snapshot. It is not an approval or contact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import re
import stat

from empire_os.workspace_solar_founder_review import (
    SNAPSHOT, WorkspaceReviewHeld, project_workspace_review,
)
from empire_os.workspace_solar_reply_tracking import ANCHORS

SCHEMA = "empire.workspace_historical_sent_manifest.v1"
HEXDIGEST = re.compile(r"^[a-f0-9]{64}$")
SIX = len(ANCHORS)
MAX_SOURCE_SIZE = 25000


class HistoricalManifestHeld(ValueError):
    """Invalid source or incomplete authenticated anchors: no partial manifest."""


def _iso(value: object) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise HistoricalManifestHeld("INVALID_SENT_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HistoricalManifestHeld("INVALID_SENT_TIMESTAMP") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoricalManifestHeld("INVALID_SENT_TIMESTAMP")
    return parsed.astimezone(timezone.utc).isoformat()


def build_historical_manifest(
    snapshot: Mapping[str, Any], *, now: datetime
) -> dict[str, Any]:
    """Extract only immutable source evidence; no approval, intent or CRM ID."""
    try:
        verified = project_workspace_review(snapshot, now=now)
    except (WorkspaceReviewHeld, AttributeError, TypeError) as e:
        raise HistoricalManifestHeld("WORKSPACE_SOURCE_NOT_VERIFIED") from None
    if (verified["monitored_threads"] != SIX
            or verified["sent_anchors_verified"] != SIX
            or snapshot.get("founder_crm_ingest_verified") is not False
            or snapshot.get("database_writes") is not False):
        raise HistoricalManifestHeld("UNTRUSTED_SOURCE_AUTHORITY")
    original = snapshot.get("threads")
    if not isinstance(original, list) or len(original) != SIX:
        raise HistoricalManifestHeld("INCOMPLETE_SOURCE")
    by_thread: dict[str, Mapping[str, Any]] = {}
    for record in original:
        if not isinstance(record, Mapping):
            raise HistoricalManifestHeld("INVALID_SOURCE_RECORD")
        tid = record.get("gmail_thread_id")
        if not isinstance(tid, str) or tid in by_thread:
            raise HistoricalManifestHeld("DUPLICATE_SOURCE_THREAD")
        by_thread[tid] = record
    if set(by_thread) != {a[3] for a in ANCHORS}:
        raise HistoricalManifestHeld("SOURCE_ANCHOR_DRIFT")
    receipt_records = []
    for company, _, recipient, thread, message in ANCHORS:
        record = by_thread[thread]
        if (record.get("company") != company
                or record.get("sent_message_id") != message
                or record.get("sent_verified_in_authenticated_mailbox") is not True):
            raise HistoricalManifestHeld("UNTRUSTED_ORIGINAL_SENT_ANCHOR")
        sent_at = _iso(record.get("sent_at"))
        recipient_hash = sha256(recipient.encode("utf-8")).hexdigest()
        evidence_payload = "|".join((
            "empire-historical-sent-v1", "EMPIRE_WORKSPACE_NOT_PERSONAL_GMAIL",
            thread, message, sent_at, recipient_hash,
        ))
        digest = sha256(evidence_payload.encode("ascii")).hexdigest()
        receipt_records.append({
            "company": company,
            "gmail_thread_id": thread,
            "original_provider_message_id": message,
            "sent_at": sent_at,
            "recipient_sha256": recipient_hash,
            "evidence_sha256": digest,
            "source_kind": "AUTHENTICATED_GMAIL_ORIGINAL_SENT_METADATA",
            "canonical_outbound_intent_admitted": False,
            "historical_approval_attested": False,
            "crm_contact_bound": False,
            "customer_revenue_verified": False,
        })
    receipt_records.sort(key=lambda r: r["company"])
    if (len(receipt_records) != SIX or
            len({r["evidence_sha256"] for r in receipt_records}) != SIX or
            len({r["gmail_thread_id"] for r in receipt_records}) != SIX):
        raise HistoricalManifestHeld("DUPLICATE_HISTORICAL_EVIDENCE")
    return {
        "schema_version": SCHEMA,
        "status": "SIX_EXTERNAL_SENT_RECEIPTS_READY_FOR_SEPARATE_DBA_REVIEW",
        "mode": "OBSERVE",
        "source": "existing_private_google_workspace_six_thread_snapshot",
        "source_scanned_at": verified["scanned_at"],
        "evidence_count": SIX,
        "items": receipt_records,
        "canonical_outbound_intents_created": 0,
        "canonical_sent_approvals_backfilled": 0,
        "crm_records_created": 0,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
        "production_schema_activation_authorized": False,
    }


def read_source_build_manifest(
    *, source: Path = SNAPSHOT, now: datetime | None = None,
) -> dict[str, Any]:
    if source != SNAPSHOT or source.is_symlink() or not source.is_file():
        raise HistoricalManifestHeld("UNTRUSTED_SOURCE_PATH")
    info = source.stat()
    if (not 0 < info.st_size <= MAX_SOURCE_SIZE
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise HistoricalManifestHeld("UNSAFE_SOURCE_PERMISSIONS")
    try:
        data = json.loads(source.read_text("utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise HistoricalManifestHeld("UNREADABLE_SOURCE") from None
    return build_historical_manifest(
        data, now=now or datetime.now(timezone.utc)
    )
