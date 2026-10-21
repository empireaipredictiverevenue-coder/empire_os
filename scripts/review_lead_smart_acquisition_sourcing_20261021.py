"""Read-only acquisition experiment inventory for the existing Lead Smart campaign.

Only first-party owned organic traffic is currently buyer scoped. These
research observations are NOT permission for third-party referrals, outreach,
call activation, source attribution or payable revenue.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PARTNERS = "docs/commercial/LEAD_SMART_CHICAGO_ORGANIC_REFERRAL_RESEARCH_20261021.csv"
DEMAND = "docs/commercial/LEAD_SMART_HOMEOWNER_DEMAND_OBSERVATIONS_20261021.csv"

ALLOWED_CATEGORIES = {
    "home_inspector", "gutter_specialist", "property_maintenance",
    "property_manager", "restoration_service",
}
PARTNER_STATUS = "RESEARCHED_NO_CONTACT"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def evaluate(root: Path = ROOT) -> dict:
    partners = rows(root / PARTNERS)
    demand = rows(root / DEMAND)
    if len(partners) != 20:
        raise ValueError("EXACT_20_DISTINCT_RESEARCH_CANDIDATES_REQUIRED")
    if len(demand) < 1:
        raise ValueError("DEMAND_OBSERVATIONS_REQUIRED")
    ids: set[str] = set()
    hosts: set[str] = set()
    for entry in partners:
        identity = entry.get("candidate_id", "")
        name = entry.get("organisation", "")
        raw = entry.get("source_url", "")
        url = urlsplit(raw)
        host = (url.hostname or "").lower().removeprefix("www.")
        if (not identity.startswith("LSCHI") or identity in ids
                or not name or host in hosts or not host or url.scheme != "https"
                or not entry.get("fit_observation")
                or not entry.get("channel_risk")
                or entry.get("category") not in ALLOWED_CATEGORIES
                or entry.get("status") != PARTNER_STATUS):
            raise ValueError("INVALID_OR_UNAPPROVED_PARTNER_SOURCE")
        ids.add(identity)
        hosts.add(host)
    seen_urls: set[str] = set()
    for entry in demand:
        url = entry.get("url", "")
        if (not url.startswith("https://www.reddit.com/r/")
                or url in seen_urls
                or not entry.get("age_or_location_issue")
                or entry.get("eligible_for_direct_calls") != "false"
                or entry.get("contacted_or_replied") != "false"
                or not entry.get("status", "").startswith(("INFORMATION_ONLY", "ARCHIVE_INFORMATION_ONLY"))):
            raise ValueError("UNAUTHORIZED_DEMAND_PROMOTION")
        seen_urls.add(url)
    return {
        "schema_version": "empire.lead_smart.homeowner_acquisition_research.v1",
        "mode": "READ_ONLY",
        "campaign": "Lead Smart roofing Direct",
        "partner_organisations_researched": len(partners),
        "partner_categories": dict(sorted(Counter(p["category"] for p in partners).items())),
        "web_researched_sources": sum(p["evidence_source"] != "prior_handoff_unreverified" for p in partners),
        "prior_handoff_sources_requiring_fresh_check": sum(p["evidence_source"] == "prior_handoff_unreverified" for p in partners),
        "public_demand_discussions_observed": len(demand),
        "qualified_consented_homeowner_leads": 0,
        "partner_referrals_authorized": 0,
        "partner_messages_sent_by_this_review": 0,
        "community_posts_sent_by_this_review": 0,
        "first_party_handoffs_proven_by_this_review": 0,
        "verified_payable_calls_proven_by_this_review": 0,
        "first_party_only_source_constraint": "EMPIRE_FIRST_PARTY_ORGANIC",
        "partner_source_authority": "NOT_AUTHORIZED",
        "buyer_affiliate_route_for_partner_visits": "NOT_APPROVED",
        "next_action": "OWNER_REVIEW_PARTNER_AND_COMMUNITY_RIGHTS_BEFORE_EXTERNAL_CONTACT",
        "execution_authority": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), sort_keys=True))
