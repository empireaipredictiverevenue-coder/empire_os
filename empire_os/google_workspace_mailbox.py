"""First-party Workspace Gmail mailbox preview using the existing OAuth account.

No new provider, sender, timer or agent runtime. Read-only, bounded Gmail API
access. An independently verified Gmail account identity must equal the
founder's configured mailbox before any message metadata is retrieved.
This is provider-only evidence, never commercial or reply-send authority.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from empire_os.gmail_api_transport import GMAIL_SEND_SCOPE, build_gmail_service, _write_token
from empire_os.owned_imap_mailbox import MailboxReadUnavailable

READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SCOPES = [GMAIL_SEND_SCOPE, READ_SCOPE]
EXPECTED_ACCOUNT = "phil@mail.empire-ai.co.uk"
TOKEN_PATH = Path("/srv/empire_os/runtime/secrets/google-workspace-internal-token.json")
ID_PATTERN = re.compile(r"^workspace:(inbox|sent):([a-zA-Z0-9]{8,48})$")
MAX_LIST = 20


class GoogleWorkspaceMailboxProvider:
    provider = "google_workspace"
    suppression_evidence_complete = False

    def __init__(self, *, token_path: str | Path = TOKEN_PATH,
                 expected_account: str = EXPECTED_ACCOUNT,
                 service_factory: Callable[..., Any] | None = None):
        self.token_path = Path(token_path)
        self.expected_account = str(expected_account or "").strip().lower()
        self._service_factory = service_factory

    @property
    def configured(self) -> bool:
        if self.expected_account != EXPECTED_ACCOUNT or self.token_path.is_symlink():
            return False
        try:
            data = json.loads(self.token_path.read_text(encoding="utf-8"))
            return (isinstance(data, dict)
                    and bool(data.get("refresh_token"))
                    and set(SCOPES).issubset(set(data.get("scopes") or [])))
        except (OSError, ValueError, TypeError):
            return False

    def _service(self):
        if not self.configured:
            raise MailboxReadUnavailable("WORKSPACE_READ_SCOPE_NOT_AUTHORIZED")
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                _write_token(self.token_path, credentials.to_json())
            if not credentials.valid:
                raise ValueError("invalid_credentials")
            factory = self._service_factory or build_gmail_service
            api = factory(credentials)
            profile = api.users().getProfile(userId="me").execute()
            if str(profile.get("emailAddress") or "").strip().lower() != self.expected_account:
                raise MailboxReadUnavailable("WORKSPACE_ACCOUNT_IDENTITY_MISMATCH")
            return api
        except MailboxReadUnavailable:
            raise
        except Exception:
            raise MailboxReadUnavailable("WORKSPACE_READ_API_UNAVAILABLE") from None

    @staticmethod
    def _row(message: dict, *, role: str) -> dict[str, Any]:
        ident = str(message.get("id") or "")
        if not re.fullmatch(r"[a-zA-Z0-9]{8,48}", ident):
            raise MailboxReadUnavailable("WORKSPACE_INVALID_PROVIDER_ID")
        labels = message.get("labelIds") or []
        if not isinstance(labels, list) or ("INBOX" if role == "inbox" else "SENT") not in labels:
            raise MailboxReadUnavailable("WORKSPACE_UNEXPECTED_MAILBOX_LABEL")
        payload = message.get("payload") or {}
        raw_headers = payload.get("headers") or []
        if not isinstance(raw_headers, list) or len(raw_headers) > 200:
            raise MailboxReadUnavailable("WORKSPACE_HEADER_BOUND_EXCEEDED")
        headers = {}
        for item in raw_headers:
            if isinstance(item, dict):
                key = str(item.get("name") or "").casefold()
                if key in ("from", "to", "subject", "message-id", "in-reply-to", "references", "reply-to"):
                    headers.setdefault(key, str(item.get("value") or "")[:1024])
        occurred_at = None
        try:
            stamp = int(message.get("internalDate"))
            if 0 < stamp < 9999999999999:
                occurred_at = datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            pass
        # Gmail snippet is a bounded, untrusted preview, not the full message.
        snippet = str(message.get("snippet") or "")[:600]
        return {
            "id": f"workspace:{role}:{ident}",
            "message_id": headers.get("message-id") or None,
            "in_reply_to": headers.get("in-reply-to") or None,
            "references": headers.get("references") or None,
            "from": headers.get("from", ""),
            "to": [headers.get("to", "")] if headers.get("to") else [],
            "reply_to": [headers.get("reply-to", "")] if headers.get("reply-to") else [],
            "subject": headers.get("subject", ""),
            "text": snippet,
            "body_preview_only": True,
            "mailbox_internal_date": occurred_at,
            "mailbox_internal_date_observed": occurred_at is not None,
            "received_at": None,
            # Gmail internalDate is provider-observed ordering, not authenticated
            # proof of external SMTP delivery or canonical reply arrival.
            "created_at": occurred_at,
            "source_received_at_verified": False,
            "status": "sent" if role == "sent" else "received",
            "last_event": "sent" if role == "sent" else "received",
            "provider": "google_workspace",
            "canonical_contact_identity_verified": False,
            "canonical_thread_identity_verified": False,
        }

    def _read(self, role: str, *, limit: int, only: str | None = None) -> list[dict[str, Any]]:
        if role not in ("inbox", "sent") or type(limit) is not int or not 1 <= limit <= MAX_LIST:
            raise MailboxReadUnavailable("WORKSPACE_INVALID_BOUNDED_READ")
        api = self._service()
        label = "INBOX" if role == "inbox" else "SENT"
        try:
            if only is not None:
                match = ID_PATTERN.fullmatch(str(only))
                if match is None or match.group(1) != role:
                    raise MailboxReadUnavailable("WORKSPACE_MESSAGE_ID_MISMATCH")
                ids = [match.group(2)]
            else:
                response = api.users().messages().list(
                    userId="me", labelIds=[label], maxResults=limit,
                    fields="messages(id),nextPageToken",
                ).execute()
                ids = [str(row.get("id") or "") for row in (response.get("messages") or [])][:limit]
            rows = []
            for ident in ids:
                if not re.fullmatch(r"[a-zA-Z0-9]{8,48}", ident):
                    raise MailboxReadUnavailable("WORKSPACE_INVALID_PROVIDER_ID")
                item = api.users().messages().get(
                    userId="me", id=ident, format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Message-ID", "In-Reply-To", "References", "Reply-To"],
                    fields="id,labelIds,internalDate,snippet,payload(headers)",
                ).execute()
                rows.append(self._row(item, role=role))
            return rows
        except MailboxReadUnavailable:
            raise
        except Exception:
            raise MailboxReadUnavailable("WORKSPACE_READ_API_UNAVAILABLE") from None

    def list_received(self, *, limit: int) -> list[dict[str, Any]]:
        return self._read("inbox", limit=min(limit, MAX_LIST))

    def list_sent(self, *, limit: int) -> list[dict[str, Any]]:
        return self._read("sent", limit=min(limit, MAX_LIST))

    def list_suppressions(self, *, limit: int) -> list[dict[str, Any]]:
        return []  # Canonical suppression comes only from the existing governor.

    def get_received(self, email_id: str) -> dict[str, Any]:
        matches = self._read("inbox", limit=1, only=email_id)
        if len(matches) != 1:
            raise MailboxReadUnavailable("WORKSPACE_MESSAGE_NOT_FOUND")
        return matches[0]

    def get_sent(self, email_id: str) -> dict[str, Any]:
        matches = self._read("sent", limit=1, only=email_id)
        if len(matches) != 1:
            raise MailboxReadUnavailable("WORKSPACE_MESSAGE_NOT_FOUND")
        return matches[0]

    def readiness(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "configured": self.configured,
            "read_only": True,
            "canonical_identity_verified": False,
            "live_identity_check_required": True,
            "suppression_evidence_complete": False,
            "execution_authority": "none",
        }
