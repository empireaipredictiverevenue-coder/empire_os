"""Existing competitor intelligence: research-only FREE vs PAID traffic sources.

No second acquisition/SEO agent. This is an evidenced source registry for the
original Founder competitor feed; it doesn't create campaigns, contacts, leads,
ad accounts, publication tasks, call routes, or estimated conversions.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "empire.call_traffic_source_registry.v1"
INPUT_SCHEMA = "empire.call_traffic_source_registry_sources.v1"
SOURCE = Path("docs/commercial/call_traffic_source_registry_20261027.json")
DEST = Path("runtime/competitive_intelligence/call_traffic_source_registry_latest.json")
FREE = "FREE_MEDIA_WITH_LABOUR"
PAID = frozenset({
    "PAID_CPC", "PAID_AD_AUCTION", "PERFORMANCE_PAID",
    "PAID_CPC_OR_CPA", "PAID_PER_ELIGIBLE_LEAD",
})
AUDIENCE = {"HOMEOWNER"}
INTENTS = {"HIGH", "MEDIUM", "LOW"}
FAMILIES = {
    "SEARCH", "REFERRAL", "SOCIAL_VIDEO", "COMMUNITY", "OWNED_AUDIENCE",
    "LOCAL_SOCIAL", "VISUAL_DISCOVERY", "AFFILIATE_PUBLISHER", "LOCAL_SEARCH",
}
EXPECTED_IDS = frozenset({
    "organic_search", "earned_local_publisher", "youtube_organic",
    "community_earned", "opt_in_homeowner_referrals", "nextdoor_business_page",
    "pinterest_organic", "google_search_ads", "microsoft_ads", "meta_call_ads",
    "nextdoor_paid", "publisher_paid", "pinterest_ads", "reddit_ads", "google_lsa",
})
SOURCE_DOMAINS = frozenset({
    "developers.google.com", "modernize.com", "support.google.com",
    "support.reddithelp.com", "business.nextdoor.com", "help.pinterest.com",
    "about.ads.microsoft.com", "www.facebook.com",
    "business.reddithelp.com", "www.ftc.gov",
})
FIELDS = {
    "id", "name", "cost_class", "audience", "channel_family", "intent",
    "research_rank", "route", "publisher_role_fit", "permission_state",
    "sources", "next_proof", "scope",
}
MEASUREMENT_EVENTS = (
    "first_party_page_session", "referral_source", "source_tag",
    "consented_call_choice", "verified_call_connection",
    "buyer_accepted_payable_call", "verified_settled_receipt",
    "media_cost", "adjustment_or_refund",
)


def _validated_source_url(url: object) -> str:
    if not isinstance(url, str) or len(url) > 500:
        raise ValueError("source URL absent or oversized")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in SOURCE_DOMAINS
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.fragment):
        raise ValueError("unverified platform/source URL")
    return url


def _review_date(raw: object, at: datetime) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("missing observed source date")
    timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.astimezone(timezone.utc) > at:
        raise ValueError("source date missing timezone or future")
    return timestamp.astimezone(timezone.utc)


def build_registry(source: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware current time required")
    now = now.astimezone(timezone.utc)
    if (not isinstance(source, dict) or source.get("schema_version") != INPUT_SCHEMA
            or source.get("vertical") != "US_ROOFING_HOMEOWNER_INFORMATION"
            or source.get("purpose") != "RESEARCH_FREE_AND_PAID_CHANNELS_NOT_APPROVED_CAMPAIGN_PLAN"):
        raise ValueError("original source inventory not permitted")
    reviewed_at = _review_date(source.get("researched_at_utc"), now)
    raw_rows = source.get("channels")
    if not isinstance(raw_rows, list) or len(raw_rows) != len(EXPECTED_IDS):
        raise ValueError("incomplete original source inventory")
    controls = source.get("global_controls")
    required_control_keys = {
        "media_spend_authority", "ad_account_mutation", "leads_created",
        "outbound_sent", "site_published", "call_route_mutation",
        "publisher_admission_approved", "settled_revenue_verified",
    }
    if (not isinstance(controls, dict) or controls.get("mode") != "OBSERVE"
            or any(controls.get(key) is not False for key in required_control_keys)):
        raise ValueError("traffic source source grants unsupported authority")

    rows = []
    seen = set()
    for item in raw_rows:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError("untrusted/incomplete traffic row")
        ident = item["id"]
        if ident not in EXPECTED_IDS or ident in seen:
            raise ValueError("unexpected or duplicated traffic source")
        seen.add(ident)
        if item["audience"] not in AUDIENCE or item["intent"] not in INTENTS:
            raise ValueError("source audience/intent invalid")
        if item["channel_family"] not in FAMILIES:
            raise ValueError("unsupported channel family")
        cost = item["cost_class"]
        if cost != FREE and cost not in PAID:
            raise ValueError("unknown source media cost model")
        if type(item["research_rank"]) is not int:
            raise ValueError("research order must be integer")
        expected_rank_range = range(1, 8) if cost == FREE else range(101, 108) if ident != "google_lsa" else (999,)
        if item["research_rank"] not in expected_rank_range:
            raise ValueError("source cost and research order disagree")
        if ident == "google_lsa":
            if (item["permission_state"] != "EXCLUDE_EMPIRE_LEAD_RESALE"
                    or item["publisher_role_fit"] != "PROHIBITED_FOR_LEAD_RESELLING"):
                raise ValueError("Google Local Services cannot be used for resale")
        else:
            if ("APPROVED" in item["permission_state"]
                    and "NOT_APPROVED" not in item["permission_state"]):
                raise ValueError("no traffic sources approved for live operations")
        for field in ("name", "route", "permission_state", "publisher_role_fit", "next_proof", "scope"):
            if not isinstance(item[field], str) or not 5 <= len(item[field]) <= 330:
                raise ValueError("source disclosure text invalid")
        sources = item["sources"]
        if not isinstance(sources, list) or not 1 <= len(sources) <= 3:
            raise ValueError("missing original provider/policy evidence")
        refs = [_validated_source_url(src) for src in sources]
        if len(set(refs)) != len(refs):
            raise ValueError("duplicate evidence source")
        status = (
            "EXCLUDED_POLICY" if ident == "google_lsa" else
            "CONDITIONAL_ELIGIBILITY_REVIEW" if item["permission_state"].startswith("HOLD_") else
            "PAID_UNFUNDED_RESEARCH_ONLY" if cost in PAID else
            "ORGANIC_EARNED_RESEARCH_ONLY"
        )
        rows.append({
            **item,
            "sources": refs,
            "source_class": "PUBLISHED_PLATFORM_CAPABILITY_OR_POLICY",
            "status": status,
            "eligible_for_immediate_ad_spend": False,
            "automated_publication_allowed": False,
            "buyer_campaign_traffic_source_accepted": False,
            "actual_traffic_volume": None,
            "actual_paid_call_cpa_usd": None,
            "verified_settled_revenue_usd": None,
            "profitable_unit_economics_observed": False,
        })
    if seen != EXPECTED_IDS:
        raise ValueError("source roster mismatched")

    no_cost_media = sorted(
        (r for r in rows if r["cost_class"] == FREE),
        key=lambda r: r["research_rank"],
    )
    paid = sorted(
        (r for r in rows if r["cost_class"] in PAID and r["status"] != "EXCLUDED_POLICY"),
        key=lambda r: r["research_rank"],
    )
    blocked = [r for r in rows if r["status"] == "EXCLUDED_POLICY"]
    if len(no_cost_media) != 7 or len(paid) != 7 or len(blocked) != 1:
        raise ValueError("source cost segmentation inconsistent")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "researched_at_utc": reviewed_at.isoformat(),
        "vertical": source["vertical"],
        "source_count": len(rows),
        "organic_earned_count": len(no_cost_media),
        "paid_candidate_count": len(paid),
        "policy_excluded_count": len(blocked),
        "free_or_earned": no_cost_media,
        "paid_research_only": paid,
        "excluded": blocked,
        "outcome_measurement_contract": {
            key: None for key in MEASUREMENT_EVENTS
        },
        "measurement_provenance_status": "AWAITING_REAL_FIRST_PARTY_AND_PROVIDER_OBSERVATIONS",
        "ranking_semantics": "SOURCE_RESEARCH_PRIORITY_NOT_FORECAST_TRAFFIC_OR_PROFIT",
        "all_source_statuses_are_research_or_policy_excluded": True,
        "settled_revenue_verified": False,
        "consumer_leads_inferred": False,
        "buyer_acceptance_verified": False,
        "ad_account_mutation": False,
        "media_spend_authorized": False,
        "site_publication_authorized": False,
        "outbound_authorized": False,
        "provider_route_mutation": False,
        "execution_authority": "none",
    }


def refresh(repo_root: Path) -> dict:
    original = json.loads((repo_root / SOURCE).read_text(encoding="utf-8"))
    report = build_registry(original)
    target = repo_root / DEST
    if not target.parent.is_dir() or target.parent.is_symlink() or target.is_symlink():
        raise ValueError("unsafe original competitive intelligence runtime")
    fd, temp = tempfile.mkstemp(prefix=".traffic-source-", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(report, writer, indent=2, sort_keys=True)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return report
