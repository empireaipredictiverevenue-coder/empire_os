"""Deliverability and sender-reputation policy for governed outbound email."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_REPLY_PREFIX_RE = re.compile(r"^\s*(re|fw|fwd)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class DeliverabilityPolicy:
    """Internal safety envelope; intentionally stricter than provider shutdown limits."""

    max_bounce_rate: float = 0.02
    max_complaint_rate: float = 0.0005
    hard_daily_cap_per_mailbox: int = 40
    max_volume_spike_ratio: float = 1.50


def _rate(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    # Provider APIs can expose either fractions (0.0385) or percentages (3.85).
    return parsed / 100.0 if parsed > 1 else parsed


def evaluate_sender_health(
    context: Mapping[str, Any] | None,
    *,
    policy: DeliverabilityPolicy | None = None,
) -> dict[str, Any]:
    """Evaluate whether a sender may be considered healthy enough for a send gate."""

    policy = policy or DeliverabilityPolicy()
    context = dict(context or {})
    hard: list[str] = []
    evidence: list[str] = []

    permitted = context.get("provider_policy_permits_use_case")
    if permitted is False:
        hard.append("provider_policy_prohibits_use_case")
    elif permitted is not True:
        evidence.append("provider_policy_compatibility_unverified")

    for key, reason in (
        ("spf_aligned", "spf_alignment_unverified"),
        ("dkim_aligned", "dkim_alignment_unverified"),
        ("dmarc_valid", "dmarc_unverified"),
        ("tls_ready", "tls_unverified"),
    ):
        if context.get(key) is not True:
            evidence.append(reason)

    if context.get("recipient_verified") is not True:
        evidence.append("recipient_verification_unverified")

    bounce_rate = _rate(context.get("bounce_rate"))
    if bounce_rate is None:
        evidence.append("bounce_rate_unverified")
    elif bounce_rate > policy.max_bounce_rate:
        hard.append("bounce_rate_above_internal_limit")

    complaint_rate = _rate(context.get("complaint_rate"))
    if complaint_rate is None:
        evidence.append("complaint_rate_unverified")
    elif complaint_rate > policy.max_complaint_rate:
        hard.append("complaint_rate_above_internal_limit")

    try:
        daily_cap = int(context.get("daily_cap"))
    except (TypeError, ValueError):
        daily_cap = -1
    if daily_cap < 1:
        evidence.append("daily_cap_unverified")
    elif daily_cap > policy.hard_daily_cap_per_mailbox:
        hard.append("daily_cap_above_internal_limit")

    spike = context.get("volume_spike_ratio")
    if spike is not None:
        try:
            spike_ratio = float(spike)
        except (TypeError, ValueError):
            evidence.append("volume_spike_ratio_invalid")
        else:
            if spike_ratio > policy.max_volume_spike_ratio:
                hard.append("sudden_volume_spike")

    if hard:
        decision = "HOLD"
    elif evidence:
        decision = "ESCALATE"
    else:
        decision = "READY"

    return {
        "decision": decision,
        "hard_holds": hard,
        "evidence_holds": evidence,
        "observed": {
            "bounce_rate": bounce_rate,
            "complaint_rate": complaint_rate,
            "daily_cap": daily_cap if daily_cap >= 0 else None,
        },
    }


def lint_first_touch(
    message: Mapping[str, Any],
) -> dict[str, list[str]]:
    """Flag avoidable first-touch patterns that increase distrust or spam complaints."""

    subject = str(message.get("subject") or "")
    body = str(message.get("body_text") or "")
    sender = str(message.get("from") or message.get("sender") or "").lower()
    is_reply = message.get("is_reply") is True
    attachment_count = int(message.get("attachment_count") or 0)

    hard: list[str] = []
    recommendations: list[str] = []

    if _REPLY_PREFIX_RE.search(subject) and not is_reply:
        hard.append("deceptive_reply_or_forward_prefix")

    if "no-reply@" in sender or "noreply@" in sender:
        recommendations.append("avoid_no_reply_sender")

    links = _URL_RE.findall(body)
    if len(links) > 1:
        recommendations.append("reduce_first_touch_links")
    if attachment_count:
        recommendations.append("avoid_first_touch_attachments")
    if subject and subject == subject.upper() and any(ch.isalpha() for ch in subject):
        recommendations.append("avoid_all_caps_subject")
    if subject.count("!") > 1 or body.count("!") > 3:
        recommendations.append("reduce_excessive_urgency_formatting")

    return {
        "hard_holds": hard,
        "recommendations": recommendations,
    }
