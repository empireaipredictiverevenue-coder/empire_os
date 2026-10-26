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
INBOX_ID = re.compile(r"workspace:inbox:[a-zA-Z0-9]{8,48}")
MAX_REPLY_OBSERVATIONS = 1000


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
    receipts = document.get("reciprocal_threads", [])
    if not isinstance(receipts, list) or len(receipts) > MAX_REPLY_OBSERVATIONS:
        raise WorkspaceSentHistoryError("WORKSPACE_REPLY_EVIDENCE_INVALID")
    seen_domains = set()
    for row in receipts:
        if (not isinstance(row, dict)
                or not accepted_domain(str(row.get("domain") or ""))
                or row["domain"] in seen_domains
                or not INBOX_ID.fullmatch(str(row.get("inbound_gmail_message_id") or ""))
                or not MESSAGE_ID.fullmatch(str(row.get("reply_gmail_message_id") or ""))
                or not isinstance(row.get("inbound_at"), str)
                or not isinstance(row.get("reply_at"), str)
                or row.get("buyer_approval_verified") is not False
                or row.get("outbound_authorized") is not False):
            raise WorkspaceSentHistoryError("WORKSPACE_REPLY_EVIDENCE_INVALID")
        seen_domains.add(row["domain"])
    return document



def reciprocal_observations(
    sent_rows: list[dict], received_rows: list[dict],
    previous: dict | None, clock: datetime,
) -> list[dict]:
    """Exact authenticated Workspace mail-header reply pairing, no bodies."""
    if not isinstance(received_rows, list) or len(received_rows) > 20:
        raise WorkspaceSentHistoryError("WORKSPACE_INBOX_BATCH_UNBOUNDED")
    by_domain = {}
    for old in (previous or {}).get("reciprocal_threads", []):
        if isinstance(old, dict):
            by_domain[old["domain"]] = dict(old)
    incoming = {}
    for row in received_rows:
        if (not isinstance(row, dict) or
                not INBOX_ID.fullmatch(str(row.get("id") or "")) or
                row.get("provider") != "google_workspace" or
                row.get("status") != "received"):
            raise WorkspaceSentHistoryError("WORKSPACE_INBOX_PROVIDER_UNVERIFIED")
        origins = getaddresses([str(row.get("from") or "")])
        if len(origins) != 1 or "@" not in origins[0][1]:
            continue
        domain = origins[0][1].rsplit("@", 1)[-1].strip().lower()
        rfc_id = str(row.get("message_id") or "").strip()
        if (not accepted_domain(domain) or domain in ("empire-ai.co.uk","mail.empire-ai.co.uk")
                or not 3 <= len(rfc_id) <= 255 or not rfc_id.startswith("<")
                or not rfc_id.endswith(">")):
            continue
        try:
            inbound_at = datetime.fromisoformat(str(row.get("mailbox_internal_date") or ""))
        except ValueError:
            continue
        if (inbound_at.tzinfo is None or inbound_at.timestamp() <= 0
                or inbound_at > clock + timedelta(minutes=5)):
            continue
        incoming[(domain, rfc_id)] = (row["id"], inbound_at.astimezone(timezone.utc))
    for row in sent_rows:
        if not isinstance(row, dict) or row.get("provider") != "google_workspace":
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_UNVERIFIED_PROVIDER_METADATA")
        sender = getaddresses([str(row.get("from") or "")])
        if len(sender) != 1 or sender[0][1].lower() not in SENDERS:
            continue
        recipient_headers = row.get("to") or []
        if not isinstance(recipient_headers, list) or len(recipient_headers) > 12:
            raise WorkspaceSentHistoryError("WORKSPACE_SENT_RECIPIENTS_UNBOUNDED")
        recipients = getaddresses(recipient_headers)
        if len(recipients) != 1 or "@" not in recipients[0][1]:
            continue
        domain = recipients[0][1].rsplit("@",1)[-1].strip().lower()
        reply_id = str(row.get("in_reply_to") or "").strip()
        candidate = incoming.get((domain, reply_id))
        if not candidate or reply_id not in str(row.get("references") or ""):
            continue
        try:
            sent_at = datetime.fromisoformat(str(row.get("mailbox_internal_date") or ""))
        except ValueError:
            continue
        if (sent_at.tzinfo is None or sent_at.astimezone(timezone.utc) <
                candidate[1] or sent_at > clock + timedelta(minutes=5)):
            continue
        record = {
            "domain": domain,
            "inbound_gmail_message_id": candidate[0],
            "reply_gmail_message_id": row["id"],
            "inbound_at": candidate[1].isoformat(),
            "reply_at": sent_at.astimezone(timezone.utc).isoformat(),
            "buyer_approval_verified": False,
            "outbound_authorized": False,
        }
        old = by_domain.get(domain)
        if old is None or record["reply_at"] > old["reply_at"]:
            by_domain[domain] = record
    if len(by_domain) > MAX_REPLY_OBSERVATIONS:
        raise WorkspaceSentHistoryError("WORKSPACE_REPLY_HISTORY_LIMIT_REACHED")
    return [by_domain[k] for k in sorted(by_domain)]

def capture(rows: list[dict], previous: dict | None = None, *,
            now: datetime | None = None, received_rows: list[dict] | None = None) -> dict:
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
        "reciprocal_threads": reciprocal_observations(
            rows, received_rows or [], previous, clock,
        ),
        "reciprocal_mail_is_not_buyer_acceptance": True,
    }
