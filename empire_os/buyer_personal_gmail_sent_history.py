"""Bounded founder-reviewed Gmail SENT receipts; original buyer history guard only.

The source is a private, exact-ID snapshot reviewed against the connected
personal Gmail account. It is NOT a live mailbox sync, delivery proof, customer
consent, buyer approval, or permission to send anything.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import stat

SCHEMA = "empire.buyer_personal_gmail_historical_sent.v1"
SOURCE = "founder_reviewed_connected_personal_gmail_sent_metadata"
MAILBOX = "flavag83@gmail.com"
HEX = re.compile(r"^[a-f0-9]{16,32}$")
DOMAIN = re.compile(r"^(?!-)[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
EMAIL = re.compile(r"^[a-z0-9._%+-]+@([a-z0-9-]+(?:\.[a-z0-9-]+)+)$")


def read_personal_gmail_sent_receipts(
    path: Path, *, now: datetime | None = None
) -> dict[str, dict]:
    """Return only exact prior-sent identity holds; malformed input blocks."""
    if not path.exists() and not path.is_symlink():
        return {}
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > 24_000
            or stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise ValueError("PERSONAL_GMAIL_SENT_SOURCE_UNSAFE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("PERSONAL_GMAIL_SENT_SOURCE_UNREADABLE") from exc
    if (not isinstance(data, dict)
            or set(data) != {"schema_version", "source", "mailbox",
                             "outbound_authorized", "buyer_approved", "receipts"}
            or data["schema_version"] != SCHEMA
            or data["source"] != SOURCE
            or data["mailbox"] != MAILBOX
            or data["outbound_authorized"] is not False
            or data["buyer_approved"] is not False
            or not isinstance(data["receipts"], list)
            or len(data["receipts"]) > 24):
        raise ValueError("PERSONAL_GMAIL_SENT_SCHEMA_INVALID")
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    result: dict[str, dict] = {}
    exact = {
        "domain", "recipient", "provider_sent_message_id", "provider_thread_id",
        "sent_at", "provider_label", "delivery_verified", "buyer_approved",
        "outbound_authorized",
    }
    for row in data["receipts"]:
        if not isinstance(row, dict) or set(row) != exact:
            raise ValueError("PERSONAL_GMAIL_SENT_ROW_INVALID")
        domain = row["domain"]
        recipient = row["recipient"]
        match = EMAIL.fullmatch(recipient) if isinstance(recipient, str) else None
        if (not isinstance(domain, str)
                or not DOMAIN.fullmatch(domain)
                or domain in result
                or match is None or match.group(1) != domain
                or not isinstance(row["provider_sent_message_id"], str)
                or not HEX.fullmatch(row["provider_sent_message_id"])
                or not isinstance(row["provider_thread_id"], str)
                or not HEX.fullmatch(row["provider_thread_id"])
                or row["provider_label"] != "SENT"
                or row["delivery_verified"] is not False
                or row["buyer_approved"] is not False
                or row["outbound_authorized"] is not False):
            raise ValueError("PERSONAL_GMAIL_SENT_UNTRUSTED_PROOF")
        try:
            when = datetime.fromisoformat(row["sent_at"])
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("PERSONAL_GMAIL_SENT_TIME_INVALID") from exc
        if (when.tzinfo is None or when.utcoffset() is None
                or not datetime(2024, 1, 1, tzinfo=timezone.utc) <=
                when.astimezone(timezone.utc) <= clock):
            raise ValueError("PERSONAL_GMAIL_SENT_TIME_INVALID")
        result[domain] = {
            "sent_at": when.astimezone(timezone.utc).isoformat(),
            "sent_message_id": row["provider_sent_message_id"],
            "thread_id": row["provider_thread_id"],
            "source": "FOUNDER_REVIEWED_PERSONAL_GMAIL_SENT_RECEIPT",
        }
    return result
