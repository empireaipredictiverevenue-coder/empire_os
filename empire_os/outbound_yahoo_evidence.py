"""Yahoo destination evidence normalization.

Yahoo Sender Hub Insights currently has no public API. Evidence therefore comes from
SMTP diagnostics, controlled seed placement, and optional externally captured Sender Hub
or Complaint Feedback Loop observations.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


_ENHANCED = re.compile(r"\b([245])\.(\d{1,3})\.(\d{1,3})\b")


def normalize_yahoo_delivery_evidence(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    text = str(context.get("response") or context.get("diagnostic") or "").strip()
    smtp_code = context.get("smtp_code")
    try:
        smtp = int(smtp_code) if smtp_code is not None else None
    except (TypeError, ValueError):
        smtp = None

    match = _ENHANCED.search(text)
    enhanced = ".".join(match.groups()) if match else None
    lowered = text.lower()

    signals: list[str] = []
    posture = "OBSERVE"

    if smtp is not None and 500 <= smtp < 600:
        posture = "HOLD_RECIPIENT"
        signals.append("permanent_yahoo_rejection")
    elif smtp is not None and 400 <= smtp < 500:
        posture = "BACKOFF_YAHOO"
        signals.append("transient_yahoo_deferral")

    if "authentication" in lowered or "dkim" in lowered or "dmarc" in lowered or "spf" in lowered:
        signals.append("yahoo_authentication_signal")
    if "unknown recipient" in lowered or "invalid recipient" in lowered:
        signals.append("yahoo_invalid_recipient_signal")
    if "unsolicited" in lowered or "spam" in lowered:
        signals.append("yahoo_reputation_or_complaint_signal")

    spam_rate = context.get("sender_hub_spam_rate")
    if spam_rate is not None:
        try:
            value = float(spam_rate)
        except (TypeError, ValueError):
            value = None
        if value is not None:
            # Yahoo's published bulk-sender enforcement ceiling is 0.3%.
            if value >= 0.003:
                posture = "HOLD_YAHOO"
                signals.append("yahoo_sender_hub_spam_rate_at_or_above_enforcement_ceiling")
            elif value >= 0.001:
                if posture == "OBSERVE":
                    posture = "LIMIT_YAHOO"
                signals.append("yahoo_sender_hub_spam_rate_elevated")

    complaints = int(context.get("arf_complaints") or 0)
    if complaints:
        posture = "HOLD_YAHOO"
        signals.append("yahoo_cfl_complaint_present")

    return {
        "posture": posture,
        "smtp_code": smtp,
        "enhanced_status": enhanced,
        "signals": list(dict.fromkeys(signals)),
        "sender_hub_spam_rate": spam_rate,
        "arf_complaints": complaints,
        "scope": "yahoo_destination_only",
        "raw_diagnostic": text,
    }
