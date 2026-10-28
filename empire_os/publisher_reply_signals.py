"""Read-only recognition of publisher negotiation messages.

Input must already be the top-level visible reply from the existing
buyer_mail_semantics Gmail parser. Only unverified event codes emerge.
"""
from __future__ import annotations

import re


def recognize_publisher_reply(text: str) -> set[str]:
    if not isinstance(text, str) or not text:
        return set()
    source = text.casefold()[:8000]
    result: set[str] = set()
    if ("single-installer, accepted-outcome approach works for us" in source
            and ("pilot" in source or "30 days" in source)):
        result.add("PUBLISHER_ACCEPTED_OUTCOME_PILOT_REPORTED")
    if ("as a negotiating target only" in source
            and re.search(r"minimum\s+of\s+£\d+\s+per\s+(?:accepted\s+)?event", source)
            and re.search(r"\b\d+%\s+of\s+the\s+amount\s+the\s+installer", source)):
        result.add("PUBLISHER_REVENUE_SHARE_TARGET_REPORTED")
    if ("nothing goes live" in source
            and "terms are signed" in source
            and "coverage is verified" in source):
        result.add("PUBLISHER_SIGNED_TERMS_AND_COVERAGE_REQUIRED_REPORTED")
    return result
