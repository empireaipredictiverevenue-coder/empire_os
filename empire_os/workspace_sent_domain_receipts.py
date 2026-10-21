"""Bounded authenticated Workspace SENT metadata for duplicate-contact holds.

Only domain, provider message ID and date are retained; never subject/body,
email address or permission to send. A SENT label does not prove SMTP delivery.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from email.utils import getaddresses
from pathlib import Path
import json
import re
import stat

from empire_os.buyer_network_research_rotation import accepted_domain

SCHEMA = "empire.workspace_sent_domain_receipts.v1"
SOURCE = "authenticated_workspace_gmail_sent_metadata"
ACCOUNT = "phil@empire-ai.co.uk"
SENDERS = frozenset({ACCOUNT, "phil@mail.empire-ai.co.uk"})
MAX_DOMAINS = 2000
MAX_BYTES = 400_000
MESSAGE_ID = re.compile(r"workspace:sent:[a-zA-Z0-9]{8,48}")


class WorkspaceSentHistoryError(ValueError):
    pass


def read_previous(path: Path) -> dict | None:
    if not path.exists() and not path.is_symlink():
        return None
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > MAX_BYTES
            or stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise WorkspaceSentHistoryError("WORKSPACE_SENT_SOURCE_UNSAFE")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise WorkspaceSentHistoryError("WORKSPACE_SENT_SOURCE_UNREADABLE") from exc
    if (not isinstance(document, dict)
            or document.get("schema_version") != SCHEMA
            or document.get("source") != SOURCE
            or document.get("account") != ACCOUNT
            or document.get("outbound_authorized") is not False
            or document.get("delivery_verified") is not False
            or not isinstance(document.get("domains"), list)
            or len(document["domains"]) > MAX_DOMAINS):
        raise WorkspaceSentHistoryError("WORKSPACE_SENT_SOURCE_INVALID")
    for row in document["domains"]:
        if (not isinstance(row, dict)
                or not accepted_domain(str(row.get("domain") or ""))
                or not MESSAGE_ID.fullmatch(str(row.get("gmail_message_id") or ""))
                or not isinstance(row.get("last_sent_at"), str)):
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_SOURCE_ROW_INVALID")
    return document


def capture(rows: list[dict], previous: dict | None = None, *,
            now: datetime | None = None) -> dict:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise WorkspaceSentHistoryError("WORKSPACE_CLOCK_UNSAFE")
    if not isinstance(rows, list) or len(rows) > 20:
        raise WorkspaceSentHistoryError("WORKSPACE_SENT_BATCH_UNBOUNDED")
    old = previous or {}
    prior = old.get("domains", [])
    if not isinstance(prior, list):
        raise WorkspaceSentHistoryError("WORKSPACE_PRIOR_ROWS_UNSAFE")
    by_domain: dict[str, dict] = {}
    for row in prior:
        if not isinstance(row, dict) or not accepted_domain(str(row.get("domain") or "")):
            raise WorkspaceSentHistoryError("WORKSPACE_PRIOR_ROW_UNSAFE")
        by_domain[row["domain"]] = dict(row)
    scanned = 0
    verified_messages = 0
    for row in rows:
        if not isinstance(row, dict):
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_ROW_UNSAFE")
        ident = str(row.get("id") or "")
        if (not MESSAGE_ID.fullmatch(ident)
                or row.get("provider") != "google_workspace"
                or row.get("status") != "sent"):
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_UNVERIFIED_PROVIDER_METADATA")
        timestamp = row.get("mailbox_internal_date")
        try:
            sent = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError as exc:
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_TIME_INVALID") from exc
        if (sent.tzinfo is None or sent.timestamp() <= 0
                or sent > clock.astimezone(timezone.utc).replace(microsecond=0) +
                timedelta(minutes=5)):
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_TIME_INVALID")
        scanned += 1
        sender = [address.lower() for _, address in getaddresses([str(row.get("from") or "")])]
        if len(sender) != 1 or sender[0] not in SENDERS:
            continue
        verified_messages += 1
        recipient_headers = row.get("to")
        if not isinstance(recipient_headers, list) or len(recipient_headers) > 12:
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_RECIPIENTS_UNBOUNDED")
        addresses = getaddresses(recipient_headers)
        if len(addresses) > 12:
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_RECIPIENTS_UNBOUNDED")
        for _, address in addresses:
            if "@" not in address:
                continue
            domain = address.rsplit("@", 1)[-1].strip().lower().rstrip(".")
            if domain in ("empire-ai.co.uk", "mail.empire-ai.co.uk"):
                continue
            if not accepted_domain(domain):
                continue
            candidate = {"domain": domain, "gmail_message_id": ident,
                         "last_sent_at": sent.astimezone(timezone.utc).isoformat()}
            old_row = by_domain.get(domain)
            if old_row is None or candidate["last_sent_at"] > old_row["last_sent_at"]:
                by_domain[domain] = candidate
    if len(by_domain) > MAX_DOMAINS:
        raise WorkspaceSentHistoryError("WORKSPACE_SENT_HISTORY_LIMIT_REACHED")
    return {
        "schema_version": SCHEMA,
        "source": SOURCE,
        "account": ACCOUNT,
        "scanned_at": clock.astimezone(timezone.utc).isoformat(),
        "scanned_message_count": scanned,
        "verified_sender_message_count": verified_messages,
        "scanned_last_20_only": True,
        "complete_mailbox_history_verified": False,
        "outbound_authorized": False,
        "delivery_verified": False,
        "message_bodies_or_subjects_retained": False,
        "domain_count": len(by_domain),
        "domains": [by_domain[d] for d in sorted(by_domain)],
    }
