"""Fail-closed outbound provider boundary for Phase 3E.

This module has no autonomous loop. It only translates a database-authorized send
claim into provider parameters and turns a cryptographically verified inbound event
into inert reply data for the governed reply-ingest RPC.
"""
from __future__ import annotations

import json
import re
from email.utils import parseaddr
from typing import Any, Callable


class OutboundProviderError(RuntimeError):
    pass


def _email(value: Any) -> str:
    text = parseaddr(str(value or ""))[1].strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
        raise OutboundProviderError("valid email address required")
    return text


def build_resend_send(claim: dict[str, Any], *, sender: str, reply_to: str) -> dict[str, Any]:
    if not isinstance(claim, dict) or claim.get("decision") != "authorized_send":
        raise OutboundProviderError("database-authorized send claim required")
    if claim.get("actual_revenue") is not False or claim.get("channel") != "email":
        raise OutboundProviderError("safe email send claim required")
    recipient = _email(claim.get("recipient"))
    sender_address = _email(sender)
    reply_address = _email(reply_to)
    body_text = str(claim.get("body_text") or "")
    if not body_text.strip():
        raise OutboundProviderError("non-empty outbound body required")
    return {
        "from": sender,
        "to": [recipient],
        "reply_to": [reply_address],
        "subject": str(claim.get("subject") or ""),
        "text": body_text,
        "html": claim.get("body_html") or None,
        "tags": [{"name": "intent_id", "value": str(claim.get("intent_id") or "")}],
        "_sender_address": sender_address,
    }


def verify_resend_inbound(raw_body: str, headers: dict[str, Any], *, secret: str,
                          verify_webhook: Callable[..., Any]) -> dict[str, Any]:
    if not isinstance(raw_body, str) or not raw_body:
        raise OutboundProviderError("raw webhook body required")
    if not secret or not callable(verify_webhook):
        raise OutboundProviderError("webhook verification configuration required")
    safe_headers = {
        "svix-id": str(headers.get("svix-id") or headers.get("Svix-Id") or ""),
        "svix-timestamp": str(headers.get("svix-timestamp") or headers.get("Svix-Timestamp") or ""),
        "svix-signature": str(headers.get("svix-signature") or headers.get("Svix-Signature") or ""),
    }
    if not all(safe_headers.values()):
        raise OutboundProviderError("complete signed webhook headers required")
    try:
        event = verify_webhook(payload=raw_body, headers=safe_headers, secret=secret)
    except Exception as exc:
        raise OutboundProviderError("webhook signature verification failed") from exc
    if not isinstance(event, dict):
        raise OutboundProviderError("verified webhook event must be an object")
    return event


def extract_resend_reply(event: dict[str, Any], *, fetch_email: Callable[[str], Any]) -> dict[str, Any] | None:
    if event.get("type") != "email.received":
        return None
    data = event.get("data") or {}
    email_id = str(data.get("email_id") or "").strip()
    if not email_id:
        raise OutboundProviderError("verified inbound event missing email_id")
    try:
        fetched = fetch_email(email_id)
    except Exception as exc:
        raise OutboundProviderError("failed to fetch inbound email") from exc
    if isinstance(fetched, dict) and isinstance(fetched.get("data"), dict):
        fetched = fetched["data"]
    if not isinstance(fetched, dict):
        raise OutboundProviderError("inbound email response must be an object")
    sender = _email(fetched.get("from") or data.get("from"))
    text = str(fetched.get("text") or "").strip()
    if not text:
        raise OutboundProviderError("plain-text inbound body required")
    headers = fetched.get("headers") if isinstance(fetched.get("headers"), dict) else {}
    return {
        "provider": "resend",
        "provider_message_id": email_id,
        "from_contact": sender,
        "subject": str(fetched.get("subject") or data.get("subject") or ""),
        "body_text": text,
        "received_at": str(data.get("created_at") or fetched.get("created_at") or ""),
        "in_reply_to": str(headers.get("in-reply-to") or headers.get("In-Reply-To") or ""),
        "references": str(headers.get("references") or headers.get("References") or ""),
        "untrusted_content": True,
        "executable": False,
    }


def send_with_resend(payload: dict[str, Any], *, api_key: str,
                     resend_module: Any | None = None) -> str:
    if not api_key:
        raise OutboundProviderError("Resend API key required")
    if not isinstance(payload, dict) or not payload.get("_sender_address"):
        raise OutboundProviderError("validated Resend payload required")
    outbound = {k: v for k, v in payload.items() if not k.startswith("_") and v is not None}
    try:
        if resend_module is None:
            import resend as resend_module
        resend_module.api_key = api_key
        result = resend_module.Emails.send(outbound)
    except Exception as exc:
        raise OutboundProviderError("Resend send failed") from exc
    if isinstance(result, dict):
        message_id = result.get("id") or (result.get("data") or {}).get("id")
    else:
        message_id = getattr(result, "id", None)
    message_id = str(message_id or "").strip()
    if not message_id:
        raise OutboundProviderError("Resend returned no message id")
    return message_id
