"""Read-only Empire Mail normalisation for the Founder Console.

Provider email is untrusted data. This module only builds a deterministic read
model; it never sends mail, executes message content, or invents conversation
identity when a canonical Empire intent alias is unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parseaddr
import re
from typing import Any, Iterable, Mapping

from empire_os.reply_classifier import classify_reply_text

_REPLY_ALIAS_RE = re.compile(
    r"\breply\+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})@",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _addresses(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for item in values:
        address = parseaddr(_text(item))[1].strip().lower()
        if address:
            result.append(address)
    return result


def _intent_from_values(*values: Any) -> str | None:
    for value in values:
        items = value if isinstance(value, (list, tuple)) else [value]
        for item in items:
            match = _REPLY_ALIAS_RE.search(_text(item))
            if match:
                return match.group(1).lower()
    return None


def _occurred_at(row: Mapping[str, Any]) -> str | None:
    value = _text(
        row.get("received_at")
        or row.get("created_at")
        or row.get("sent_at")
        or row.get("updated_at")
    )
    return value or None


def _delivery_state(row: Mapping[str, Any], *, direction: str) -> str:
    if direction == "inbound":
        return "received"
    return (
        _text(row.get("last_event") or row.get("status") or "sent").lower()
        or "sent"
    )


def normalise_sent_email(row: Mapping[str, Any]) -> dict[str, Any]:
    provider_id = _text(row.get("id"))
    intent_id = _intent_from_values(
        row.get("reply_to"),
        row.get("replyTo"),
        row.get("to"),
    )
    thread_id = intent_id or (f"email:{provider_id}" if provider_id else None)
    return {
        "provider": "resend",
        "provider_id": provider_id or None,
        "message_id": _text(row.get("message_id")) or None,
        "thread_id": thread_id,
        "intent_id": intent_id,
        "direction": "outbound",
        "from": _text(row.get("from")) or None,
        "to": _addresses(row.get("to")),
        "reply_to": _addresses(row.get("reply_to") or row.get("replyTo")),
        "subject": _text(row.get("subject")) or "(no subject)",
        "occurred_at": _occurred_at(row),
        "delivery_state": _delivery_state(row, direction="outbound"),
        "body_text": _text(row.get("text")) or None,
        "classification": None,
        "suppressed": _delivery_state(row, direction="outbound") == "suppressed",
        "untrusted_content": False,
    }


def normalise_received_email(row: Mapping[str, Any]) -> dict[str, Any]:
    provider_id = _text(row.get("id") or row.get("email_id"))
    recipients = row.get("to")
    intent_id = _intent_from_values(recipients)
    thread_id = intent_id or (f"received:{provider_id}" if provider_id else None)
    body = _text(row.get("text") or row.get("body_text"))
    subject = _text(row.get("subject"))
    classification = classify_reply_text(body, subject) if body else {
        "classification": "unknown",
        "confidence": None,
        "auto_apply": False,
    }
    label = classification.get("classification")
    return {
        "provider": "resend",
        "provider_id": provider_id or None,
        "message_id": _text(row.get("message_id")) or None,
        "thread_id": thread_id,
        "intent_id": intent_id,
        "direction": "inbound",
        "from": _text(row.get("from")) or None,
        "to": _addresses(recipients),
        "reply_to": [],
        "subject": subject or "(no subject)",
        "occurred_at": _occurred_at(row),
        "delivery_state": "received",
        "body_text": body or None,
        "classification": label,
        "classification_confidence": classification.get("confidence"),
        "suppressed": label == "unsubscribe",
        "untrusted_content": True,
    }


def _ts(value: Any) -> float:
    text = _text(value)
    if not text:
        return 0.0
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def _next_action(events: list[dict[str, Any]]) -> str:
    inbound = next((row for row in events if row["direction"] == "inbound"), None)
    if inbound:
        label = inbound.get("classification")
        return {
            "unsubscribe": "suppress_and_close",
            "negative": "close",
            "later": "schedule_followup_review",
            "objection": "reason_over_objection_then_prepare_reply",
            "positive": "prepare_reply",
            "question": "answer_from_evidence_then_prepare_reply",
        }.get(label, "review_reply")
    outbound = next((row for row in events if row["direction"] == "outbound"), None)
    if outbound and outbound.get("delivery_state") in {"bounced", "failed"}:
        return "resolve_delivery"
    if outbound and outbound.get("delivery_state") == "suppressed":
        return "suppressed_no_send"
    return "await_reply_or_followup"


def _commercial_status(events: list[dict[str, Any]]) -> str:
    if any(row.get("suppressed") for row in events):
        return "suppressed"
    if any(row["direction"] == "inbound" for row in events):
        return "replied"
    if any(
        row["direction"] == "outbound"
        and row.get("delivery_state") in {"bounced", "failed"}
        for row in events
    ):
        return "delivery_failed"
    return "no_reply"


def build_mailbox(
    sent_rows: Iterable[Mapping[str, Any]],
    received_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    events = [normalise_sent_email(row) for row in sent_rows]
    events.extend(normalise_received_email(row) for row in received_rows)
    events = [row for row in events if row.get("thread_id")]
    events.sort(key=lambda row: _ts(row.get("occurred_at")), reverse=True)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in events:
        grouped.setdefault(str(row["thread_id"]), []).append(row)

    threads: list[dict[str, Any]] = []
    for thread_id, rows in grouped.items():
        rows.sort(key=lambda row: _ts(row.get("occurred_at")), reverse=True)
        latest = rows[0]
        inbound = next((row for row in rows if row["direction"] == "inbound"), None)
        outbound = next((row for row in rows if row["direction"] == "outbound"), None)
        threads.append({
            "thread_id": thread_id,
            "intent_id": latest.get("intent_id"),
            "subject": latest.get("subject"),
            "contact": (
                inbound.get("from") if inbound
                else ((outbound.get("to") or [None])[0] if outbound else None)
            ),
            "latest_at": latest.get("occurred_at"),
            "latest_direction": latest.get("direction"),
            "delivery_state": (
                outbound.get("delivery_state") if outbound else "received"
            ),
            "classification": inbound.get("classification") if inbound else None,
            "commercial_status": _commercial_status(rows),
            "suppressed": any(row.get("suppressed") for row in rows),
            "next_action": _next_action(rows),
            "event_count": len(rows),
            "events": rows,
        })

    threads.sort(key=lambda row: _ts(row.get("latest_at")), reverse=True)
    return {
        "schema_version": "empire.mailbox.v1",
        "mode": "OBSERVE",
        "read_only": True,
        "execution_authority": "none",
        "provider": "resend",
        "thread_count": len(threads),
        "summary": {
            "all": len(threads),
            "replies": sum(
                1 for row in threads if row["commercial_status"] == "replied"
            ),
            "positive": sum(1 for row in threads if row["classification"] == "positive"),
            "questions": sum(1 for row in threads if row["classification"] == "question"),
            "objections": sum(1 for row in threads if row["classification"] == "objection"),
            "bounced_failed": sum(
                1 for row in threads if row["commercial_status"] == "delivery_failed"
            ),
            "suppressed": sum(1 for row in threads if row["suppressed"]),
        },
        "threads": threads,
    }


def mailbox_thread(mailbox: Mapping[str, Any], thread_id: str) -> dict[str, Any] | None:
    for row in mailbox.get("threads") or []:
        if str(row.get("thread_id")) == str(thread_id):
            return dict(row)
    return None
