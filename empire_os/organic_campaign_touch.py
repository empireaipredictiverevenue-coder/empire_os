"""Nonidentifying UTM campaign touch attached to a buyer-initiated enquiry.

This is a claimed campaign token from a first-party URL, NOT an observed
session, CRM identity, conversion attribution, publisher receipt or revenue.
No cookies, cross-site tracking or new database.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

CAMPAIGN_RE = re.compile(r"campaign_[0-9a-f]{24}\Z")
LANDING_PATHS = frozenset((
    "/industries/solar",
    "/industries/roofing",
    "/commercial",
))
SOURCES = {
    "linkedin": ("organic_social", "linkedin"),
    "youtube": ("organic_video", "youtube"),
    "owned_newsletter": ("email", "newsletter"),
}
KEYS = frozenset(("campaign_id", "asset_id", "source", "medium", "landing_path"))


def normalize_organic_touch(raw: Any) -> dict[str, Any]:
    """Validate an all-or-nothing campaign token; never infer it as a lead."""
    if not isinstance(raw, Mapping) or set(raw) != KEYS:
        raise ValueError("untrusted_organic_touch_shape")
    if any(type(value) is not str or not 1 <= len(value) <= 120
           for value in raw.values()):
        raise ValueError("invalid_organic_touch_text")
    cid = raw["campaign_id"]
    source = raw["source"]
    if (not CAMPAIGN_RE.fullmatch(cid)
            or source not in SOURCES
            or raw["medium"] != SOURCES[source][0]
            or raw["asset_id"] != f"{cid}:{SOURCES[source][1]}"
            or raw["landing_path"] not in LANDING_PATHS):
        raise ValueError("untrusted_organic_touch_parameters")
    return {
        "campaign_id": cid,
        "asset_id": raw["asset_id"],
        "source": source,
        "medium": raw["medium"],
        "landing_path": raw["landing_path"],
        "evidence_class": "BUYER_SUBMITTED_URL_CAMPAIGN_TOKEN_ONLY",
        "session_verified": False,
        "channel_click_verified": False,
        "source_campaign_registry_verified": False,
        "attributable_enquiry_confirmed": False,
        "revenue_attribution_confirmed": False,
        "execution_authority": "none",
    }
