"""Governed Gmail reply adapter for canonical outbound conversations.

Gmail content is untrusted input. This module does not send email and does not
grant inbound content execution authority. It correlates a Gmail message only
when the canonical sent outbound intent already carries the same Gmail thread
id and the inbound sender matches the original normalized recipient.
"""
from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Any, Callable, Iterable, Mapping

from empire_os.reply_classifier import classify_reply_text

Rpc = Callable[[str, dict[str, Any]], Any]

_DSN_LOCAL_PARTS = {"mailer-daemon", "postmaster"}
_QUOTED_REPLY_BOUNDARIES = (
    re.compile(r"^On .+wrote:\s*$", re.IGNORECASE),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}$", re.IGNORECASE),
)


def normalize_email(value: Any) -> str:
    """Return a conservative normalized mailbox or an empty string."""
    email = parseaddr(str(value or ""))[1].strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return ""
    return email


def visible_reply_text(value: Any) -> str:
    """Remove obvious quoted history before deterministic classification."""
    lines: list[str] = []
    for raw_line in str(value or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.rstrip()
        if any(pattern.match(line.strip()) for pattern in _QUOTED_REPLY_BOUNDARIES):
            break
        if line.lstrip().startswith(">"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _is_delivery_status_sender(email: str) -> bool:
    if not email or "@" not in email:
        return False
    local = email.split("@", 1)[0].lower()
    return local in _DSN_LOCAL_PARTS or local.startswith("mailer-daemon+")


def _metadata(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, Mapping) else {}


def correlate_gmail_reply(
    message: Mapping[str, Any],
    outbound_intents: Iterable[Mapping[str, Any]],
    *,
    self_addresses: Iterable[str] = (),
) -> dict[str, Any]:
    """Correlate one Gmail message to exactly one canonical sent intent."""
    message_id = str(message.get("id") or "").strip()
    thread_id = str(message.get("thread_id") or "").strip()
    sender = normalize_email(message.get("from"))
    received_at = str(message.get("email_ts") or "").strip()
    labels = {
        str(label or "").strip().upper()
        for label in (message.get("labels") or [])
        if str(label or "").strip()
    }
    own = {normalize_email(value) for value in self_addresses}
    own.discard("")

    if not message_id:
        return {"matched": False, "reason": "missing_message_id"}
    if not thread_id:
        return {"matched": False, "reason": "missing_thread_id"}
    if not received_at:
        return {"matched": False, "reason": "missing_received_at"}
    if not sender:
        return {"matched": False, "reason": "invalid_sender"}
    if sender in own:
        return {"matched": False, "reason": "self_message"}
    if "SENT" in labels or "DRAFT" in labels:
        return {"matched": False, "reason": "outbound_or_draft_message"}
    if _is_delivery_status_sender(sender):
        return {"matched": False, "reason": "delivery_status_message"}

    matches: list[Mapping[str, Any]] = []
    for row in outbound_intents:
        if str(row.get("status") or "").strip().lower() != "sent":
            continue
        if str(row.get("channel") or "").strip().lower() != "email":
            continue
        metadata = _metadata(row)
        if str(metadata.get("provider") or "").strip().lower() != "gmail":
            continue
        if str(metadata.get("gmail_thread_id") or "").strip() != thread_id:
            continue
        recipient = normalize_email(
            row.get("normalized_recipient") or row.get("recipient")
        )
        if recipient != sender:
            continue
        intent_id = str(row.get("id") or "").strip()
        if not intent_id:
            continue
        matches.append(row)

    if not matches:
        return {"matched": False, "reason": "no_canonical_thread_match"}
    if len(matches) != 1:
        return {"matched": False, "reason": "ambiguous_canonical_thread_match"}

    row = matches[0]
    return {
        "matched": True,
        "intent_id": str(row["id"]),
        "provider_message_id": message_id,
        "gmail_thread_id": thread_id,
        "from_contact": sender,
        "subject": str(message.get("subject") or "").strip(),
        "body_text": str(message.get("body") or "").strip(),
        "received_at": received_at,
        "labels": sorted(labels),
    }


def ingest_gmail_reply(
    message: Mapping[str, Any],
    outbound_intents: Iterable[Mapping[str, Any]],
    rpc: Rpc,
    *,
    self_addresses: Iterable[str] = (),
) -> dict[str, Any]:
    """Ingest and deterministically classify one correlated Gmail reply."""
    correlated = correlate_gmail_reply(
        message,
        outbound_intents,
        self_addresses=self_addresses,
    )
    if not correlated.get("matched"):
        return {
            "ok": True,
            "ignored": True,
            "reason": correlated.get("reason"),
            "outbound_sent": False,
            "actual_revenue": False,
        }

    result = rpc(
        "ingest_outbound_reply",
        {
            "p_intent_id": correlated["intent_id"],
            "p_provider_message_id": correlated["provider_message_id"],
            "p_from_contact": correlated["from_contact"],
            "p_subject": correlated["subject"],
            "p_body_text": correlated["body_text"],
            "p_received_at": correlated["received_at"],
            "p_metadata": {
                "provider": "gmail",
                "untrusted_content": True,
                "gmail_thread_id": correlated["gmail_thread_id"],
                "gmail_labels": correlated["labels"],
                "correlation_version": "gmail_thread_sender_v1",
                "classifier_body_mode": "visible_reply_only_v1",
            },
        },
    )

    classifier_body = visible_reply_text(correlated["body_text"])
    classification = classify_reply_text(
        classifier_body,
        correlated["subject"],
    )
    classified = None
    if classification["auto_apply"]:
        classified = rpc(
            "classify_outbound_reply",
            {
                "p_reply_id": result["reply_id"],
                "p_classification": classification["classification"],
                "p_confidence": classification["confidence"],
                "p_actor": "gmail_reply_classifier_v1",
            },
        )

    return {
        "ok": True,
        "ignored": False,
        "decision": result.get("decision", "recorded"),
        "intent_id": correlated["intent_id"],
        "reply_id": result.get("reply_id"),
        "classification": (
            classified.get("classification")
            if isinstance(classified, Mapping)
            else classification["classification"]
        ),
        "classification_auto_applied": bool(classified),
        "outbound_sent": False,
        "actual_revenue": False,
    }
