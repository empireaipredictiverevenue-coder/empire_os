"""Read-only Founder API for Empire Mail."""
from __future__ import annotations

import os
from email.utils import parseaddr
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query
import requests

from empire_os.closer_reply_draft import build_closer_reply
from empire_os.empire_mailbox import build_mailbox, mailbox_thread
from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider
from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider
from empire_os.empiredb_founder_reply_mailbox import EmpireDBFounderReplyMailbox
from empire_os.workspace_solar_founder_review import (
    WorkspaceReviewHeld, read_workspace_review,
)
from empire_os.workspace_solar_canonical_intent_review import (
    CanonicalIntentReviewUnavailable, review_six_workspace_canonical_intents,
)


DEFAULT_OUTBOUND_ENV = Path("/srv/empire_os/runtime/secrets/outbound.env")
_SAFE_IDENTITY_KEYS = {"EMPIRE_OUTBOUND_FROM", "EMPIRE_REPLY_TO"}
_RESEND_KEY_NAMES = {
    "RESEND_API_KEY",
    "RESEND_RECEIVING_API_KEY",
    "RESEND_MAILBOX_API_KEY",
}


def _read_selected_env_keys(
    env_path: Path,
    names: set[str],
) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in names:
                values[key] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def read_mail_identity(env_path: Path = DEFAULT_OUTBOUND_ENV) -> dict[str, Any]:
    values = {
        key: os.getenv(key, "").strip()
        for key in _SAFE_IDENTITY_KEYS
    }
    if not all(values.values()):
        from_file = _read_selected_env_keys(env_path, _SAFE_IDENTITY_KEYS)
        for key in _SAFE_IDENTITY_KEYS:
            if not values.get(key):
                values[key] = from_file.get(key, "")

    sender = values.get("EMPIRE_OUTBOUND_FROM") or None
    sender_email = parseaddr(sender or "")[1].strip().lower() or None
    reply_to = values.get("EMPIRE_REPLY_TO") or None
    return {
        "sender": sender,
        "sender_email": sender_email,
        "reply_to": reply_to,
        "observed": bool(sender and reply_to),
    }


class MailboxProvider(Protocol):
    def list_sent(self, *, limit: int) -> list[dict[str, Any]]:
        ...

    def list_received(self, *, limit: int) -> list[dict[str, Any]]:
        ...

    def list_suppressions(self, *, limit: int) -> list[dict[str, Any]]:
        ...

    def get_sent(self, email_id: str) -> dict[str, Any]:
        ...

    def get_received(self, email_id: str) -> dict[str, Any]:
        ...


class ResendMailboxProvider:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        receiving_api_key: str | None = None,
        mailbox_api_key: str | None = None,
        secret_env_path: Path = DEFAULT_OUTBOUND_ENV,
        timeout_s: float = 10.0,
    ):
        file_keys = _read_selected_env_keys(secret_env_path, _RESEND_KEY_NAMES)
        sending = (
            api_key
            or os.getenv("RESEND_API_KEY", "").strip()
            or file_keys.get("RESEND_API_KEY", "")
        )
        receiving = (
            receiving_api_key
            or os.getenv("RESEND_RECEIVING_API_KEY", "").strip()
            or file_keys.get("RESEND_RECEIVING_API_KEY", "")
            or sending
        )
        mailbox = (
            mailbox_api_key
            or os.getenv("RESEND_MAILBOX_API_KEY", "").strip()
            or file_keys.get("RESEND_MAILBOX_API_KEY", "")
            or sending
        )
        self.sending_api_key = sending
        self.receiving_api_key = receiving
        self.mailbox_api_key = mailbox
        self.timeout_s = timeout_s

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        receiving: bool = False,
        mailbox: bool = False,
    ) -> Any:
        if receiving and mailbox:
            raise ValueError("mailbox_and_receiving_are_mutually_exclusive")
        key = (
            self.receiving_api_key
            if receiving
            else self.mailbox_api_key
            if mailbox
            else self.sending_api_key
        )
        if not key:
            raise RuntimeError("resend_api_key_missing")
        response = requests.get(
            "https://api.resend.com" + path,
            params=params,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
            },
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return [dict(row) for row in payload["data"] if isinstance(row, dict)]
        return []

    def list_sent(self, *, limit: int) -> list[dict[str, Any]]:
        return self._rows(
            self._get("/emails", params={"limit": limit}, mailbox=True)
        )

    def list_received(self, *, limit: int) -> list[dict[str, Any]]:
        rows = self._rows(
            self._get("/emails/receiving", params={"limit": limit}, receiving=True)
        )
        hydrated: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            email_id = str(row.get("id") or "").strip()
            if not email_id or index >= 25:
                hydrated.append(row)
                continue
            try:
                detail = self.get_received(email_id)
                hydrated.append({**row, **detail})
            except Exception:
                hydrated.append(row)
        return hydrated

    def list_suppressions(self, *, limit: int) -> list[dict[str, Any]]:
        return self._rows(
            self._get("/suppressions", params={"limit": limit}, mailbox=True)
        )

    def get_sent(self, email_id: str) -> dict[str, Any]:
        payload = self._get(f"/emails/{email_id}", mailbox=True)
        return dict(payload) if isinstance(payload, dict) else {}

    def get_received(self, email_id: str) -> dict[str, Any]:
        payload = self._get(f"/emails/receiving/{email_id}", receiving=True)
        return dict(payload) if isinstance(payload, dict) else {}


def create_founder_mailbox_router(
    provider: MailboxProvider | None = None,
    *,
    identity_env_path: Path = DEFAULT_OUTBOUND_ENV,
) -> APIRouter:
    if provider is None:
        # Preserve owned IMAP by default. Explicit first-party Google Workspace
        # OAuth reads reuse the *existing* account, never Resend or AWS.
        mode = os.getenv('EMPIRE_FOUNDER_MAILBOX_PROVIDER', 'owned_imap').strip().lower()
        if mode in ('owned_imap', 'imap'):
            source: MailboxProvider = OwnedIMAPMailboxProvider()
        elif mode == 'google_workspace':
            source = GoogleWorkspaceMailboxProvider()
        elif mode == 'empiredb_canonical_replies':
            # Explicit private source for previously ingested EmpireDB replies.
            # It does not represent a general professional email inbox.
            source = EmpireDBFounderReplyMailbox()
        else:
            raise RuntimeError('FOUNDER_MAILBOX_PROVIDER_NOT_AUTHORIZED')
    else:
        source = provider
    router = APIRouter(prefix="/v1/founder-mailbox", tags=["founder-mailbox"])
    cache: dict[int, tuple[float, dict[str, Any]]] = {}

    def snapshot(limit: int) -> dict[str, Any]:
        cached = cache.get(limit)
        now = monotonic()
        if cached is not None and cached[0] > now:
            return cached[1]
        try:
            sent = source.list_sent(limit=limit)
            received = source.list_received(limit=limit)
            suppressions = source.list_suppressions(limit=100)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"mailbox_provider_unavailable:{type(exc).__name__}",
            ) from exc
        provider_name = str(getattr(source, 'provider', 'resend'))
        suppression_complete = getattr(source, 'suppression_evidence_complete', True) is True
        mailbox = build_mailbox(
            sent, received, suppressions,
            provider=provider_name,
            suppression_evidence_complete=suppression_complete,
        )
        mailbox["identity"] = read_mail_identity(identity_env_path)
        cache[limit] = (now + 10.0, mailbox)
        return mailbox

    @router.get('/readiness')
    def readiness():
        if isinstance(source, (OwnedIMAPMailboxProvider, GoogleWorkspaceMailboxProvider, EmpireDBFounderReplyMailbox)):
            details = source.readiness()
            return {
                'status': 'READY_FOR_READ_PROBE' if details['configured'] else 'NOT_CONFIGURED',
                **details,
            }
        return {
            'status': 'INJECTED_PROVIDER_UNVERIFIED',
            'provider': str(getattr(source, 'provider', 'injected')),
            'configured': False,
            'canonical_identity_verified': False,
            'suppression_evidence_complete': False,
            'execution_authority': 'none',
        }

    @router.get("/summary")
    def summary(limit: int = Query(default=50, ge=1, le=100)):
        mailbox = snapshot(limit)
        return {
            "schema_version": mailbox["schema_version"],
            "mode": mailbox["mode"],
            "read_only": True,
            "execution_authority": "none",
            "provider": mailbox["provider"],
            "canonical_buyer_conversation_verified": False,
            "suppression_evidence_complete": mailbox['suppression_evidence_complete'],
            "identity": mailbox["identity"],
            "summary": mailbox["summary"],
        }

    @router.get("/threads")
    def threads(limit: int = Query(default=50, ge=1, le=100)):
        mailbox = snapshot(limit)
        return {
            **mailbox,
            "threads": [
                {key: value for key, value in row.items() if key != "events"}
                for row in mailbox["threads"]
            ],
        }


    @router.get("/workspace-solar-canonical-intent-review")
    def workspace_solar_canonical_intent_review():
        """Six exact canonical intent counts, never a CRM promotion or write."""
        try:
            return review_six_workspace_canonical_intents()
        except (CanonicalIntentReviewUnavailable, OSError, ValueError):
            raise HTTPException(
                status_code=503,
                detail="workspace_solar_canonical_intent_review_unavailable",
            ) from None

    @router.get("/workspace-solar-reply-review")
    def workspace_solar_reply_review():
        """Founder-only local read surface; no canonical CRM promotion.

        This router runs on the existing loopback-only Founder Read API.
        Source is a private authenticated Gmail metadata snapshot, not a
        tenant-scoped canonical CRM relationship or a public intake record.
        """
        try:
            return read_workspace_review()
        except (WorkspaceReviewHeld, OSError, ValueError):
            raise HTTPException(
                status_code=503,
                detail="workspace_solar_review_evidence_unavailable",
            ) from None

    @router.get("/draft-preview")
    def draft_preview(
        thread_id: str,
        limit: int = Query(default=80, ge=1, le=100),
    ):
        mailbox = snapshot(limit)
        row = mailbox_thread(mailbox, thread_id)
        if row is None:
            raise HTTPException(status_code=404, detail="mail_thread_not_found")
        if row.get("suppressed") is True:
            raise HTTPException(status_code=409, detail="recipient_suppressed")
        if mailbox.get('suppression_evidence_complete') is not True:
            raise HTTPException(status_code=409, detail='suppression_evidence_not_verified')
        if mailbox.get('canonical_buyer_conversation_verified') is not True and (
            mailbox.get('provider') == 'owned_imap'
        ):
            raise HTTPException(status_code=409, detail='canonical_buyer_thread_not_verified')

        inbound = next(
            (
                event
                for event in row.get("events") or []
                if event.get("direction") == "inbound"
            ),
            None,
        )
        if inbound is None:
            raise HTTPException(status_code=409, detail="inbound_reply_required")

        classification = str(
            inbound.get("classification") or ""
        ).strip().lower()
        if classification not in {"positive", "question", "objection"}:
            raise HTTPException(
                status_code=409,
                detail="commercial_reply_not_draft_eligible",
            )

        sender_name = parseaddr(str(inbound.get("from") or ""))[0].strip()
        draft = build_closer_reply({
            "classification": classification,
            "reply_body_text": inbound.get("body_text"),
            "root_subject": row.get("subject"),
            "contact_name": sender_name,
        })
        return {
            "schema_version": "empire.mailbox_draft_preview.v1",
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "outbound_send_authority": False,
            "thread_id": row.get("thread_id"),
            "intent_id": row.get("intent_id"),
            "classification": classification,
            "draft": draft,
            "context": {
                "business_name": None,
                "market": None,
                "pricing": None,
                "capacity": None,
            },
            "unknowns_preserved": True,
        }

    @router.get("/threads/{thread_id:path}")
    def thread(thread_id: str, limit: int = Query(default=100, ge=1, le=100)):
        mailbox = snapshot(limit)
        row = mailbox_thread(mailbox, thread_id)
        if row is None:
            raise HTTPException(status_code=404, detail="mail_thread_not_found")

        # Hydrate selected events only. Failure leaves body unknown rather than
        # fabricating or blocking the read model.
        hydrated: list[dict[str, Any]] = []
        for event in row.get("events") or []:
            provider_id = str(event.get("provider_id") or "").strip()
            if not provider_id:
                hydrated.append(event)
                continue
            try:
                detail = (
                    source.get_received(provider_id)
                    if event.get("direction") == "inbound"
                    else source.get_sent(provider_id)
                )
                hydrated.append({**event, **{
                    "body_text": str(detail.get("text") or event.get("body_text") or "").strip() or None,
                    "message_id": (
                        str(detail.get("message_id") or event.get("message_id") or "").strip() or None
                    ) if mailbox.get('provider') not in ('owned_imap', 'google_workspace', 'empiredb_canonical_replies') else None,
                }})
            except Exception:
                hydrated.append(event)
        row["events"] = hydrated
        row["read_only"] = True
        row["execution_authority"] = "none"
        row["email_sends"] = False
        return row

    return router
