"""Apple/iCloud destination evidence normalization.

Apple does not expose a complaint feedback loop. Ringleader therefore relies on SMTP/NDR
evidence plus controlled seed placement and authentication observations.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


_ENHANCED = re.compile(r"\b([245])\.(\d{1,3})\.(\d{1,3})\b")


def normalize_apple_delivery_evidence(
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
        signals.append("permanent_apple_rejection")
    elif smtp is not None and 400 <= smtp < 500:
        posture = "BACKOFF_APPLE"
        signals.append("transient_apple_deferral")

    if any(token in lowered for token in ("spf", "dkim", "dmarc", "authentication")):
        signals.append("apple_authentication_signal")
    if "policy" in lowered or "reputation" in lowered:
        signals.append("apple_policy_or_reputation_signal")

    return {
        "posture": posture,
        "smtp_code": smtp,
        "enhanced_status": enhanced,
        "signals": list(dict.fromkeys(signals)),
        "scope": "apple_destination_only",
        "raw_diagnostic": text,
    }
