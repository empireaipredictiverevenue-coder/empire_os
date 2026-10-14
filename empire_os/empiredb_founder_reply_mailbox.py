"""Read canonically recorded EmpireOS email replies in the existing Founder API.

This is NOT a general email inbox. It reads only previously ingested EmpireDB
outbound replies and sent-intent records, using the existing limited
empire_closer_observer role. No migrations, no new runtime, no OAuth, no send.
Database role grants are defined in EmpireDB migration 016.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from datetime import datetime
from typing import Any, Callable

from empire_os.owned_imap_mailbox import MailboxReadUnavailable

MAX_ROWS = 50
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
READ_ROLE = "empire_closer_observer"
SYSTEMD_CREDENTIAL = "founder_reply_reader_dsn"

def _credential_from_systemd() -> str:
    directory = os.getenv("CREDENTIALS_DIRECTORY", "").strip()
    if not directory:
        return ""
    base = Path(directory)
    path = base / SYSTEMD_CREDENTIAL
    try:
        if not base.is_dir() or path.is_symlink() or not path.is_file():
            return ""
        info = path.stat()
        if not 0 < info.st_size <= 4096 or (stat.S_IMODE(info.st_mode) & 0o027):
            return ""
        secret = path.read_text(encoding="utf-8").strip()
        return secret if secret and "\n" not in secret and "\r" not in secret else ""
    except (OSError, UnicodeError):
        return ""
# SQL identifiers are fixed, not derived from user input. Recipient addresses
# and full bodies are never printed in health/readiness output.
RECEIVED_SQL = """
SELECT r.id, r.intent_id, r.from_contact, i.recipient, r.subject,
       r.body_text, r.received_at, r.classification,
       r.provider_message_id
FROM public.outbound_replies r
JOIN public.outbound_intents i ON i.id = r.intent_id
WHERE i.channel = 'email'
ORDER BY r.received_at DESC, r.id DESC
LIMIT %s
"""
SENT_SQL = """
SELECT i.id, i.recipient, i.subject, i.body_text, i.updated_at, i.status
FROM public.outbound_intents i
WHERE i.channel='email' AND i.status IN ('sent','delivered','replied')
ORDER BY i.updated_at DESC, i.id DESC
LIMIT %s
"""
RECEIVED_ONE_SQL = """
SELECT r.id, r.intent_id, r.from_contact, i.recipient, r.subject,
       r.body_text, r.received_at, r.classification,
       r.provider_message_id
FROM public.outbound_replies r
JOIN public.outbound_intents i ON i.id = r.intent_id
WHERE i.channel='email' AND r.id=%s::uuid
LIMIT 1
"""
SENT_ONE_SQL = """
SELECT i.id, i.recipient, i.subject, i.body_text, i.updated_at, i.status
FROM public.outbound_intents i
WHERE i.channel='email' AND i.id=%s::uuid
  AND i.status IN ('sent','delivered','replied')
LIMIT 1
"""


def _str_date(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


class EmpireDBFounderReplyMailbox:
    """Read-only canonical reply viewer, never sender or suppression reader."""

    provider = "empiredb_canonical_replies"
    suppression_evidence_complete = False

    def __init__(self, *, dsn: str | None = None, connect_factory: Callable[..., Any] | None = None):
        self.dsn = (dsn if dsn is not None else (_credential_from_systemd() or os.environ.get("EMPIRE_FOUNDER_REPLY_READER_DSN", ""))).strip()
        self._connect = connect_factory

    @property
    def configured(self) -> bool:
        return bool(self.dsn)

    def _run(self, query: str, parameter: int | str, *, expected_cols: int,
             max_rows: int = MAX_ROWS) -> list[tuple]:
        if not self.dsn:
            raise MailboxReadUnavailable("DEDICATED_CANONICAL_REPLY_READER_UNAVAILABLE")
        connect = self._connect
        if connect is None:
            import psycopg
            connect = psycopg.connect
        try:
            with connect(self.dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute("SET LOCAL ROLE " + READ_ROLE)
                    cur.execute("SET LOCAL statement_timeout = '4000ms'")
                    cur.execute(query, (parameter,))
                    rows = cur.fetchall()
                    cur.execute("ROLLBACK")
        except Exception:
            raise MailboxReadUnavailable("CANONICAL_REPLY_READ_FAILED") from None
        if (not isinstance(rows, list) or len(rows) > max_rows
                or any(not isinstance(x, (tuple, list)) or len(x) != expected_cols for x in rows)):
            raise MailboxReadUnavailable("CANONICAL_REPLY_SCHEMA_MISMATCH")
        return rows

    @staticmethod
    def _received(row: tuple) -> dict[str, Any]:
        ident, intent, sender, recipient, subject, body, stamp, classification, provider_id = row
        if not all((ident, intent, sender, recipient, stamp)):
            raise MailboxReadUnavailable("CANONICAL_REPLY_INCOMPLETE")
        return {
            "id": "canonical-reply:" + str(ident),
            "intent_id": str(intent),
            "from": str(sender),
            "to": [str(recipient)],
            "subject": str(subject or ""),
            "text": str(body or "")[:300],
            "body_preview_only": True,
            "received_at": _str_date(stamp),
            "created_at": _str_date(stamp),
            "status": "received",
            "provider": "empiredb_canonical_replies",
            "recorded_classification_unverified": str(classification or "unclassified"),
            "provider_message_id_observed": bool(provider_id),
            "canonical_person_identity_verified": False,
            "commercial_buying_intent_verified": False,
            "outreach_authorized": False,
        }

    @staticmethod
    def _sent(row: tuple) -> dict[str, Any]:
        ident, recipient, subject, body, stamp, status = row
        if not ident or not recipient or status not in ("sent", "delivered", "replied"):
            raise MailboxReadUnavailable("CANONICAL_SENT_INTENT_INCOMPLETE")
        return {
            "id": "canonical-intent:" + str(ident),
            "from": "",  # Sender identity must be checked against actual delivery separately.
            "to": [str(recipient)],
            "subject": str(subject or ""),
            "text": str(body or "")[:300],
            "body_preview_only": True,
            "created_at": _str_date(stamp),
            "status": str(status),
            "canonical_intent_state_only": True,
            "verified_provider_delivery": False,
            "outreach_authorized": False,
            "provider": "empiredb_canonical_replies",
        }

    @staticmethod
    def _bounded_limit(limit: int) -> int:
        if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
            raise MailboxReadUnavailable("CANONICAL_REPLY_ROW_LIMIT_REQUIRED")
        return limit

    @staticmethod
    def _extract_id(value: str, prefix: str) -> str:
        text = str(value or "")
        candidate = text.removeprefix(prefix)
        if not text.startswith(prefix) or not _UUID.fullmatch(candidate):
            raise MailboxReadUnavailable("CANONICAL_MESSAGE_IDENTIFIER_UNVERIFIED")
        return candidate

    def list_received(self, *, limit: int) -> list[dict[str, Any]]:
        rows = self._run(RECEIVED_SQL, self._bounded_limit(limit), expected_cols=9)
        return [self._received(row) for row in rows]

    def list_sent(self, *, limit: int) -> list[dict[str, Any]]:
        rows = self._run(SENT_SQL, self._bounded_limit(limit), expected_cols=6)
        return [self._sent(row) for row in rows]

    def list_suppressions(self, *, limit: int) -> list[dict[str, Any]]:
        return []  # A separate authorised suppression gate remains mandatory.

    def get_received(self, email_id: str) -> dict[str, Any]:
        rows = self._run(RECEIVED_ONE_SQL, self._extract_id(email_id, "canonical-reply:"), expected_cols=9, max_rows=1)
        if len(rows) != 1:
            raise MailboxReadUnavailable("CANONICAL_REPLY_NOT_FOUND")
        return self._received(rows[0])

    def get_sent(self, email_id: str) -> dict[str, Any]:
        rows = self._run(SENT_ONE_SQL, self._extract_id(email_id, "canonical-intent:"), expected_cols=6, max_rows=1)
        if len(rows) != 1:
            raise MailboxReadUnavailable("CANONICAL_SENT_INTENT_NOT_FOUND")
        return self._sent(rows[0])

    def readiness(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "configured": self.configured,
            "scope": "CANONICAL_RECORDED_REPLIES_ONLY_NOT_GENERAL_INBOX",
            "read_only": True,
            "canonical_person_identity_verified": False,
            "canonical_buyer_conversation_verified": False,
            "suppression_evidence_complete": False,
            "execution_authority": "none",
        }
