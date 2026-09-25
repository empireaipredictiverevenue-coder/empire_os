"""Read-only Founder API for Empire Mail."""
from __future__ import annotations

import os
from time import monotonic
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query
import requests

from empire_os.empire_mailbox import build_mailbox, mailbox_thread


class MailboxProvider(Protocol):
    def list_sent(self, *, limit: int) -> list[dict[str, Any]]:
        ...

    def list_received(self, *, limit: int) -> list[dict[str, Any]]:
        ...

    def get_sent(self, email_id: str) -> dict[str, Any]:
        ...

    def get_received(self, email_id: str) -> dict[str, Any]:
        ...


class ResendMailboxProvider:
    def __init__(self, api_key: str | None = None, timeout_s: float = 10.0):
        self.api_key = (
            api_key
            or os.getenv("RESEND_RECEIVING_API_KEY", "").strip()
            or os.getenv("RESEND_API_KEY", "").strip()
        )
        self.timeout_s = timeout_s

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise RuntimeError("resend_api_key_missing")
        response = requests.get(
            "https://api.resend.com" + path,
            params=params,
            headers={
                "Authorization": f"Bearer {self.api_key}",
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
            self._get("/emails/receiving", params={"limit": limit})
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
        payload = self._get(f"/emails/receiving/{email_id}")
        return dict(payload) if isinstance(payload, dict) else {}


def create_founder_mailbox_router(
    provider: MailboxProvider | None = None,
) -> APIRouter:
    source = provider or ResendMailboxProvider()
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
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"mailbox_provider_unavailable:{type(exc).__name__}",
            ) from exc
        mailbox = build_mailbox(sent, received)
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
