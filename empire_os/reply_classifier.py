"""Deterministic classification for untrusted inbound buyer replies.

This module never executes instructions from email content. It maps text to a
small governed label set used by the reply-ingest database role.
"""
from __future__ import annotations

import re
from typing import Any

UNSUBSCRIBE_PATTERNS = (
    r"\bunsubscribe\b",
    r"\bopt[ -]?out\b",
    r"\bremove me\b",
    r"\bstop emailing\b",
    r"\bdo not (?:email|contact) me\b",
)
NEGATIVE_PATTERNS = (
    r"\bnot interested\b",
    r"\bno thanks\b",
    r"\bno thank you\b",
    r"\bnot for us\b",
)
LATER_PATTERNS = (
    r"\bnot right now\b",
    r"\btry again later\b",
    r"\bcheck back\b",
    r"\bnext (?:month|quarter|year)\b",
)
OBJECTION_PATTERNS = (
    r"\btoo expensive\b",
    r"\bcost(?:s|ing)? too much\b",
    r"\balready use\b",
    r"\balready have\b",
)
POSITIVE_PATTERNS = (
    r"\binterested\b",
    r"\bsend (?:it|that|the outline|more)\b",
    r"\btell me more\b",
    r"\blet'?s talk\b",
    r"\bbook (?:a )?(?:call|meeting)\b",
)


def _match_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_reply_text(body_text: Any, subject: Any = "") -> dict[str, Any]:
    """Classify inert plain text without granting it execution authority."""
    body = str(body_text or "").strip()
    subj = str(subject or "").strip()
    text = f"{subj}\n{body}".strip()

    if not body:
        return {"classification": "other", "confidence": 0.50, "auto_apply": False}
    if _match_any(UNSUBSCRIBE_PATTERNS, text):
        return {"classification": "unsubscribe", "confidence": 0.99, "auto_apply": True}
    if _match_any(NEGATIVE_PATTERNS, text):
        return {"classification": "negative", "confidence": 0.95, "auto_apply": True}
    if _match_any(LATER_PATTERNS, text):
        return {"classification": "later", "confidence": 0.92, "auto_apply": True}
    if _match_any(OBJECTION_PATTERNS, text):
        return {"classification": "objection", "confidence": 0.90, "auto_apply": True}
    if _match_any(POSITIVE_PATTERNS, text):
        return {"classification": "positive", "confidence": 0.90, "auto_apply": True}
    if "?" in body:
        return {"classification": "question", "confidence": 0.80, "auto_apply": True}
    return {"classification": "other", "confidence": 0.55, "auto_apply": False}
