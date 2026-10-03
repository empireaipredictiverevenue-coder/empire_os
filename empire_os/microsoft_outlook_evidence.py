"""Microsoft/Outlook destination evidence normalization.

Microsoft consumer-mail evidence is primarily derived from NDR/SMTP results and controlled
seed placement. This module does not assume an undocumented SNDS/JMRP API.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


_ENHANCED = re.compile(r"\b([245])\.(\d{1,3})\.(\d{1,3})\b")


def normalize_outlook_delivery_evidence(
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

    signals: list[str] = []
    posture = "OBSERVE"

    if enhanced == "5.7.515" or "5.7.515" in text:
        posture = "HOLD_MICROSOFT"
        signals.append("microsoft_authentication_requirement_failure")
    elif smtp is not None and 500 <= smtp < 600:
        posture = "HOLD_RECIPIENT"
        signals.append("permanent_microsoft_rejection")
    elif smtp is not None and 400 <= smtp < 500:
        posture = "BACKOFF_MICROSOFT"
        signals.append("transient_microsoft_deferral")

    lowered = text.lower()
    if "spf" in lowered:
        signals.append("spf_referenced")
    if "dkim" in lowered:
        signals.append("dkim_referenced")
    if "dmarc" in lowered:
        signals.append("dmarc_referenced")

    return {
        "posture": posture,
        "smtp_code": smtp,
        "enhanced_status": enhanced,
        "signals": list(dict.fromkeys(signals)),
        "scope": "microsoft_destination_only",
        "raw_diagnostic": text,
    }
