"""Offline, provenance-gated Meta social market-signal matching for Empire AI.

No network, scraping, collection, PII enrichment, canonical lead promotion,
buyers, payouts, database changes, publication or outbound authority.
The input is a pre-reviewed structured packet from an authorised origin.
"""
from __future__ import annotations

from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit
import re

SCHEMA = "empire.meta_social_opportunity_review.v1"
CHANNEL_HOSTS = {
    "facebook_group": ("facebook.com",),
    "facebook_marketplace": ("facebook.com",),
    "instagram": ("instagram.com",),
}
ACCESS_METHODS = frozenset({"official_approved_api", "authorised_manual_review", "consented_partner"})
KINDS = frozenset({"aggregate_demand", "business_supply", "market_pricing"})
FORBIDDEN_FIELDS = frozenset({
    "name", "person_name", "first_name", "last_name", "phone", "email",
    "username", "user_id", "member_id", "profile_id", "raw_text",
    "text", "body", "private_message", "direct_message", "contact",
    "address", "ip", "cookie", "access_token", "session",
})
ZIP = re.compile(r"^[0-9]{5}$")
NICHE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _canonical_url(value: Any, platform: str) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        u = urlsplit(value)
    except ValueError:
        return None
    if u.scheme != "https" or u.username or u.password or u.port:
        return None
    host = (u.hostname or "").lower()
    bases = CHANNEL_HOSTS[platform]
    if not any(host == base or host.endswith("." + base) for base in bases):
        return None
    if not u.path or u.path == "/":
        return None
    return urlunsplit(("https", host, u.path.rstrip("/"), "", ""))


def _iso_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def review_packet(packet: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Produce cautious market hypotheses, never actionable consumer leads."""
    if not isinstance(packet, Mapping) or packet.get("schema_version") != SCHEMA:
        raise ValueError("unsupported_packet_schema")
    rows = packet.get("observations")
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError("observations_must_be_bounded_list")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    accepted: dict[tuple[str, str, str, str], dict[str, str]] = {}
    held = Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            held["not_structured"] += 1
            continue
        if any(str(k).lower() in FORBIDDEN_FIELDS for k in row):
            held["personal_or_raw_content_field"] += 1
            continue
        platform = row.get("platform")
        if platform not in CHANNEL_HOSTS:
            held["unsupported_platform"] += 1
            continue
        url = _canonical_url(row.get("source_url"), platform)
        if not url:
            held["untrusted_source_url"] += 1
            continue
        if row.get("rights_status") != "verified_permitted" or row.get("access_method") not in ACCESS_METHODS:
            held["source_rights_not_verified"] += 1
            continue
        if row.get("subject_type") not in ("aggregated", "business"):
            held["consumer_or_unverified_subject"] += 1
            continue
        kind = row.get("kind")
        if kind not in KINDS:
            held["unsupported_signal_kind"] += 1
            continue
        if kind == "business_supply" and row["subject_type"] != "business":
            held["invalid_supply_subject"] += 1
            continue
        if kind == "aggregate_demand" and row["subject_type"] != "aggregated":
            held["individual_demand_disallowed"] += 1
            continue
        niche = row.get("niche")
        postcode = row.get("us_zip")
        if not isinstance(niche, str) or not NICHE.fullmatch(niche) or not isinstance(postcode, str) or not ZIP.fullmatch(postcode):
            held["invalid_market"] += 1
            continue
        observed = _iso_time(row.get("observed_at"))
        if observed is None or observed < now - timedelta(days=14) or observed > now + timedelta(minutes=5):
            held["stale_or_invalid_time"] += 1
            continue
        key = (url, kind, niche, postcode)
        # Collapse duplicate evidence, keeping newest observation per source.
        new = {
            "evidence_id": sha256("|".join(key).encode()).hexdigest()[:20],
            "source_url": url,
            "platform": platform,
            "niche": niche,
            "us_zip": postcode,
            "kind": kind,
            "observed_at": observed.isoformat(),
            "evidence_state": "authorised_source_observation_not_verified_purchase",
        }
        if key in accepted:
            held["duplicate_observation"] += 1
            if accepted[key]["observed_at"] < new["observed_at"]:
                accepted[key] = new
        else:
            accepted[key] = new

    buckets: dict[tuple[str, str], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: {"aggregate_demand": [], "business_supply": [], "market_pricing": []}
    )
    for observation in accepted.values():
        buckets[(observation["niche"], observation["us_zip"])][observation["kind"]].append(observation)
    opportunities = []
    for (niche, postcode), groups in sorted(buckets.items()):
        if not groups["aggregate_demand"] or not groups["business_supply"]:
            continue
        # An evidence-strength heuristic, NOT purchase intent probability.
        score = min(80, 35 + 10 * len(groups["aggregate_demand"]) +
                    10 * len(groups["business_supply"]) + 5 * len(groups["market_pricing"]))
        opportunities.append({
            "niche": niche, "us_zip": postcode,
            "evidence_strength_score_not_probability": score,
            "demand_evidence": sorted(x["evidence_id"] for x in groups["aggregate_demand"]),
            "supply_evidence": sorted(x["evidence_id"] for x in groups["business_supply"]),
            "market_pricing_evidence": sorted(x["evidence_id"] for x in groups["market_pricing"]),
            "market_match_state": "HYPOTHESIS_REQUIRES_BUSINESS_AND_CAPACITY_VERIFICATION",
            "verified_buyer_count": 0, "verified_purchaser_count": 0,
            "revenue_verified": False, "outbound_authorized": False,
            "canonical_lead_created": False,
        })
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "read_only": True,
        "live_meta_queries": 0, "meta_scraping": False, "database_writes": False,
        "published": False, "messages_sent": False, "paid_calls": 0,
        "reviewed_at": now.isoformat(), "observations_received": len(rows),
        "accepted_observations": len(accepted), "held_counts": dict(sorted(held.items())),
        "market_hypotheses": opportunities, "evidence": list(sorted(accepted.values(), key=lambda x: x["evidence_id"])),
        "next_action": "VERIFY_SOURCE_RIGHTS_PROVIDER_CAPACITY_BUYER_TERMS_AND_OPT_IN_BEFORE_COMMERCIAL_USE",
    }
