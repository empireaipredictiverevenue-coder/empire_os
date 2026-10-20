"""Prompt-to-B2B source targeting without claiming a contact or sale.

Uses only existing public research-source records, with no network or LLM
request. Intended as a safe, bounded extraction stage for later ASTRA prompts.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit
import re

from empire_os.a2a_commercial_signal_miner import AGENT_ID, COMMUNITY_SCHEMA
from empire_os.icp_intent_relevance import classify_icp_intent

SCHEMA = "empire.a2a.prompt_targeted_research.v1"
REPORT_SCHEMA = "empire.a2a.targeted_buyer_source_review.v1"
NICHE_RULES = (
    ("general_contractor", r"\b(?:general contractor|commercial construction|permit intelligence|construction data)\b"),
    ("roofing", r"\b(?:roofing|roofer|restoration contractor)\b"),
    ("hvac", r"\b(?:hvac|heating and air|air conditioning)\b"),
    ("solar", r"\bsolar\b"),
    ("plumbing", r"\bplumb(?:ing|er|ers)\b"),
    ("law", r"\b(?:law firm|attorney)\b"),
    ("agency", r"\b(?:marketing agenc(?:y|ies)|seo agenc(?:y|ies))\b"),
    ("b2b", r"\b(?:b2b|revops|revenue operations)\b"),
)
CITY_RULES = (
    ("little rock", "little rock, ar", "US"),
    ("tampa", "tampa, fl", "US"),
    ("new york city", "nyc", "US"),
    ("new york", "nyc", "US"),
    ("brooklyn", "brooklyn, ny", "US"),
    ("phoenix", "phoenix, az", "US"),
    ("atlanta", "atlanta, ga", "US"),
    ("london", "london", "UK"),
)
PRODUCT_RULES = (
    ("leads_calls_appointments", r"\b(?:calls?|appointments?|leads?|pay.per.call|pay.per.lead)\b"),
    ("business_data_intelligence", r"\b(?:data|dataset|permit|intelligence|research report)\b"),
    ("revenue_conversion_software", r"\b(?:crm|sales automation|conversion software|sales software)\b"),
)
_FORBIDDEN_PROMPT_CHARS = re.compile(r"[\x00-\x1f<>{}`]")
_B2B = re.compile(r"\b(?:businesses|companies|firms|contractors|operators|buyers|directors|owners|agencies|data)\b")
_ROLE_RULES = (
    ("owner", r"\bowners?\b"),
    ("growth_director", r"\b(?:head of growth|growth director|marketing director)\b"),
    ("lead_buyer", r"\b(?:lead buyers?|call buyers?|appointment buyers?)\b"),
    ("procurement", r"\b(?:procurement|purchasing|estimators?)\b"),
)

def compile_target_prompt(prompt: str) -> dict[str, Any]:
    if not isinstance(prompt, str) or not 15 <= len(prompt.strip()) <= 550:
        raise ValueError("PROMPT_LENGTH_REQUIRED")
    if _FORBIDDEN_PROMPT_CHARS.search(prompt):
        raise ValueError("UNSAFE_PROMPT_FORMAT")
    text = " ".join(prompt.casefold().split())
    matches = [k for k, pat in NICHE_RULES if re.search(pat, text)]
    # Exclusions naming agencies must not change roofing/HVAC to agency target.
    if "agency" in matches and len(matches) > 1:
        matches.remove("agency")
    niches = list(dict.fromkeys(matches))
    niche = niches[0] if len(niches) == 1 else None
    locations = {(norm, country) for phrase, norm, country in CITY_RULES
                 if re.search(r"\b" + re.escape(phrase) + r"\b", text)}
    if "nyc" in {c for c, _ in locations} and "brooklyn, ny" in {c for c, _ in locations}:
        locations = {v for v in locations if v[0] == "brooklyn, ny"}
    metro, country = next(iter(locations)) if len(locations) == 1 else (None, None)
    products = [k for k, pat in PRODUCT_RULES if re.search(pat, text)]
    product = products[0] if products else None
    roles = [k for k, pat in _ROLE_RULES if re.search(pat, text)]
    exclusions = []
    if re.search(r"\b(?:exclude|no|not|without)\b.{0,55}\b(?:resellers?|brokers?|aggregators?)\b", text):
        exclusions.append("UNVERIFIED_RESELLERS")
    if re.search(r"\b(?:exclude|no|not|without)\b.{0,55}\b(?:agencies|agency)\b", text):
        exclusions.append("AGENCY_INTERMEDIARIES")
    missing = []
    if niche is None: missing.append("NICHE_AMBIGUOUS")
    if metro is None: missing.append("MARKET_LOCATION_NOT_EXPLICIT")
    if product is None: missing.append("PRODUCT_TYPE_UNSPECIFIED")
    if not _B2B.search(text): missing.append("BUSINESS_AUDIENCE_NOT_CLEAR")
    return {
        "schema_version": SCHEMA, "agent_id": AGENT_ID,
        "target_id": sha256(text.encode()).hexdigest()[:20],
        "prompt": prompt.strip(),
        "parser_type": "DETERMINISTIC_PROMPT_EXTRACTION_NOT_LLM",
        "niche": niche, "metro": metro, "country": country,
        "product_type": product,
        "buyer_roles_to_verify": roles or ["business_decision_maker_unverified"],
        "negative_filters": exclusions,
        "missing_details": missing, "research_ready": not missing,
        "external_contact_authorized": False,
        "campaign_authorized": False, "personal_profile_targeting": False,
        "execution_authority": "NONE",
    }

def target_source_review(
    target: Mapping[str, Any], community: Mapping[str, Any],
    *, now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError("CLOCK_TIMEZONE_REQUIRED")
    now = now.astimezone(timezone.utc)
    if not isinstance(target, Mapping) or target.get("schema_version") != SCHEMA:
        raise ValueError("UNTRUSTED_TARGET_SPEC")
    if target.get("agent_id") != AGENT_ID or target.get("execution_authority") != "NONE":
        raise ValueError("UNTRUSTED_TARGET_OWNER")
    if target.get("external_contact_authorized") is not False or target.get("campaign_authorized") is not False:
        raise ValueError("TARGET_NOT_READ_ONLY")
    if target.get("research_ready") is not True:
        return {
            "schema_version": REPORT_SCHEMA, "target_id": target.get("target_id"),
            "status": "TARGET_CLARIFICATION_REQUIRED",
            "missing": target.get("missing_details"),
            "permitted_sources": [], "public_discussion_refs": [],
            "businesses_verified": 0, "execution_authority": "NONE",
        }
    if not isinstance(community, Mapping) or community.get("schema_version") != COMMUNITY_SCHEMA:
        raise ValueError("UNTRUSTED_COMMUNITY_SCHEMA")
    if (community.get("mode") != "OBSERVE" or community.get("outreach_authority") != "none"
            or str(community.get("execution_authority")).lower() != "none"):
        raise ValueError("UNTRUSTED_COMMUNITY_AUTHORITY")
    date = community.get("observed_at")
    try: stamp = datetime.fromisoformat(str(date).replace("Z", "+00:00"))
    except ValueError: raise ValueError("INVALID_COMMUNITY_STAMP") from None
    if stamp.tzinfo is None or not now - timedelta(hours=48) <= stamp.astimezone(timezone.utc) <= now + timedelta(minutes=5):
        raise ValueError("STALE_COMMUNITY_SOURCE")
    atlas = community.get("icp_source_atlas")
    if (not isinstance(atlas, Mapping) or atlas.get("schema_version") != "empire.icp_research_sources.v1"
            or atlas.get("mode") != "OBSERVE"
            or atlas.get("execution_authority") != "NONE"
            or atlas.get("outbound_authorized") is not False
            or atlas.get("private_or_login_gated_scraping_enabled") is not False):
        raise ValueError("UNTRUSTED_SOURCE_ATLAS")
    rows = atlas.get("sources")
    if not isinstance(rows, list) or len(rows) > 100: raise ValueError("INVALID_ATLAS_SOURCES")
    health = community.get("source_status")
    if not isinstance(health, Mapping): raise ValueError("MISSING_COLLECTION_HEALTH")
    reddit_ok = isinstance(health.get("reddit"), Mapping) and health["reddit"].get("ok") is True
    matches = []
    for row in rows:
        if not isinstance(row, Mapping): continue
        if row.get("niche") != target.get("niche"): continue
        if (row.get("venue") != "Reddit" or row.get("access") != "public_reddit_rss"
                or row.get("automation_state") != "OBSERVE" or row.get("outbound_authorized") is not False):
            continue
        url = row.get("url")
        if not isinstance(url, str) or urlsplit(url).hostname not in ("reddit.com", "www.reddit.com"):
            continue
        coverage = ( "COUNTRY_RESEARCH_ONLY_NOT_CITY_VERIFIED"
                    if row.get("geography") == target.get("country")
                    else "REGIONAL_BUYER_COVERAGE_UNKNOWN" )
        matches.append({
            "source_id": row.get("source_id"), "public_source": url,
            "topic": row.get("problem"), "geography_status": coverage,
            "reddit_platform_latest_report_success_not_this_specific_source": reddit_ok,
            "direct_buyer_identification": False, "contact_permission": False,
        })
    # Do not promote individual or personal Reddit posts to buyer records.
    # The existing owner's pain-solution aggregate supports only topical research.
    briefs = community.get("pain_solution_briefs")
    if not isinstance(briefs, list): briefs = []
    suggested_pains = {
        "leads_calls_appointments": ("lead_generation", "sales_conversion"),
        "business_data_intelligence": ("lead_generation", "search_visibility"),
        "revenue_conversion_software": ("sales_conversion", "revenue_growth", "automation_ops"),
    }[target["product_type"]]
    refs = []
    for brief in briefs[:100]:
        if not isinstance(brief, Mapping) or brief.get("pain_point") not in suggested_pains:
            continue
        for url in (brief.get("evidence_urls") or [])[:8]:
            if not isinstance(url, str): continue
            u = urlsplit(url)
            if u.scheme != "https" or u.hostname not in ("reddit.com","www.reddit.com") or not reddit_ok or not u.path.startswith("/r/") or "/comments/" not in u.path:
                continue
            refs.append({
                "public_url_for_owner_review": url.split("?")[0].split("#")[0],
                "aggregate_pain": brief["pain_point"],
                "buyer_intent_verified": False, "geo_verified": False,
                "outreach_authorized": False,
            })
    refs = sorted({x["public_url_for_owner_review"]: x for x in refs}.values(), key=lambda x:x["public_url_for_owner_review"])[:10]
    # Transient read of real public post text; only minimum non-identifying
    # evidence survives into the report. No author names or post copies.
    matching_posts = []
    obs_rows = community.get("top_observations")
    obs_rows = obs_rows if isinstance(obs_rows, list) else []
    if len(obs_rows) > 200:
        raise ValueError("EXCESS_UNTRUSTED_PUBLIC_POSTS")
    for obs in obs_rows:
        if not isinstance(obs, Mapping) or obs.get("source") != "reddit" or not reddit_ok:
            continue
        if obs.get("niche") != target["niche"]:
            continue
        post_url = obs.get("url")
        if not isinstance(post_url, str) or len(post_url) > 2048:
            continue
        parsed = urlsplit(post_url)
        if parsed.scheme != "https" or parsed.hostname not in ("reddit.com", "www.reddit.com") or not parsed.path.startswith("/r/") or "/comments/" not in parsed.path:
            continue
        if parsed.username or parsed.password:
            continue
        observed_at = obs.get("observed_at")
        try: seen = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        except ValueError: continue
        if seen.tzinfo is None or not now - timedelta(hours=48) <= seen.astimezone(timezone.utc) <= now + timedelta(minutes=5):
            continue
        cls = classify_icp_intent(obs)
        if cls["intent_class"] not in ("EXPLICIT_REQUEST_UNVERIFIED", "OPERATOR_PROBLEM_SELF_REPORTED"):
            continue
        matching_posts.append({
            "source_public_post_for_owner_review": post_url.split("?")[0].split("#")[0],
            "intent_classification": cls["intent_class"],
            "niche_classification": target["niche"],
            "metro_classification": obs.get("metro") if obs.get("metro") == target["metro"] else "NOT_MATCHED",
            "target_geo_verified": False,
            "buyer_business_verified": False,
            "buyer_capacity_verified": False,
            "personal_author_removed_from_research_output": True,
            "raw_post_text_retained": False,
            "outbound_authorized": False,
        })
    matching_posts = [matching_posts[k] for k in range(len(matching_posts))
                      if matching_posts[k]["source_public_post_for_owner_review"] not in
                      {x["source_public_post_for_owner_review"] for x in matching_posts[:k]}][:10]
    return {
        "schema_version": REPORT_SCHEMA, "target_id": target["target_id"],
        "niche": target["niche"], "market": target["metro"],
        "product": target["product_type"],
        "status": ("PERMITTED_NICHE_RESEARCH_AVAILABLE_FOR_OWNER_REVIEW" if matches else
                   "NO_NICHE_SOURCE_FOUND_REVIEW_OTHER_PERMITTED_SOURCES"),
        "permitted_sources": matches[:10], "public_discussion_refs": refs,
        "source_count": len(matches), "research_reference_count": len(refs),
        "niche_matched_public_post_research": matching_posts,
        "niche_matched_public_post_count": len(matching_posts),
        "discussion_references_are_not_target_niche_or_geo_confirmation": True,
        "owner": "existing_community_intent_and_buyer_scout_owners",
        "next_owner_action": "VERIFY_BUSINESS_INTENT_GEO_BUYING_CAPACITY_AND_CANONICAL_DUPLICATES",
        "owner_handoff_dispatched": False,
        "verified_businesses": 0, "sales_qualified_leads": 0,
        "city_level_buyer_evidence_verified": False, "contact_authorized": False,
        "external_messaging": False, "ad_campaign_created": False,
        "payment_collected": False, "execution_authority": "NONE",
    }
