"""Fail-closed outbound provider boundary for Phase 3E.

This module has no autonomous loop. It only translates a database-authorized send
claim into provider parameters and turns a cryptographically verified inbound event
into inert reply data for the governed reply-ingest RPC.
"""
from __future__ import annotations

import json
import re
from email.utils import parseaddr
from uuid import UUID
from typing import Any, Callable


class OutboundProviderError(RuntimeError):
    pass


def _email(value: Any) -> str:
    text = parseaddr(str(value or ""))[1].strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
        raise OutboundProviderError("valid email address required")
    return text


def _intent_uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise OutboundProviderError("valid intent id required") from exc


def threaded_reply_address(reply_to: str, intent_id: Any) -> str:
    base = _email(reply_to)
    local, domain = base.split("@", 1)
    return f"{local}+{_intent_uuid(intent_id)}@{domain}"


def build_resend_send(claim: dict[str, Any], *, sender: str, reply_to: str,
                      required_sender_domain: str = "mail.empire-ai.co.uk",
                      required_postal_footer: str = "31 St Thomas St, Bolton, BL1 2QR, UK") -> dict[str, Any]:
    if not isinstance(claim, dict) or claim.get("decision") != "authorized_send":
        raise OutboundProviderError("database-authorized send claim required")
    if claim.get("actual_revenue") is not False or claim.get("channel") != "email":
        raise OutboundProviderError("safe email send claim required")
    recipient = _email(claim.get("recipient"))
    sender_address = _email(sender)
    required_domain = str(required_sender_domain or "").strip().lower()
    if not required_domain or sender_address.rsplit("@", 1)[-1] != required_domain:
        raise OutboundProviderError("approved outbound sender domain required")
    reply_address = threaded_reply_address(reply_to, claim.get("intent_id"))
    if reply_address.rsplit("@", 1)[-1] != required_domain:
        raise OutboundProviderError("approved outbound reply domain required")
    body_text = str(claim.get("body_text") or "")
    if not body_text.strip():
        raise OutboundProviderError("non-empty outbound body required")
    lower_body = body_text.lower()
    if not any(token in lower_body for token in ("unsubscribe", "opt out", "opt-out")):
        raise OutboundProviderError("visible outbound opt-out required")
    footer = str(required_postal_footer or "").strip()
    normalized_body = re.sub(r"[^a-z0-9]+", " ", lower_body).strip()
    normalized_footer = re.sub(r"[^a-z0-9]+", " ", footer.lower()).strip()
    if not normalized_footer or normalized_footer not in normalized_body:
        raise OutboundProviderError("approved postal footer required")
    return {
        "from": sender,
        "to": [recipient],
        "reply_to": [reply_address],
        "subject": str(claim.get("subject") or ""),
        "text": body_text,
        "html": claim.get("body_html") or None,
        "tags": [{"name": "intent_id", "value": str(claim.get("intent_id") or "")}],
        "headers": {"List-Unsubscribe": f"<mailto:{reply_address}?subject=opt%20out>"},
        "_sender_address": sender_address,
        "_idempotency_key": f"outbound/{_intent_uuid(claim.get("intent_id"))}",
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
        event = verify_webhook({
            "payload": raw_body,
            "headers": {
                "id": safe_headers["svix-id"],
                "timestamp": safe_headers["svix-timestamp"],
                "signature": safe_headers["svix-signature"],
            },
            "webhook_secret": secret,
        })
    except Exception as exc:
        raise OutboundProviderError("webhook signature verification failed") from exc
    if not isinstance(event, dict):
        raise OutboundProviderError("verified webhook event must be an object")
    return event


def _resend_tag(tags: Any, name: str) -> str:
    if isinstance(tags, dict):
        return str(tags.get(name) or "").strip()
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, dict) and str(item.get("name") or "") == name:
                return str(item.get("value") or "").strip()
    return ""


def extract_resend_provider_event(event: dict[str, Any]) -> dict[str, Any] | None:
    event_map = {
        "email.delivered": "delivered",
        "email.delivery_delayed": "delivery_delayed",
        "email.bounced": "bounced",
        "email.complained": "complained",
        "email.opened": "opened",
        "email.clicked": "clicked",
        "email.failed": "failed",
        "email.suppressed": "suppressed",
    }
    event_type = event_map.get(str(event.get("type") or ""))
    if not event_type:
        return None
    data = event.get("data")
    if not isinstance(data, dict):
        raise OutboundProviderError("verified provider event missing data")
    message_id = str(data.get("email_id") or "").strip()
    if not message_id:
        raise OutboundProviderError("verified provider event missing email_id")
    recipients = data.get("to")
    if isinstance(recipients, str):
        recipients = [recipients]
    if not isinstance(recipients, list) or len(recipients) != 1:
        raise OutboundProviderError("provider event requires one recipient")
    recipient = _email(recipients[0])
    intent_id = _intent_uuid(_resend_tag(data.get("tags"), "intent_id"))
    suppress = event_type in {"complained", "suppressed"}
    if event_type == "bounced":
        bounce = data.get("bounce") if isinstance(data.get("bounce"), dict) else {}
        bounce_type = str(bounce.get("type") or "").strip().lower()
        bounce_subtype = str(bounce.get("subType") or "").strip().lower()
        suppress = bounce_type in {"permanent", "hard"} or bounce_subtype == "suppressed"
    return {
        "intent_id": intent_id,
        "event_type": event_type,
        "provider_message_id": message_id,
        "recipient": recipient,
        "suppress": suppress,
        "payload": data,
    }


def extract_resend_reply(event: dict[str, Any], *, fetch_email: Callable[[str], Any],
                         reply_to: str | None = None) -> dict[str, Any] | None:
    if event.get("type") != "email.received":
        return None
    data = event.get("data") or {}
    if not isinstance(data, dict):
        raise OutboundProviderError("verified inbound event missing data")
    email_id = str(data.get("email_id") or "").strip()
    if not email_id:
        raise OutboundProviderError("verified inbound event missing email_id")

    event_recipients = (
        data.get("received_for")
        or data.get("to")
        or []
    )
    intent_id = (
        resolve_intent_from_recipients(
            event_recipients,
            reply_to=reply_to,
        )
        if reply_to
        else ""
    )
    event_sender = _email(data.get("from"))
    event_subject = str(data.get("subject") or "")

    try:
        fetched = fetch_email(email_id)
    except Exception:
        # A send-only Resend key cannot fetch received-email bodies. The
        # signed webhook still proves that a reply arrived and provides the
        # governed reply alias, sender, subject and provider email id. Record
        # that event instead of silently losing it; downstream automation can
        # only auto-classify explicit deterministic patterns such as opt-out.
        return {
            "provider": "resend",
            "provider_message_id": email_id,
            "intent_id": intent_id,
            "from_contact": event_sender,
            "subject": event_subject,
            "body_text": "[provider body unavailable]",
            "received_at": str(data.get("created_at") or ""),
            "in_reply_to": "",
            "references": "",
            "body_unavailable": True,
            "untrusted_content": True,
            "executable": False,
        }

    if isinstance(fetched, dict) and isinstance(fetched.get("data"), dict):
        fetched = fetched["data"]
    if not isinstance(fetched, dict):
        raise OutboundProviderError("inbound email response must be an object")
    sender = _email(fetched.get("from") or event_sender)
    text = str(fetched.get("text") or "").strip()
    if not text:
        raise OutboundProviderError("plain-text inbound body required")
    headers = fetched.get("headers") if isinstance(fetched.get("headers"), dict) else {}
    recipients = (
        fetched.get("received_for")
        or fetched.get("to")
        or event_recipients
    )
    if reply_to:
        intent_id = resolve_intent_from_recipients(
            recipients,
            reply_to=reply_to,
        )
    return {
        "provider": "resend",
        "provider_message_id": email_id,
        "intent_id": intent_id,
        "from_contact": sender,
        "subject": str(fetched.get("subject") or event_subject),
        "body_text": text,
        "received_at": str(data.get("created_at") or fetched.get("created_at") or ""),
        "in_reply_to": str(headers.get("in-reply-to") or headers.get("In-Reply-To") or ""),
        "references": str(headers.get("references") or headers.get("References") or ""),
        "body_unavailable": False,
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
    idempotency_key = str(payload.get("_idempotency_key") or "").strip()
    if not idempotency_key:
        raise OutboundProviderError("outbound idempotency key required")
    try:
        if resend_module is None:
            import resend as resend_module
        resend_module.api_key = api_key
        result = resend_module.Emails.send(outbound, {"idempotency_key": idempotency_key})
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


def resolve_intent_from_recipients(recipients: Any, *, reply_to: str) -> str:
    base = _email(reply_to)
    local, domain = base.split("@", 1)
    if isinstance(recipients, str):
        recipients = [recipients]
    if not isinstance(recipients, (list, tuple)):
        raise OutboundProviderError("inbound recipients required")
    prefix = local + "+"
    for value in recipients:
        address = _email(value)
        rlocal, rdomain = address.split("@", 1)
        if rdomain != domain or not rlocal.startswith(prefix):
            continue
        token = rlocal[len(prefix):]
        try:
            return _intent_uuid(token)
        except OutboundProviderError:
            continue
    raise OutboundProviderError("inbound email is not addressed to a governed reply alias")
