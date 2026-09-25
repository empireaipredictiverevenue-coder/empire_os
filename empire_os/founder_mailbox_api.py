"""Read-only Founder API for Empire Mail."""
from __future__ import annotations

import os
from email.utils import parseaddr
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query
import requests

from empire_os.empire_mailbox import build_mailbox, mailbox_thread


DEFAULT_OUTBOUND_ENV = Path("/srv/empire_os/runtime/secrets/outbound.env")
_SAFE_IDENTITY_KEYS = {"EMPIRE_OUTBOUND_FROM", "EMPIRE_REPLY_TO"}
_RESEND_KEY_NAMES = {"RESEND_API_KEY", "RESEND_RECEIVING_API_KEY"}


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

    def list_suppressions(self, *, limit: int) -> list[dict[str, Any]]:
        return self._rows(self._get("/suppressions", params={"limit": limit}))

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
        self.sending_api_key = sending
        self.receiving_api_key = receiving
        self.timeout_s = timeout_s

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        receiving: bool = False,
    ) -> Any:
        key = self.receiving_api_key if receiving else self.sending_api_key
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
        return self._rows(self._get("/emails", params={"limit": limit}))

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

    def get_sent(self, email_id: str) -> dict[str, Any]:
        payload = self._get(f"/emails/{email_id}")
        return dict(payload) if isinstance(payload, dict) else {}

    def get_received(self, email_id: str) -> dict[str, Any]:
        payload = self._get(f"/emails/receiving/{email_id}", receiving=True)
        return dict(payload) if isinstance(payload, dict) else {}


def create_founder_mailbox_router(
    provider: MailboxProvider | None = None,
    *,
    identity_env_path: Path = DEFAULT_OUTBOUND_ENV,
) -> APIRouter:
    source = provider or ResendMailboxProvider(
        secret_env_path=identity_env_path,
    )
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
        mailbox = build_mailbox(sent, received, suppressions)
        mailbox["identity"] = read_mail_identity(identity_env_path)
        cache[limit] = (now + 10.0, mailbox)
        return mailbox

    @router.get("/summary")
    def summary(limit: int = Query(default=50, ge=1, le=100)):
        mailbox = snapshot(limit)
        return {
            "schema_version": mailbox["schema_version"],
            "mode": mailbox["mode"],
            "read_only": True,
            "execution_authority": "none",
            "provider": mailbox["provider"],
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
                    "message_id": str(detail.get("message_id") or event.get("message_id") or "").strip() or None,
                }})
            except Exception:
                hydrated.append(event)
        row["events"] = hydrated
        row["read_only"] = True
        row["execution_authority"] = "none"
        row["email_sends"] = False
        return row

    return router
