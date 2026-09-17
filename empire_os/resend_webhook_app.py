"""Isolated signed Resend webhook receiver for governed Phase 3E replies.

Inbound email is untrusted data. This service verifies the provider signature,
correlates only to an Empire intent-specific reply alias, and writes an inert
reply record through the dedicated reply-ingest role. It never calls an agent.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from empire_os.outbound_provider import (
    OutboundProviderError,
    extract_resend_reply,
    verify_resend_inbound,
)
from empire_os.outbound_role_transport import PostgresOutboundRpc

MAX_WEBHOOK_BYTES = 1_000_000


def _defaults():
    import resend
    resend.api_key = os.getenv("RESEND_API_KEY", "").strip()
    return resend.Webhooks.verify, resend.Emails.Receiving.get


def create_app(*, verify_webhook: Callable[..., Any] | None = None,
               fetch_email: Callable[[str], Any] | None = None,
               reply_rpc: Callable[[str, dict[str, Any]], Any] | None = None,
               webhook_secret: str | None = None,
               reply_to: str | None = None) -> FastAPI:
    app = FastAPI(title="Empire Resend Inbound", docs_url=None, redoc_url=None)
    if verify_webhook is None or fetch_email is None:
        default_verify, default_fetch = _defaults()
        verify_webhook = verify_webhook or default_verify
        fetch_email = fetch_email or default_fetch
    secret = (webhook_secret if webhook_secret is not None
              else os.getenv("RESEND_WEBHOOK_SECRET", "")).strip()
    reply_base = (reply_to if reply_to is not None
                  else os.getenv("EMPIRE_REPLY_TO", "")).strip()

    @app.get("/health")
    async def health():
        return {"ok": True, "mode": "OBSERVE", "provider": "resend"}

    @app.post("/webhooks/resend-inbound")
    async def inbound(request: Request):
        raw_bytes = await request.body()
        if len(raw_bytes) > MAX_WEBHOOK_BYTES:
            return JSONResponse({"ok": False}, status_code=413)
        try:
            raw = raw_bytes.decode("utf-8", errors="strict")
            event = verify_resend_inbound(
                raw, dict(request.headers), secret=secret,
                verify_webhook=verify_webhook,
            )
        except (UnicodeDecodeError, OutboundProviderError):
            return JSONResponse({"ok": False}, status_code=400)

        try:
            reply = extract_resend_reply(
                event, fetch_email=fetch_email, reply_to=reply_base,
            )
        except OutboundProviderError:
            return {"ok": True, "ignored": True}
        if reply is None:
            return {"ok": True, "ignored": True}

        rpc = reply_rpc
        if rpc is None:
            dsn = os.getenv("EMPIRE_REPLY_INGEST_DSN", "").strip()
            if not dsn:
                return JSONResponse({"ok": False}, status_code=503)
            try:
                rpc = PostgresOutboundRpc(dsn, "empire_reply_ingest")
            except OutboundProviderError:
                return JSONResponse({"ok": False}, status_code=503)
        try:
            result = rpc("ingest_outbound_reply", {
                "p_intent_id": reply["intent_id"],
                "p_provider_message_id": reply["provider_message_id"],
                "p_from_contact": reply["from_contact"],
                "p_subject": reply["subject"],
                "p_body_text": reply["body_text"],
                "p_received_at": reply["received_at"],
                "p_metadata": {
                    "provider": "resend", "untrusted_content": True,
                    "in_reply_to": reply["in_reply_to"],
                    "references": reply["references"],
                },
            })
        except Exception:
            return JSONResponse({"ok": False}, status_code=503)
        return {"ok": True, "decision": result.get("decision", "recorded")}

    return app


app = create_app()
