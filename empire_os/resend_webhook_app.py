"""Isolated signed Resend webhook receiver for governed Phase 3E replies.

Inbound email is untrusted data. This service verifies the provider signature,
correlates only to an Empire intent-specific reply alias, and writes an inert
reply record through the dedicated reply-ingest role. It never calls an agent.
"""
from __future__ import annotations

import os
import re
from email.utils import parseaddr
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


def _valid_email(value: Any) -> str:
    email = parseaddr(str(value or ""))[1].strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return ""
    return email


def _forward_reply_notification(
    reply: dict[str, Any],
    *,
    target: str,
    sender: str,
    resend_module: Any | None = None,
) -> dict[str, Any]:
    target_email = _valid_email(target)
    sender_email = _valid_email(sender)
    if not target_email or not sender_email:
        return {
            "forwarded": False,
            "reason": "forwarding_configuration_invalid",
        }

    if resend_module is None:
        import resend as resend_module

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return {
            "forwarded": False,
            "reason": "resend_api_key_missing",
        }

    resend_module.api_key = api_key
    provider_message_id = str(
        reply.get("provider_message_id") or ""
    ).strip()
    intent_id = str(reply.get("intent_id") or "").strip()
    original_subject = str(reply.get("subject") or "").strip()
    original_from = str(reply.get("from_contact") or "").strip()
    body = str(reply.get("body_text") or "").strip()

    subject = (
        "[Empire buyer reply] "
        + (original_subject or "(no subject)")
    )
    text = (
        "EmpireOS buyer reply notification\n\n"
        f"From: {original_from or 'unknown'}\n"
        f"Intent: {intent_id or 'unknown'}\n"
        f"Provider message: {provider_message_id or 'unknown'}\n"
        f"Received: {str(reply.get('received_at') or '').strip()}\n"
        f"Subject: {original_subject or '(no subject)'}\n\n"
        "--- Untrusted inbound reply content ---\n"
        + (body or "[body unavailable]")
        + "\n--- End inbound reply ---\n\n"
        "This is a visibility copy only. EmpireOS retains the canonical "
        "reply record and conversation state."
    )
    options = {
        "idempotency_key": (
            "reply-forward/"
            + (provider_message_id or intent_id or "unknown")
        )
    }
    result = resend_module.Emails.send(
        {
            "from": sender,
            "to": [target_email],
            "subject": subject,
            "text": text,
            "tags": [
                {"name": "intent_id", "value": intent_id}
            ] if intent_id else [],
        },
        options,
    )
    if isinstance(result, dict):
        email_id = result.get("id") or (result.get("data") or {}).get("id")
    else:
        email_id = getattr(result, "id", None)
    return {
        "forwarded": bool(email_id),
        "email_id": str(email_id or "").strip() or None,
        "target": target_email,
    }


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
               reply_to: str | None = None,
               reply_forward_to: str | None = None,
               reply_forward_sender: str | None = None,
               resend_module: Any | None = None) -> FastAPI:
    app = FastAPI(title="Empire Resend Inbound", docs_url=None, redoc_url=None)
    if verify_webhook is None or fetch_email is None:
        default_verify, default_fetch = _defaults()
        verify_webhook = verify_webhook or default_verify
        fetch_email = fetch_email or default_fetch
    secret = (webhook_secret if webhook_secret is not None
              else os.getenv("RESEND_WEBHOOK_SECRET", "")).strip()
    reply_base = (reply_to if reply_to is not None
                  else os.getenv("EMPIRE_REPLY_TO", "")).strip()
    forward_target = (
        reply_forward_to
        if reply_forward_to is not None
        else os.getenv("EMPIRE_REPLY_FORWARD_TO", "")
    ).strip()
    forward_sender = (
        reply_forward_sender
        if reply_forward_sender is not None
        else os.getenv("EMPIRE_OUTBOUND_FROM", "")
    ).strip()

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

        forward_result = {
            "forwarded": False,
            "reason": "reply_forwarding_disabled",
        }
        if forward_target:
            try:
                forward_result = _forward_reply_notification(
                    reply,
                    target=forward_target,
                    sender=forward_sender,
                    resend_module=resend_module,
                )
            except Exception:
                forward_result = {
                    "forwarded": False,
                    "reason": "reply_forward_failed",
                }

        return {
            "ok": True,
            "decision": result.get("decision", "recorded"),
            "classification": (
                classified.get("classification")
                if isinstance(classified, dict)
                else classification["classification"]
            ),
            "classification_auto_applied": bool(classified),
            "reply_forwarded": bool(
                forward_result.get("forwarded")
            ),
            "reply_forward_target": (
                forward_result.get("target")
                if forward_result.get("forwarded")
                else None
            ),
            "reply_forward_reason": (
                forward_result.get("reason")
                if not forward_result.get("forwarded")
                else None
            ),
        }

    return app


app = create_app()
