"""Recognise only unmistakable stop-contact requests in partial reply evidence.

Unlike a commercial-interest classifier, this conservative detection only
adds a protective no-contact hold. Never infer positive intent, approval, or
confirmed suppression-table persistence from a provider preview.
"""
from __future__ import annotations

import re
from typing import Any


_DIRECT_SUBJECT = re.compile(
    r"^(?:(?:re|fw|fwd)\s*:\s*)*(?:opt[ -]?out|unsubscribe|stop(?: contact| emailing)?)(?:[\s!.]*)$",
    re.IGNORECASE,
)
_DIRECT_BODY_START = re.compile(
    r"^(?:hi[,!]?\s+|hello[,!]?\s+|thanks?\s+(?:for\s+(?:reaching out|the email|your message))\.?\s+|please\s+|kindly\s+)*"
    r"(?:opt[ -]?out\b|unsubscribe\b|remove\s+me\s+(?:from\s+(?:your|the|this)\s+(?:mailing\s+)?list\b|from\s+your\s+contacts\b)|"
    r"(?:do\s+not|don't)\s+(?:email|contact)\s+me\b|stop\s+(?:contacting|emailing)\s+me\b)",
    re.IGNORECASE,
)
_CLEAR_DIRECT_REQUEST = re.compile(
    r"\bplease\s+(?:remove\s+me\s+from\s+(?:your|the|this)\s+(?:mailing\s+)?list|"
    r"unsubscribe\s+me|stop\s+(?:sending\s+)?(?:me\s+)?emails|"
    r"(?:do\s+not|don't)\s+(?:email|contact)\s+me)\b",
    re.IGNORECASE,
)
_QUOTE_BOUNDARY = re.compile(
    r"^(?:>+\s*|on\s+.{1,150}\s+wrote\s*:|from\s*:|-----original message-----|"
    r"sent\s*:|subject\s*:)",
    re.IGNORECASE,
)
_UNAVAILABLE_BODY = {"", "[provider body unavailable]", "[message unavailable]"}
_SINGLE_WORD_OPTOUT = re.compile(r"^stop[.!]?$", re.IGNORECASE)


def explicit_opt_out_from_preview(subject: Any, body_preview: Any) -> dict[str, Any]:
    """Return a conservative protective signal, never execution authority.

    Subject alone can establish an explicit request when it is solely an
    opt-out subject. Otherwise inspect only the sender's first unquoted block.
    Quoted marketing boilerplate and a discussion *about* opt-outs are ignored.
    """
    subj = str(subject or "").strip()[:250]
    body = str(body_preview or "").strip()[:600]
    if _DIRECT_SUBJECT.fullmatch(subj):
        return {
            "explicit_opt_out_observed": True,
            "evidence_kind": "direct_subject",
            "suppression_write_verified": False,
            "auto_apply": False,
        }
    if body.lower() in _UNAVAILABLE_BODY:
        return {
            "explicit_opt_out_observed": False,
            "evidence_kind": "unavailable",
            "suppression_write_verified": False,
            "auto_apply": False,
        }
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if _QUOTE_BOUNDARY.match(stripped):
            break
        if stripped:
            lines.append(stripped)
        if len(lines) >= 3:
            break
    candidate = " ".join(lines)[:350].strip()
    # Generic opt-out advice, negation or quoting must never be interpreted
    # as an instruction from the recipient to suppress their own address.
    if (not candidate
            or re.search(r"\b(?:don't|do not|not trying to|cannot)\s+(?:want\s+to\s+)?(?:opt[ -]?out|unsubscribe)\b",
                         candidate, re.IGNORECASE)):
        found = False
    else:
        found = bool(
            _SINGLE_WORD_OPTOUT.fullmatch(candidate)
            or _DIRECT_BODY_START.search(candidate)
            or _CLEAR_DIRECT_REQUEST.search(candidate)
        )
    return {
        "explicit_opt_out_observed": found,
        "evidence_kind": "direct_body_preview" if found else "not_proven",
        "suppression_write_verified": False,
        "auto_apply": False,
    }
