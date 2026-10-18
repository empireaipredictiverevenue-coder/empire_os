"""Aggregate *existing* SEO workstreams without inventing traffic or authority.

Four-surface live discovery, first-party GSC page-only, owner organic release
integrity, pre-existing legacy 404 triage, and the existing marketing_growth
multi-desk editorial research portfolio. This is a read-only evidence join,
NOT an autonomous agent, publisher, tracker or rank-estimation service.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

SCHEMA = "empire.search_growth.department_integration.v1"


class IntegrationEvidenceHeld(ValueError):
    pass


def _exact_nonnegative(value: Any, *, max_value: int = 1_000_000) -> int:
    if type(value) is not int or not 0 <= value <= max_value:
        raise IntegrationEvidenceHeld("UNTRUSTED_AGGREGATE_COUNT")
    return value


def reconcile_department(
    *,
    four: Mapping[str, Any],
    organic: Mapping[str, Any],
    growth: Mapping[str, Any],
    gsc: Mapping[str, Any],
    legacy: Mapping[str, Any],
    semantic: Mapping[str, Any],
) -> dict[str, Any]:
    """Accept only reviewed first-party/owner evidence; every gap stays visible."""
    if (not isinstance(four, Mapping) or four.get("schema")
            != "empire.discovery.four_surface_readonly.v1"
            or four.get("authority") != "OBSERVE"
            or four.get("production_mutation") is not False):
        raise IntegrationEvidenceHeld("FOUR_SURFACE_PROVENANCE_UNVERIFIED")
    seo, aeo, geo, a2a = (
        four.get("seo"), four.get("aeo"), four.get("geo"), four.get("a2a")
    )
    if not all(isinstance(x, Mapping) for x in (seo, aeo, geo, a2a)):
        raise IntegrationEvidenceHeld("FOUR_SURFACE_SHAPE_INVALID")
    pages = seo.get("pages")
    expected = {"/commercial", "/industries/roofing", "/aeo/roofing/DFW/"}
    if not isinstance(pages, Mapping) or set(pages) != expected:
        raise IntegrationEvidenceHeld("FOUR_SURFACE_PAGE_SCOPE_DRIFT")
    for page in pages.values():
        if (not isinstance(page, Mapping) or type(page.get("http")) not in {int, type(None)}
                or page.get("available") not in {True, False}):
            raise IntegrationEvidenceHeld("FOUR_SURFACE_PAGE_UNVERIFIED")
    if (not isinstance(organic, Mapping) or organic.get("schema_version")
            != "empire.organic_live_release_integrity.v1"
            or organic.get("mode") != "READ_ONLY"
            or organic.get("database_writes_performed_by_review") is not False
            or organic.get("outbound_sent_by_review") is not False
            or organic.get("payment_executed_by_review") is not False):
        raise IntegrationEvidenceHeld("ORGANIC_INTEGRITY_PROVENANCE_UNVERIFIED")
    if (not isinstance(growth, Mapping) or growth.get("schema_version")
            != "empire.marketing_growth.search_department.portfolio_review.v1"
            or growth.get("canonical_department") != "marketing_growth"
            or growth.get("operating_mode") != "OBSERVE"
            or growth.get("production_write") is not False
            or growth.get("outbound_or_publication_performed") is not False
            or growth.get("credentials_read") is not False
            or growth.get("external_requests") is not False
            or growth.get("budget_gbp") != 0
            or growth.get("campaigns_approved_to_launch") != 0):
        raise IntegrationEvidenceHeld("GROWTH_PORTFOLIO_PROVENANCE_UNVERIFIED")
    campaigns = growth.get("campaigns")
    campaigns_count = _exact_nonnegative(growth.get("campaign_count"), max_value=16)
    desks = _exact_nonnegative(growth.get("desk_count"), max_value=12)
    if (not isinstance(campaigns, list) or len(campaigns) != campaigns_count
            or not 7 <= desks <= 12 or campaigns_count < 1
            or any(not isinstance(x, Mapping)
                   or x.get("status") != "RESEARCH_ONLY" for x in campaigns)):
        raise IntegrationEvidenceHeld("UNAPPROVED_GROWTH_CAMPAIGN")
    if (not isinstance(gsc, Mapping) or gsc.get("schema_version")
            != "empire.search.first_party_gsc_page_review.v1"
            or gsc.get("source") != "google_search_console_page_dimension"
            or gsc.get("mode") != "OBSERVE"
            or gsc.get("page_only_aggregation_not_query_page") is not True
            or gsc.get("indexation_verified") is not False
            or gsc.get("commercial_conversion_verified") is not False
            or gsc.get("outbound_authorized") is not False
            or gsc.get("publishing_authorized") is not False):
        raise IntegrationEvidenceHeld("GSC_PAGE_DIMENSION_UNVERIFIED")
    if (not isinstance(legacy, Mapping) or legacy.get("schema_version")
            != "empire.organic_search.gsc_page_legacy_404_review.v1"
            or legacy.get("source") != "google_search_console_page_dimension_final"
            or legacy.get("mode") != "OBSERVE"
            or legacy.get("query_page_rows_joined_or_added") is not False
            or legacy.get("database_writes") is not False
            or legacy.get("redirect_authorized") is not False
            or legacy.get("publication_authorized") is not False):
        raise IntegrationEvidenceHeld("LEGACY_PAGE_REVIEW_UNVERIFIED")
    if (not isinstance(semantic, Mapping) or semantic.get("schema_version")
            != "live_semantic_site_quality_review.v1"
            or semantic.get("mode") != "OBSERVE"
            or semantic.get("source_type") != "read_only_public_html"
            or semantic.get("site_mutated") is not False
            or semantic.get("paid_api_requests") != 0
            or semantic.get("submission_executed") is not False
            or semantic.get("crm_receipt_verified") is not False
            or semantic.get("revenue_verified") is not False
            or semantic.get("observed_google_indexing") is not False
            or semantic.get("execution_authority") != "none"):
        raise IntegrationEvidenceHeld("SEMANTIC_SITE_SOURCE_UNVERIFIED")
    semantic_pages = _exact_nonnegative(semantic.get("assessed_public_pages"),max_value=4)
    intended_pages = _exact_nonnegative(semantic.get("intended_public_pages"),max_value=4)
    editorial = semantic.get("editorial_candidate_counts")
    if (not isinstance(editorial, Mapping) or len(editorial) > 20
            or any(not isinstance(k,str) or len(k)>120 for k in editorial)
            or not isinstance(semantic.get("read_errors"), list)
            or len(semantic["read_errors"]) > 4):
        raise IntegrationEvidenceHeld("SEMANTIC_SITE_COUNTS_UNTRUSTED")
    semantic_candidate_count = sum(_exact_nonnegative(v,max_value=100) for v in editorial.values())
    semantic_sites_ready = (semantic_pages == 4 and intended_pages == 4
        and not semantic["read_errors"]
        and semantic.get("page_to_static_commercial_form_path_observed") is True)
    if gsc.get("date_window") != legacy.get("window"):
        raise IntegrationEvidenceHeld("GSC_DATE_WINDOW_MISMATCH")
    gsc_count = _exact_nonnegative(gsc.get("returned_page_rows"), max_value=1000)
    legacy_count = _exact_nonnegative(legacy.get("returned_page_rows"), max_value=250)
    missing = _exact_nonnegative(legacy.get("missing_legacy_page_count"), max_value=250)
    missing_imp = _exact_nonnegative(legacy.get("missing_legacy_page_impressions"))
    missing_clicks = _exact_nonnegative(legacy.get("missing_legacy_page_clicks"))
    if (gsc_count != legacy_count or missing > legacy_count
            or missing_clicks > missing_imp):
        raise IntegrationEvidenceHeld("INCONSISTENT_PAGE_DIMENSION_SAMPLE")
    ready = (
        all(p.get("http") == 200 and p.get("available") is True for p in pages.values())
        and seo.get("sitemap_http") == 200
        and a2a.get("no_privileged_actions_exposed") is True
    )
    integrity = organic.get("status") == "LIVE_BYTES_VERIFIED"
    if organic.get("file_integrity_pass") is not integrity:
        raise IntegrationEvidenceHeld("ORGANIC_INTEGRITY_CONTRADICTION")
    source_owned = organic.get("canonical_source_commit_verified") is True
    release_registered = organic.get("live_campaign_release_verified") is True
    ai_proven = aeo.get("answer_engine_citation_verified") is True
    geo_proven = geo.get("external_ai_mentions_or_citations") is True
    blocks = []
    if not ready:
        blocks.append("OWNED_DISCOVERY_SURFACE_REVIEW_REQUIRED")
    if not integrity:
        blocks.append("ORGANIC_LIVE_ASSET_INTEGRITY_HOLD")
    if not source_owned:
        blocks.append("ORGANIC_RELEASE_SOURCE_COMMIT_NOT_VERIFIED")
    if not release_registered:
        blocks.append("INDUSTRY_CAMPAIGN_RELEASE_NOT_VERIFIED")
    if missing:
        blocks.append("HISTORIC_GSC_404_EDITORIAL_TRIAGE_PENDING")
    if not semantic_sites_ready:
        blocks.append("SEMANTIC_LIVE_PAGE_OR_COMMERCIAL_LINK_REVIEW_REQUIRED")
    if semantic_candidate_count:
        blocks.append("SEMANTIC_ORIGINAL_CONTENT_EDITORIAL_REVIEW_PENDING")
    if not ai_proven or not geo_proven:
        blocks.append("INDEPENDENT_AI_ANSWER_CITATION_EVIDENCE_MISSING")
    blocks += [
        "INDEPENDENT_SERP_RANKING_OBSERVATIONS_NOT_VERIFIED_BY_THIS_REVIEW",
        "ORGANIC_BUYER_ENQUIRY_AND_REALIZED_REVENUE_NOT_PROVEN",
        "EDITORIAL_RESEARCH_REQUIRES_OWNER_PUBLICATION_DECISION",
    ]
    return {
        "schema_version": SCHEMA,
        "status": "DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN",
        "mode": "OBSERVE",
        "canonical_department": "marketing_growth",
        "canonical_database": "EmpireDB PostgreSQL",
        "origin": "https://empire-ai.co.uk",
        "gsc_property": "sc-domain:empire-ai.co.uk",
        "gsc_final_page_window": gsc["date_window"],
        "gsc_returned_page_rows": gsc_count,
        "gsc_sitewide_traffic_or_indexing_verified": False,
        "gsc_query_and_page_totals_added": False,
        "legacy_missing_404_count_in_returned_page_sample": missing,
        "legacy_missing_404_impressions_in_returned_page_sample": missing_imp,
        "legacy_missing_404_clicks_in_returned_page_sample": missing_clicks,
        "owned_seo_aeo_a2a_discovery_http_verified": ready,
        "external_ai_answer_citation_verified": ai_proven,
        "external_geo_mentions_verified": geo_proven,
        "organic_live_assets_verified": integrity,
        "organic_source_committed_verified": source_owned,
        "live_campaign_measurement_release_verified": release_registered,
        "semantic_live_priority_pages_checked": semantic_pages,
        "semantic_owned_pages_commercial_route_verified": semantic_sites_ready,
        "semantic_editorial_review_candidates": semantic_candidate_count,
        "semantic_google_indexing_verified": False,
        "semantic_paid_api_requests": 0,
        "research_campaigns": campaigns_count,
        "growth_specialist_desks": desks,
        "campaigns_approved_to_launch": 0,
        "zero_spend_gbp": 0,
        "open_gates": blocks,
        "search_rankings_verified": False,
        "buyer_enquiries_verified": False,
        "realised_revenue_verified": False,
        "customer_records_accessed": False,
        "database_writes": False,
        "live_website_changed": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }


def run(*, start: date | None = None, end: date | None = None) -> dict[str, Any]:
    """One-shot reuse of independently reviewed readers and existing data."""
    from pathlib import Path
    import json
    from empire_os.search_intelligence.four_surface_discovery import run as discovery_run
    from scripts.review_organic_live_release_integrity_20261018 import review as integrity_run
    from scripts.review_search_growth_department_portfolio_20261016 import (
        MANIFEST, validate_and_prioritize,
    )
    from scripts.review_live_gsc_page_performance import build_live_priority_page_report
    from scripts.review_live_search_page_404_revenue_readonly import run as legacy_run
    from scripts.review_live_semantic_site_quality import build_live_site_quality_review

    end = end or date.today() - timedelta(days=2)
    start = start or end - timedelta(days=12)
    if end >= date.today() or start > end or (end-start).days > 30:
        raise IntegrationEvidenceHeld("UNAPPROVED_GSC_FINAL_DATE_WINDOW")
    if MANIFEST.is_symlink() or not MANIFEST.is_file() or MANIFEST.stat().st_size > 60_000:
        raise IntegrationEvidenceHeld("UNTRUSTED_GROWTH_PORTFOLIO_MANIFEST")
    growth = validate_and_prioritize(json.loads(MANIFEST.read_text("utf8")))
    page_report = build_live_priority_page_report(
        start_date=start.isoformat(),end_date=end.isoformat())
    legacy = legacy_run(start=start,end=end)
    if legacy.get("status") == "HELD":
        raise IntegrationEvidenceHeld("LIVE_LEGACY_PAGE_OBSERVER_HELD")
    return reconcile_department(
        four=discovery_run(), organic=integrity_run(), growth=growth,
        gsc=page_report, legacy=legacy,
        semantic=build_live_site_quality_review(),
    )
