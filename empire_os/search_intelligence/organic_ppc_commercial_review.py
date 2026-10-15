"""Evidence-first owned organic SEO -> PPC/PPL/call monetisation review.

One pure, read-only bridge for the existing Search Intelligence and affiliate
tracking modules. GSC clicks are *incoming search visits*, never payable
outbound advertiser clicks. NO redirects, conversion ingestion or funds.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

SCHEMA = "empire.search.owned_organic_ppc_commercial_review.v1"
GSC_SCHEMA = "empire.search.owned_gsc_organic_review.v1"
OWNED = "empire-ai.co.uk"
PAGE_PATHS = (
    "/", "/industries/roofing", "/industries/solar", "/industries/hvac",
    "/predictive-revenue", "/roofing", "/privacy", "/terms",
)

# Commercial research categorisation only. No signed contract, account
# approval or buyer payout is asserted by the presence of a programme page.
# These records are not consumed by any public redirect/paid ads integration.
RESEARCH_LANES = (
    {"programme": "Home Services Lead Group / Validated", "market": "USA", "role": "LEAD_BUYER_NETWORK", "model": "PAY_PER_CALL", "status": "HUMAN_REPLY_BUYBOX_UNKNOWN", "source": "gmail_thread:1a0cfb667dca0957"},
    {"programme": "Modernize", "market": "USA", "role": "PUBLISHER_AFFILIATE_PROGRAMME", "model": "PAY_PER_LEAD", "status": "CONTACTED_TERMS_UNKNOWN", "source": "gmail_sent:1a1349e18b6e46cf"},
    {"programme": "SolarBriton", "market": "UK", "role": "TRAFFIC_SUPPLY_PARTNER", "model": "REVENUE_SHARE_PILOT", "status": "DISCUSSION_NO_DOWNSTREAM_BUYER", "source": "gmail_thread:1a1268b899c78a29"},
    {"programme": "Your Solar Quotes", "market": "AU", "role": "PUBLISHER_AFFILIATE_PROGRAMME", "model": "PAY_PER_LEAD", "status": "PUBLIC_PROGRAMME_NOT_APPROVED", "source": "public:https://yoursolarquotes.com.au/solar-affiliate-program/"},
    {"programme": "LiveLeads", "market": "CA", "role": "PUBLISHER_AFFILIATE_PROGRAMME", "model": "PAY_PER_LEAD", "status": "PUBLIC_PROGRAMME_NOT_APPROVED", "source": "public:https://www.liveleads.ca/"},
    {"programme": "AdSense", "market": "MULTIMARKET", "role": "OPTIONAL_AD_NETWORK", "model": "DISPLAY_AD_IMPRESSIONS", "status": "NO_EMPIRE_AI_ACCOUNT_APPROVAL_VERIFIED", "source": "public:https://support.google.com/adsense/answer/9724/eligibility-requirements-for-adsense"},
)


def _site_evidence(page: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(page, Mapping) or set(page) != {
        "path", "http", "title_present", "h1_count", "canonical", "robots", "description_present",
    }:
        raise ValueError("invalid_site_observation_shape")
    path = page["path"]
    if path not in PAGE_PATHS:
        raise ValueError("out_of_scope_owned_site_path")
    status = page["http"]
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError("invalid_page_http_status")
    if type(page["title_present"]) is not bool or type(page["description_present"]) is not bool:
        raise ValueError("invalid_page_metadata_flags")
    h1 = page["h1_count"]
    if h1 is not None and (type(h1) is not int or not 0 <= h1 <= 12):
        raise ValueError("invalid_heading_evidence")
    canonical = page["canonical"]
    if canonical is not None:
        if not isinstance(canonical, str) or len(canonical) > 512:
            raise ValueError("invalid_canonical")
        u = urlsplit(canonical)
        if (u.scheme != "https" or u.hostname != OWNED
                or u.username is not None or u.password is not None
                or u.port is not None or u.query or u.fragment):
            raise ValueError("canonical_not_first_party_secure")
    robots = page["robots"]
    if not isinstance(robots, str) or len(robots) > 160:
        raise ValueError("invalid_robots_observation")
    held = "noindex" in robots.lower()
    canonical_matches = bool(canonical and urlsplit(canonical).path.rstrip("/") == path.rstrip("/"))
    signals = bool(status == 200 and page["title_present"] is True
                   and h1 == 1 and canonical_matches and page["description_present"] is True
                   and not held)
    return {
        "path": path, "http": status,
        "robots_noindex": held,
        "canonical_present": canonical is not None,
        "canonical_matches_path": canonical_matches,
        "technical_indexability_signals_present": signals,
        "google_indexed_verified": False,
        "independent_content_quality_verified": False,
        "buyer_source_approved": False,
    }


def review_owned_organic_ppc(
    baseline: Mapping[str, Any], *,
    pages: Sequence[Mapping[str, Any]],
    www_home_http: int | None,
    www_home_redirect_location: str | None,
) -> dict[str, Any]:
    """Classify observed SEO and mutually distinct monetisation models.

    Even perfectly shaped caller evidence is NEVER sufficient for publishing,
    paid traffic, affiliate redirects, click charging or revenue recognition.
    Buyer-approved terms and independent canonical source/payment events are
    separate mandatory authorities outside this preview.
    """
    if not isinstance(baseline, Mapping) or baseline.get("schema_version") != GSC_SCHEMA:
        raise ValueError("reviewed_owned_gsc_baseline_required")
    if (baseline.get("tenant_id") != "empire-ai"
            or baseline.get("site_id") != OWNED
            or baseline.get("gsc_property") != "sc-domain:" + OWNED
            or baseline.get("mode") != "OBSERVE"
            or baseline.get("measurement_status") != "GSC_DAILY_SITEWIDE_PLUS_QUERY_PAGE"
            or baseline.get("production_mutation") is not False
            or baseline.get("direct_publishing_allowed") is not False
            or baseline.get("outbound_allowed") is not False):
        raise ValueError("untrusted_or_incomplete_owned_gsc_baseline")
    dates = baseline.get("window")
    if not isinstance(dates, Mapping):
        raise ValueError("missing_gsc_window")
    try:
        start, end = date.fromisoformat(dates["start"]), date.fromisoformat(dates["end"])
    except (TypeError, ValueError, KeyError):
        raise ValueError("invalid_gsc_window") from None
    if end < start or (end-start).days > 31:
        raise ValueError("unbounded_gsc_window")
    site = baseline.get("sitewide_current")
    prior = baseline.get("sitewide_previous")
    if not isinstance(site, Mapping) or not isinstance(prior, Mapping):
        raise ValueError("sitewide_search_metrics_required")
    for row in (site, prior):
        for key in ("impressions", "clicks"):
            val = row.get(key)
            if type(val) is not int or val < 0 or val > 100_000_000:
                raise ValueError("invalid_sitewide_search_count")
        if row["clicks"] > row["impressions"] or row.get("commercial_source_attribution_verified") is not False:
            raise ValueError("source_search_clicks_cannot_be_commercial_conversions")
    if not isinstance(pages, (list, tuple)) or len(pages) != len(PAGE_PATHS):
        raise ValueError("complete_bounded_owned_page_audit_required")
    seen = set()
    checked=[]
    for page in pages:
        r=_site_evidence(page)
        if r["path"] in seen:
            raise ValueError("duplicate_owned_page_observation")
        seen.add(r["path"])
        checked.append(r)
    if seen != set(PAGE_PATHS):
        raise ValueError("missing_required_owned_page")
    if www_home_http is not None and (type(www_home_http) is not int or not 100 <= www_home_http <= 599):
        raise ValueError("invalid_www_http")
    if www_home_redirect_location is not None and (
        not isinstance(www_home_redirect_location, str)
        or www_home_redirect_location not in {"https://empire-ai.co.uk/", "https://empire-ai.co.uk"}
    ):
        raise ValueError("unsafe_www_redirect_location")
    index={p["path"]:p for p in checked}
    roof=index["/roofing"]
    roofing_held=roof["http"] == 200 and roof["robots_noindex"]
    www_still_200=www_home_http == 200
    technical=sum(p["technical_indexability_signals_present"] for p in checked)
    tasks=[]
    if site["impressions"] < prior["impressions"] or site["clicks"] < prior["clicks"]:
        tasks.append({"owner":"seo", "priority":"P1", "action":"REVIEW_ORGANIC_DEMAND_DECLINE", "reason":"observed_sitewide_gsc_window_lower_than_comparison", "automated_page_publication_allowed":False})
    if www_still_200 or (www_home_http in (301,308) and www_home_redirect_location not in ("https://empire-ai.co.uk/", "https://empire-ai.co.uk")):
        tasks.append({"owner":"website", "priority":"P1", "action":"REVIEW_WWW_CANONICAL_REDIRECT_PARITY", "reason":"observed_www_response_not_verified_single_permanent_origin", "automated_redirect_change_allowed":False})
    if not roofing_held:
        tasks.append({"owner":"seo", "priority":"P0", "action":"RESTORE_BUYER_ROOFING_NOINDEX_HOLD", "reason":"buyer_pilot_landing_not_observed_in_expected_noindex_state", "production_traffic_authorized":False})
    for path in ("/industries/roofing", "/industries/solar", "/predictive-revenue"):
        if not index[path]["technical_indexability_signals_present"]:
            tasks.append({"owner":"seo", "priority":"P1", "action":"REVIEW_PILLAR_INDEXABILITY_AND_ORIGINAL_EVIDENCE", "path":path, "automatic_indexation_allowed":False})
    for path in ("/privacy", "/terms"):
        if index[path]["http"] == 200 and not index[path]["canonical_present"]:
            tasks.append({"owner":"website", "priority":"P2", "action":"REVIEW_PUBLISHED_LEGAL_PAGE_CANONICAL", "path":path, "automatic_legal_edit_allowed":False})
    tasks.append({"owner":"business_development", "priority":"P1", "action":"OBTAIN_SIGNED_PAYABLE_OUTBOUND_CPC_BUYER_TERMS", "reason":"research_programmes_not_signed_per_click_agreements", "outbound_authorized":False})
    tasks.append({"owner":"seo", "priority":"P1", "action":"CREATE_ONE_ORIGINAL_HIGH_INTENT_PILLAR_CONTENT_REVIEW", "reason":"human_evidence_quality_and_market_source_required_before_publish", "automatic_publish_allowed":False})
    return {
        "schema_version":SCHEMA,
        "site":"https://empire-ai.co.uk",
        "tenant":"empire-ai",
        "mode":"OBSERVE",
        "window":{"start":start.isoformat(),"end":end.isoformat()},
        "observed_gsc_sitewide":{"impressions":site["impressions"],"clicks":site["clicks"],"comparison_impressions":prior["impressions"],"comparison_clicks":prior["clicks"]},
        "search_clicks_are_payable_advertiser_clicks":False,
        "gsc_query_page_data_is_sitewide_complete":False,
        "owned_pages":checked,
        "technical_indexability_signal_count":technical,
        "www_host_redirect_to_canonical_verified":www_home_http in (301,308) and www_home_redirect_location in ("https://empire-ai.co.uk/", "https://empire-ai.co.uk"),
        "buyer_roofing_page_held_noindex":roofing_held,
        "research_programmes":[{**p,"accepted_click_payout_terms_verified":False,"activation_authorized":False} for p in RESEARCH_LANES],
        "monetization_models":{
            "PUBLISHER_PPC":{"status":"NO_VERIFIED_PAYABLE_CPC_BUYER","accepted_outbound_clicks":None,"click_payout_contract_verified":False,"idempotent_empiredb_click_writer_verified":False,"redirect_authorized":False},
            "PAY_PER_CALL":{"status":"HUMAN_INTEREST_BUYBOX_AND_TERMS_HOLD","buyer_capacity_verified":False,"phone_route_enabled":False},
            "PAY_PER_LEAD":{"status":"PROGRAMME_DISCOVERY_NOT_ENROLLED","accepted_leads_verified":None,"consumer_transfer_enabled":False},
            "DISPLAY_ADS":{"status":"OPTIONAL_NETWORK_NOT_APPROVED","ad_network_account_verified":False,"ad_slots_enabled":False},
            "PAID_SEARCH_ADS":{"status":"ZERO_BUDGET_DISABLED","account_spend_authorized":False,"daily_budget_authorized":False},
        },
        "next_actions":tasks,
        "compliance_requirements":["GSC_inbound_click_not_billable_CPC_event", "approved_country_and_buyer_terms", "first_party_traffic_source_verification", "explicit_affiliate_disclosure_and_rel_sponsored", "canonical_durable_click_event_and_buyer_acceptance", "consent_and_privacy_review", "attributable_buyer_settlement_before_revenue"],
        "paid_media_spend_authorized":False,
        "live_click_attribution_enabled":False,
        "live_referral_redirects_enabled":False,
        "live_buyers_authorized":False,
        "outbound_authorized":False,
        "production_publish_authorized":False,
        "revenue_recognition_authorized":False,
        "buyer_paid_click_revenue_verified":False,
        "confirmed_payable_click_count":None,
        "execution_authority":"none",
    }
