"""Recognise explicit buyer email statements without treating them as verification.

Raw Gmail body exists only in memory during a read-only observation. Persist
only bounded event codes and provider message IDs; do not accept instructions,
grant provider authority, or save caller data.
"""
from __future__ import annotations

import base64
import re
from typing import Any, Mapping

from empire_os.gmail_reply_adapter import visible_reply_text

EVENT_CODES = frozenset({
    "LANDING_VISUAL_APPROVED_REPORTED",
    "RECORDING_ENABLED_REPORTED",
    "RECORDING_DISABLED_REPORTED",
    "TEST_ENDED_BEFORE_CONNECTION_REPORTED",
    "ROUTE_OR_NUMBER_LIVE_REPORTED",
    "CALLER_ID_PASSTHROUGH_REPORTED",
    "PILOT_TECHNICAL_REQUIREMENTS_SENT",
    "COMPLETE_BUYER_REQUIREMENTS_SENT",
})

def _decode(data: Any) -> str:
    if not isinstance(data, str) or len(data) > 35000:
        return ""
    try:
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        return raw[:16000].decode("utf-8", "replace")
    except (ValueError, UnicodeError):
        return ""


def _body_parts(part: Mapping[str, Any], depth: int = 0) -> list[str]:
    if depth > 4:
        return []
    if part.get("mimeType") == "text/plain":
        return [_decode((part.get("body") or {}).get("data"))]
    chunks = []
    for child in (part.get("parts") or [])[:15]:
        if isinstance(child, Mapping):
            chunks.extend(_body_parts(child, depth + 1))
    return chunks


def classify_visible_claims(visible: str, *, outbound: bool = False) -> list[str]:
    """High-precision rules, never a guessed contract or connected-leg proof."""
    if not isinstance(visible, str):
        return []
    # Ignore everything after quoted history / reply separators. Only direct
    # top-of-message statements count, never echoed claims in a quote.
    text = visible_reply_text(visible[:16000]).lower()[:8000]
    if not text:
        return []
    # Gmail plain-text MIME often hard-wraps a single sentence mid-phrase
    # ("hung up\nbefore connection"). Join soft wraps, preserve paragraphs.
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    segments = re.split(r"[\n.!?]+", text)
    events = set()
    for segment in segments:
        line = segment.strip()
        if not line:
            continue
        if not outbound:
            # An actual affirmative decision must be explicit. Phrases such
            # as "awaiting sign-off", "when you send screenshots" or
            # "will reply with approval" are NOT approval.
            approved = re.search(
                r"you(?:\s+are|'re) approved|you have (?:our |my )?sign[ -]?off"
                r"|we (?:hereby )?approve|approved (?:and |to )?(?:can )?go live",
                text,
            )
            page_context = re.search(
                r"\b(landing|page|screenshots?|creative|website|roofing)\b",
                text[:1300],
            )
            if (approved and page_context
                    and not re.search(r"\b(not approved|approval (?:still )?pending)\b",
                                      approved.group(0))):
                events.add("LANDING_VISUAL_APPROVED_REPORTED")
            if re.search(r"\b(recording|recordings)\b",line):
                if re.search(r"\b(are|is|remain|currently) (enabled|on)\b|\brecording(?:s)? enabled\b",line):
                    events.add("RECORDING_ENABLED_REPORTED")
                if re.search(r"\b(are|is|remain|currently) (disabled|off)\b|\brecording(?:s)? disabled\b",line):
                    events.add("RECORDING_DISABLED_REPORTED")
            if re.search(r"\b(hung up|hanged up|ended|disconnected|hang up)\b.*\bbefore (?:the )?(?:buyer )?connection\b|\bnever connected\b",line):
                events.add("TEST_ENDED_BEFORE_CONNECTION_REPORTED")
            if (re.search(r"\b(number|call route|routing|campaign)\b",line)
                    and re.search(r"\b(is live|are live|now live|live and|activated)\b",line)):
                events.add("ROUTE_OR_NUMBER_LIVE_REPORTED")
            if re.search(r"\b(caller.?id|ani)\b",line) and re.search(
                r"\b(came through|passed through|pass.through|preserved|unchanged|delivered)\b",line):
                events.add("CALLER_ID_PASSTHROUGH_REPORTED")
        elif ("caller id" in text or "caller-id" in text or "ani" in text):
            if ("recording" in text and
                    re.search(r"\b(confirm|verification|evidence|screenshot|could|please)\b",text)
                    and re.search(r"\b(target|route|destination|buyer leg)\b",text)):
                events.add("PILOT_TECHNICAL_REQUIREMENTS_SENT")
    if outbound and re.search(r"\b(could you|please (?:send|confirm|provide)|we need)\b",text):
        groups = [
            r"\b(campaign|buy.?box|accepted (?:jobs|services|zip|markets))\b",
            r"\b(payout|settlement|revenue.share|payable event)\b",
            r"\b(routing|tracking|caller.?id|ani|postback)\b",
            r"\b(recording|consent|compliance|disclosure|source acceptance)\b",
            r"\b(agreement|onboarding|contract|signing)\b",
        ]
        if sum(bool(re.search(pattern,text)) for pattern in groups)>=4:
            events.add("COMPLETE_BUYER_REQUIREMENTS_SENT")
    return sorted(events)


def recognize_message_payload(payload: Mapping[str, Any], *, outbound: bool = False) -> list[str]:
    # A metadata-only Gmail payload produces no invented recognition.
    if not isinstance(payload, Mapping):
        return []
    parts = _body_parts(payload)
    if not parts and payload.get("mimeType") == "text/plain":
        parts = [_decode((payload.get("body") or {}).get("data"))]
    if not parts:
        return []
    return classify_visible_claims("\n".join(parts), outbound=outbound)
