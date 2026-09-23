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
    extract_resend_provider_event,
    extract_resend_reply,
    verify_resend_inbound,
)
from empire_os.outbound_role_transport import (
    PostgresOutboundRpc,
    SupabaseOutboundRpc,
)
from empire_os.reply_classifier import classify_reply_text

MAX_WEBHOOK_BYTES = 1_000_000


def _receiving_api_key() -> str:
    return (
        os.getenv("RESEND_RECEIVING_API_KEY", "").strip()
        or os.getenv("RESEND_API_KEY", "").strip()
    )


def _defaults():
    import resend

    def fetch_received_email(email_id: str):
        resend.api_key = _receiving_api_key()
        return resend.Emails.Receiving.get(email_id)

    return resend.Webhooks.verify, fetch_received_email


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

    def inbound_rpc():
        if reply_rpc is not None:
            return reply_rpc
        dsn = os.getenv("EMPIRE_REPLY_INGEST_DSN", "").strip()
        if dsn:
            return PostgresOutboundRpc(dsn, "empire_reply_ingest")
        return SupabaseOutboundRpc("empire_reply_ingest")

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
            provider_event = extract_resend_provider_event(event)
        except OutboundProviderError:
            return JSONResponse({"ok": False}, status_code=400)

        if provider_event is not None:
            try:
                result = inbound_rpc()("record_outbound_provider_event", {
                    "p_intent_id": provider_event["intent_id"],
                    "p_event_type": provider_event["event_type"],
                    "p_provider_message_id": provider_event["provider_message_id"],
                    "p_recipient": provider_event["recipient"],
                    "p_suppress": provider_event["suppress"],
                    "p_payload": provider_event["payload"],
                })
            except Exception:
                return JSONResponse({"ok": False}, status_code=503)
            return {
                "ok": True,
                "decision": result.get("decision", "recorded_provider_event"),
                "event_type": provider_event["event_type"],
                "suppressed": bool(result.get("suppressed", False)),
            }

        try:
            reply = extract_resend_reply(
                event, fetch_email=fetch_email, reply_to=reply_base,
            )
        except OutboundProviderError:
            return {"ok": True, "ignored": True}
        if reply is None:
            return {"ok": True, "ignored": True}

        try:
            rpc = inbound_rpc()
            result = rpc("ingest_outbound_reply", {
                "p_intent_id": reply["intent_id"],
                "p_provider_message_id": reply["provider_message_id"],
                "p_from_contact": reply["from_contact"],
                "p_subject": reply["subject"],
                "p_body_text": reply["body_text"],
                "p_received_at": reply["received_at"],
                "p_metadata": {
                    "provider": "resend", "untrusted_content": True,
                    "body_unavailable": bool(reply.get("body_unavailable")),
                    "in_reply_to": reply["in_reply_to"],
                    "references": reply["references"],
                },
            })
        except Exception:
            return JSONResponse({"ok": False}, status_code=503)

        classification = classify_reply_text(reply["body_text"], reply["subject"])
        classified = None
        if classification["auto_apply"]:
            try:
                classified = rpc("classify_outbound_reply", {
                    "p_reply_id": result["reply_id"],
                    "p_classification": classification["classification"],
                    "p_confidence": classification["confidence"],
                    "p_actor": "reply_classifier_v1",
                })
            except Exception:
                return JSONResponse({"ok": False}, status_code=503)

        return {
            "ok": True,
            "decision": result.get("decision", "recorded"),
            "classification": (
                classified.get("classification")
                if isinstance(classified, dict)
                else classification["classification"]
            ),
            "classification_auto_applied": bool(classified),
        }

    return app


app = create_app()
