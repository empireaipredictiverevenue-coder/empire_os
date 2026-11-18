"""B2B buyer-job discovery for the ORIGINAL Data Brokerage market-intelligence report.

Candidates originate from public indexed job ads, NOT connected buyer emails,
accepted RFPs or a personal-contact scraper. Their indexed content has NOT
been independently fetched from the job provider. Nothing here authorizes
applying, messaging, billing, client delivery or putting people into CRM.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from hashlib import sha256
from collections.abc import Mapping
from typing import Any
import json
import re

from empire_os.data_brokerage_prospect_queue import build_brokerage_prospect_queue, validate_prospect_queue
from empire_os.data_brokerage_buyer_fit import (
    qualify_existing_agency_report, validate_agency_fit_receipt,
    _json_source, SAMPLE, QUALIFIED,
)

SCHEMA = "empire.data_brokerage.public_targeted_buyer_scope.v1"
RELATIONSHIPS = Path("runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
DATE_OBSERVED = datetime(2026, 11, 15, 20, 55, tzinfo=timezone.utc)
SHA = re.compile(r"[a-f0-9]{64}\Z")
# The link addresses are public source identifiers. Text fields are narrow
# paraphrases of search-indexed advertisement evidence, not entire job texts.
PUBLIC_BRIEFS = (
    {
        "id": "us_pay_per_call_geo",
        "source": "https://www.upwork.com/freelance-jobs/apply/Google-Ads-Pay-Per-Call-Expert-Needed-Proven-Positive-ROI-Landing-Page-Development_~022121311045134120896/",
        "buyer_identity": None, "buyer_domain": None,
        "market_requested": "US_HOME_SERVICES",
        "buyer_job": "Profitable Google Ads pay-per-call campaigns with geography, niche and competitor research",
        "partial_research_need": "First-party evidence about roofing, HVAC and restoration publisher networks and programme language",
        "required_unproven": (
            "buyer-specified city/ZIP competitor and CPC checks",
            "verified qualified-call economics and buyer payout inputs",
            "demonstrated profitable Google Ads call campaigns and campaign operation",
        ),
        "verticals": ("roofing", "hvac", "restoration", "home_services"),
        "research_role": "PARTIAL_RESEARCH_COMPONENT_ONLY",
        "full_contract_fit": "NOT_VERIFIED",
    },
    {
        "id": "india_fintech_demat",
        "source": "https://www.upwork.com/freelance-jobs/apply/Fintech-Affiliate-Marketing-Specialist-Needed-for-Demat-Account-Campaigns_~022119067515397303429/",
        "buyer_identity": None, "buyer_domain": None,
        "market_requested": "INDIA_FINTECH_DEMAT",
        "buyer_job": "Research Indian fintech affiliate networks and publishers, then develop and run compliant CPA acquisition strategy",
        "partial_research_need": "Existing public publisher-programme categories only, not India fintech publisher identities",
        "required_unproven": (
            "Indian demat account advertiser programme and licensing evidence",
            "India-specific verified publisher landscape",
            "approved campaign management, tracking and regulatory compliance",
        ),
        "verticals": ("fintech", "finance"),
        "research_role": "SECTOR_AND_GEOGRAPHY_NOT_ESTABLISHED",
        "full_contract_fit": "NOT_VERIFIED",
    },
    {
        "id": "prints_of_love_etsy",
        "source": "https://www.upwork.com/freelance-jobs/apply/Affiliate-Outreach-Partner-Activation-Specialist-Ecommerce_~022098145569386806637/",
        "buyer_identity": "Prints of Love",
        "buyer_domain": "printsoflove.com",
        "market_requested": "US_ETSY_DESIGN_CREATOR_PARTNERS",
        "buyer_job": "Recruit, contact and activate Etsy designers and publisher partners with verified referrals",
        "partial_research_need": "Original research process can classify programme disclosures but not prove designer-publisher partner delivery",
        "required_unproven": (
            "target-specific Etsy creator audience discovery and qualification",
            "verified partner introductions, conversions and referral placements",
            "client authorisation to recruit or message publishers",
        ),
        "verticals": ("etsy", "design", "creator"),
        "research_role": "RECRUITMENT_AND_ACTIVATION_NOT_DESK_REPORT",
        "full_contract_fit": "NOT_VERIFIED",
    },
    {
        "id": "cpa_publisher_recruitment",
        "source": "https://www.upwork.com/freelance-jobs/apply/Affiliate-Publisher-Recruiter-CPA-CPS-Performance-Marketing_~022110823692162499925/",
        "buyer_identity": None, "buyer_domain": None,
        "market_requested": "CONSUMER_DTC_SKINCARE",
        "buyer_job": "Identify, contact, qualify and activate CPA/CPS affiliate publishers for DTC skincare",
        "partial_research_need": "Public programme roles can be mapped but no qualified publisher-traffic capability is verified",
        "required_unproven": (
            "skincare-vertical publisher identity and traffic-quality verification",
            "demonstrated successful active affiliate introductions",
            "buyer-specific outreach and approved onboarding terms",
        ),
        "verticals": ("skincare", "beauty", "ecommerce"),
        "research_role": "ACTIVE_PUBLISHER_RECRUITMENT_NOT_MARKET_REPORT",
        "full_contract_fit": "NOT_VERIFIED",
    },
)
assert len({x["source"] for x in PUBLIC_BRIEFS}) == len(PUBLIC_BRIEFS)


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 65:
        return None
    try:
        v = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return v.astimezone(timezone.utc) if v.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _known_relationship_domains(root: Path, *, now: datetime) -> tuple[set[str], bool]:
    path = root / RELATIONSHIPS
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 2_000_000:
            return set(), False
        src = json.loads(path.read_text("utf-8"))
        if (not isinstance(src, dict)
                or src.get("schema_version") != "empire.commercial_relationship_registry.v1"
                or src.get("mode") != "OBSERVE"
                or src.get("outbound_authorized") is not False
                or src.get("execution_authority") not in ("NONE", "none")
                or not isinstance(src.get("relationships"), list)
                or len(src["relationships"]) > 2000
                or _utc(src.get("generated_at")) is None
                or not timedelta(0) <= now - _utc(src["generated_at"]) <= timedelta(days=7)):
            return set(), False
        known = set()
        for item in src["relationships"]:
            if not isinstance(item, Mapping):
                continue
            identifiers = [item.get("company"), *(item.get("identity_domains") or [])]
            for value in identifiers:
                if isinstance(value, str) and re.fullmatch(r"[a-z0-9.-]{5,250}", value.casefold()):
                    known.add(value.casefold())
        for row in src.get("founder_reported_external_contact_queue", [])[:120]:
            if isinstance(row, Mapping) and isinstance(row.get("domain"), str):
                known.add(row["domain"].casefold())
        return known, True
    except (OSError, ValueError, TypeError, UnicodeError):
        return set(), False


def assess_targeted_buyer_demand(root: Path, *, now: datetime) -> dict[str, Any]:
    if now.utcoffset() is None:
        raise ValueError("TARGETED_BROKERAGE_BUYER_NEEDS_TZ")
    now = now.astimezone(timezone.utc)
    original = qualify_existing_agency_report(root, now=now)
    original_valid = (validate_agency_fit_receipt(original)
                      and original.get("status") == "ORIGINAL_RESEARCH_CONFIRMED_NO_PAID_BUYER")
    reference_fresh = timedelta(0) <= now - DATE_OBSERVED <= timedelta(days=7)
    relationship_domains, relationship_snapshot_valid = _known_relationship_domains(root, now=now)
    # Keep the private source receipt bounded; count the full cohort, retain
    # the top 15 evidence-linked organizations for founder review.
    research_prospects = build_brokerage_prospect_queue(root, now=now, limit=15)
    # Derive a specific, traceable desk-research subset rather than treating
    # 430 cross-industry domain hypotheses as proven buyer-relevant evidence.
    home_service_source_examples: list[dict[str, Any]] = []
    if original_valid:
        sample = _json_source(root, SAMPLE, maximum=110_000)
        report = _json_source(root, QUALIFIED, maximum=1_500_000)
        if (sample is not None and report is not None
                and sample[1] == original["source_report_sha256"]
                and report[1] == original["qualified_domain_source_sha256"]):
            by_domain = {r.get("domain"): r for r in report[0].get("records", [])
                         if isinstance(r, Mapping)}
            relevant = {"roofing", "hvac", "restoration", "home_services"}
            for case in sample[0].get("case_studies", [])[:5]:
                if not isinstance(case, Mapping):
                    continue
                domain = case.get("domain")
                source = by_domain.get(domain)
                if not isinstance(source, Mapping):
                    continue
                sectors = set(source.get("site_vertical_evidence") or ())
                obs = _utc(case.get("first_party_observed_utc"))
                if (not sectors.intersection(relevant)
                        or case.get("website_signal_categories", {}).get("publisher_program") is not True
                        or obs is None or not timedelta(0) <= now - obs <= timedelta(days=7)):
                    continue
                home_service_source_examples.append({
                    "public_domain": domain,
                    "first_party_programme_page": case.get("observed_first_party_url"),
                    "original_site_observed_at": obs.isoformat(),
                    "observed_sector_keywords_not_confirmed_product_verticals": sorted(sectors.intersection(relevant)),
                    "programme_language_observed_not_affiliate_contract": True,
                    "advertiser_buying_activity_independently_verified": False,
                    "buyer_coverage_or_current_payout_verified": False,
                })
    # These are source-index reports, never direct client confirmations.
    rows = []
    for entry in PUBLIC_BRIEFS:
        matched = (entry["id"] == "us_pay_per_call_geo" and original_valid
                   and reference_fresh and len(home_service_source_examples) >= 1)
        scope = ("RESEARCH_COMPONENT_HAS_REAL_SOURCE_SAMPLES_NEEDS_NEW_BUYER_BRIEF"
                 if matched else
                 "DISCOVERY_HOLD_SOURCE_EXPIRED" if not reference_fresh else
                 "NO_VALIDATED_DELIVERABLE_MATCH")
        named_domain = entry["buyer_domain"]
        relationship_status = (
            "UNLINKED_ANONYMOUS_PUBLIC_ADVERT"
            if not named_domain else
            "EXISTING_RELATIONSHIP_REVIEW_REQUIRED"
            if named_domain in relationship_domains else
            "NO_MATCH_IN_NONCANONICAL_RELATIONSHIP_REGISTRY"
            if relationship_snapshot_valid else
            "RELATIONSHIP_REGISTRY_UNAVAILABLE"
        )
        rows.append({
            "research_ref": entry["id"],
            "source_url": entry["source"],
            "source_evidence_level": "PUBLIC_SEARCH_INDEX_SNIPPET_NOT_PLATFORM_LIVE_FETCH",
            "buyer_organisation_as_advertised": entry["buyer_identity"],
            "buyer_legal_identity_independently_verified": False,
            "buyer_requested_market": entry["market_requested"],
            "public_job_summary_paraphrase": entry["buyer_job"],
            "specific_research_component": entry["partial_research_need"],
            "unproven_full_engagement_requirements": list(entry["required_unproven"]),
            "research_scope_state": scope,
            "original_report_evidence_overlap": bool(matched),
            "source_linked_home_service_programme_examples": (home_service_source_examples[:5] if matched else []),
            "examples_are_not_verified_US_market_or_buyer_coverage": True,
            "relationship_review": relationship_status,
            "canonical_crm_suppression_complete": False,
            "advert_still_accepting_applications_verified": False,
            "external_requirement_verified_as_direct_employer_brief": False,
            "full_engagement_fulfilment_verified": False,
            "standalone_research_purchase_request_verified": False,
            "research_item_is_not_a_genuine_customer_order": True,
            "payout_or_fee_terms_for_research_verified": False,
            "recommended_next": (
                "RECHECK_JOB_WITH_PROVIDER_THEN_BUYER_CONFIRM_STANDALONE_SCOPE"
                if matched else
                "RESEARCH_ONLY_HOLD_NO_OUTREACH"
            ),
            "contact_or_application_authorized": False,
        })
    return {
        "schema_version": SCHEMA, "status": "TARGETED_PUBLIC_BUYER_SCOPE_REVIEW_ONLY",
        "research_observed_at": DATE_OBSERVED.isoformat(), "evaluated_at": now.isoformat(),
        "discovery_source": "BOUNDED_WEB_SEARCH_OF_PUBLIC_JOB_ADVERTS",
        "index_content_is_not_independent_live_post_verification": True,
        "original_agency_report_verified": original_valid,
        "original_source_report_sha256": original.get("source_report_sha256") if original_valid else None,
        "original_company_relationship_snapshot_checked": relationship_snapshot_valid,
        "full_job_contracts_qualified": 0,
        "standalone_market_research_buyer_order_count_verified": 0,
        "discovery_items_count": len(rows),
        "records": rows,
        "source_backed_research_prospect_queue": research_prospects,
        "research_prospects_found": research_prospects["total_research_prospects"],
        "price_offered_or_accepted": False,
        "buyer_emails_or_contact_data_captured": False,
        "outreach_or_application_submitted": False,
        "crm_writes": False,
        "sales_revenue_verified": False,
        "customer_data_delivery_authorized": False,
        "execution_authority": "none",
    }


def validate_targeted_buyer_demand(report: Any) -> bool:
    if not isinstance(report, Mapping):
        return False
    if (report.get("schema_version") != SCHEMA
            or report.get("status") != "TARGETED_PUBLIC_BUYER_SCOPE_REVIEW_ONLY"
            or report.get("index_content_is_not_independent_live_post_verification") is not True
            or report.get("full_job_contracts_qualified") != 0
            or report.get("standalone_market_research_buyer_order_count_verified") != 0
            or report.get("price_offered_or_accepted") is not False
            or report.get("buyer_emails_or_contact_data_captured") is not False
            or report.get("outreach_or_application_submitted") is not False
            or report.get("crm_writes") is not False
            or report.get("sales_revenue_verified") is not False
            or report.get("customer_data_delivery_authorized") is not False
            or report.get("execution_authority") != "none"
            or _utc(report.get("research_observed_at")) != DATE_OBSERVED
            or _utc(report.get("evaluated_at")) is None):
        return False
    prospects = report.get("source_backed_research_prospect_queue")
    if prospects is not None:
        if not validate_prospect_queue(prospects):
            return False
        if report.get("research_prospects_found") != prospects["total_research_prospects"]:
            return False
    elif "research_prospects_found" in report:
        # Preserve existing integrity-checked receipts from before this
        # additive discovery correction; they are not new results.
        return False
    original = report.get("original_source_report_sha256")
    if original is not None and (not isinstance(original, str) or not SHA.fullmatch(original)):
        return False
    rows = report.get("records")
    if not isinstance(rows, list) or len(rows) != len(PUBLIC_BRIEFS):
        return False
    if report.get("discovery_items_count") != len(rows):
        return False
    for expected, row in zip(PUBLIC_BRIEFS, rows):
        if (not isinstance(row, Mapping)
                or row.get("research_ref") != expected["id"]
                or row.get("source_url") != expected["source"]
                or row.get("source_evidence_level") != "PUBLIC_SEARCH_INDEX_SNIPPET_NOT_PLATFORM_LIVE_FETCH"
                or row.get("buyer_organisation_as_advertised") != expected["buyer_identity"]
                or row.get("buyer_requested_market") != expected["market_requested"]
                or row.get("buyer_legal_identity_independently_verified") is not False
                or row.get("canonical_crm_suppression_complete") is not False
                or row.get("public_job_summary_paraphrase") != expected["buyer_job"]
                or row.get("specific_research_component") != expected["partial_research_need"]
                or row.get("unproven_full_engagement_requirements") != list(expected["required_unproven"])
                or row.get("relationship_review") not in (
                    "UNLINKED_ANONYMOUS_PUBLIC_ADVERT",
                    "EXISTING_RELATIONSHIP_REVIEW_REQUIRED",
                    "NO_MATCH_IN_NONCANONICAL_RELATIONSHIP_REGISTRY",
                    "RELATIONSHIP_REGISTRY_UNAVAILABLE",
                )
                or row.get("advert_still_accepting_applications_verified") is not False
                or row.get("external_requirement_verified_as_direct_employer_brief") is not False
                or row.get("full_engagement_fulfilment_verified") is not False
                or row.get("standalone_research_purchase_request_verified") is not False
                or row.get("research_item_is_not_a_genuine_customer_order") is not True
                or row.get("payout_or_fee_terms_for_research_verified") is not False
                or row.get("contact_or_application_authorized") is not False
                or row.get("examples_are_not_verified_US_market_or_buyer_coverage") is not True
                or not isinstance(row.get("source_linked_home_service_programme_examples"), list)
                or len(row["source_linked_home_service_programme_examples"]) > 5
                or (expected["id"] != "us_pay_per_call_geo"
                    and row["source_linked_home_service_programme_examples"] != [])
                or row.get("research_scope_state") not in (
                    "RESEARCH_COMPONENT_HAS_REAL_SOURCE_SAMPLES_NEEDS_NEW_BUYER_BRIEF",
                    "DISCOVERY_HOLD_SOURCE_EXPIRED", "NO_VALIDATED_DELIVERABLE_MATCH")
                or row.get("recommended_next") not in (
                    "RECHECK_JOB_WITH_PROVIDER_THEN_BUYER_CONFIRM_STANDALONE_SCOPE",
                    "RESEARCH_ONLY_HOLD_NO_OUTREACH")):
            return False
        if row.get("research_scope_state") == "RESEARCH_COMPONENT_HAS_REAL_SOURCE_SAMPLES_NEEDS_NEW_BUYER_BRIEF":
            if (expected["id"] != "us_pay_per_call_geo"
                    or report.get("original_agency_report_verified") is not True
                    or row.get("original_report_evidence_overlap") is not True):
                return False
    return True
