"""SEO Director: reconcile *actual* site releases with bounded GSC evidence.

Pure read-only analytics. Relies on existing organic_revenue_baseline for all
Google Search Console aggregation/trust checks. Never mistakes search visits
for buyer enquiries, payable CPC events, appointments, or settled revenue.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "empire.search.publication_impact_review.v1"
PROPERTY = "sc-domain:empire-ai.co.uk"
RELEASE_DATE = date(2026, 10, 15)
ORIGIN = "https://empire-ai.co.uk"

PAGE_SET = (
    "/industries/roofing", "/industries/solar",
    "/commercial", "/predictive-revenue",
)
FIRST_RELEASE = {"industries/roofing.html", "industries/solar.html", "commercial.html", "predictive-revenue.html"}
SECOND_RELEASE = {"commercial.html", "predictive-revenue.html"}
METADATA_RELEASE = {"industries/roofing.html", "industries/solar.html"}
TAM_ANSWER_RELEASE = {"commercial.html"}
INDUSTRY_LINK_RELEASE = {
    "industries/solar.html", "industries/hvac.html",
    "industries/legal-mass-tort.html", "industries/roofing.html",
    "industries/property.html", "industries/private-equity.html",
}
EXPECTED_HEADINGS = {
    "/industries/roofing": "From a roofing search to a qualified commercial opportunity.",
    "/industries/solar": "Solar referrals only become revenue when the buyer accepts the outcome.",
    "/commercial": "Start with the business problem, not a product label",
    "/predictive-revenue": "What is predictive revenue intelligence?",
}


def _release(packet: Mapping[str, Any], *, expected: set[str]) -> dict[str, str]:
    if (not isinstance(packet, Mapping)
        or packet.get("schema_version") != "empire.public.four-page-seo-release.v1"
        or packet.get("release_state") != "FOUR_PAGES_RELEASED_LOOPBACK_VERIFIED"
        or packet.get("gateway_restart_performed") is not False
        or packet.get("paid_media_authorized") is not False
        or packet.get("buyer_outbound_authorized") is not False):
        raise ValueError("untrusted_scope_or_execution_in_release_receipt")
    pages = packet.get("pages")
    if not isinstance(pages, dict) or set(pages) != expected:
        raise ValueError("incorrect_reviewed_release_page_scope")
    hashes = {}
    for rel, entry in pages.items():
        if not isinstance(entry, Mapping):
            raise ValueError("malformed_publication_page_hash")
        h = entry.get("after_sha256")
        if not (isinstance(h, str) and len(h) == 64 and
                all(c in "0123456789abcdef" for c in h)):
            raise ValueError("invalid_publication_sha256")
        hashes[rel] = h
    return hashes


def review_publication_impact(*,
        baseline: Mapping[str, Any],
        observed_query_pages: Mapping[str, Any],
        earlier_release: Mapping[str, Any],
        latest_release: Mapping[str, Any],
        live_pages: Mapping[str, Mapping[str, Any]],
        buyer_capacity_status: str,
        www_status: int | None,
        metadata_release: Mapping[str, Any] | None = None,
        tam_answer_release: Mapping[str, Any] | None = None,
        industry_link_release: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if (not isinstance(baseline, Mapping) or
        baseline.get("schema_version") != "empire.search.owned_gsc_organic_review.v1"
        or baseline.get("tenant_id") != "empire-ai"
        or baseline.get("site_id") != "empire-ai.co.uk"
        or baseline.get("gsc_property") != PROPERTY
        or baseline.get("mode") != "OBSERVE"
        or baseline.get("measurement_status") != "GSC_DAILY_SITEWIDE_PLUS_QUERY_PAGE"
        or baseline.get("gsc_currently_available") is not True
        or baseline.get("production_mutation") is not False
        or baseline.get("direct_publishing_allowed") is not False):
        raise ValueError("untrusted_existing_owned_gsc_review")
    dates = baseline.get("window")
    if not isinstance(dates, Mapping):
        raise ValueError("invalid_gsc_dates")
    try:
        window_start = date.fromisoformat(dates["start"])
        window_end = date.fromisoformat(dates["end"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid_gsc_dates") from None
    if (window_start > window_end or
        (window_end-window_start).days != 28 or
        window_end < date(2026,10,13)):
        raise ValueError("gsc_window_not_comparable_to_publication")
    sitewide = baseline.get("sitewide_current")
    previous = baseline.get("sitewide_previous")
    current = baseline.get("current")
    if any(not isinstance(v,Mapping) for v in (sitewide,previous,current)):
        raise ValueError("verified_sitewide_and_visible_query_page_required")
    for value in (sitewide,previous):
        im=value.get("impressions");clicks=value.get("clicks")
        if type(im) is not int or type(clicks) is not int or not 0<=clicks<=im<=100_000_000:
            raise ValueError("impossible_owned_sitewide_gsc_count")
        if value.get("commercial_source_attribution_verified") is not False:
            raise ValueError("gsc_clicks_are_not_commercial_conversions")
    first = _release(earlier_release,expected=FIRST_RELEASE)
    second = _release(latest_release,expected=SECOND_RELEASE)
    final = {**first, **second}
    if metadata_release is not None:
        # A later search snippet-only release updates roofing/solar HTML hashes.
        # Only these exact original industry pages may overlay first-release
        # evidence, and every subsequent live page must match its receipt.
        final.update(_release(metadata_release, expected=METADATA_RELEASE))
    if tam_answer_release is not None:
        # Real historical TAM-interest query: preserve the 404 on the
        # unverified legacy route; the current Commercial page supplies
        # new, original guidance without inventing conversion evidence.
        final.update(_release(tam_answer_release, expected=TAM_ANSWER_RELEASE))
    if industry_link_release is not None:
        # Only a six-page, independently loopback-verified atomic release
        # can advance the roofing/solar hash baseline. The other four pages
        # are protected by the exact six-target receipt and owner audit.
        if (industry_link_release.get("approved_page_count") != 6
            or industry_link_release.get("gateway_restart_required") is not False
            or industry_link_release.get("consumer_roofing_indexation_enabled") is not False):
            raise ValueError("untrusted_six_industry_link_release_scope")
        changed = _release(industry_link_release, expected=INDUSTRY_LINK_RELEASE)
        for rel in METADATA_RELEASE:
            prior = industry_link_release["pages"][rel].get("before_sha256")
            if prior != final[rel]:
                raise ValueError("industry_link_release_previous_hash_chain_broken")
            final[rel] = changed[rel]
    if not isinstance(live_pages,Mapping) or set(live_pages)!=set(PAGE_SET):
        raise ValueError("all_four_owned_pages_live_proof_required")
    for path in PAGE_SET:
        page=live_pages[path]
        if not isinstance(page,Mapping):
            raise ValueError("invalid_live_page_evidence")
        expected_sha=final[path.lstrip("/")+".html"]
        if (page.get("http") != 200 or
            page.get("sha256") != expected_sha or
            page.get("canonical") != ORIGIN+path or
            page.get("h1_count") != 1 or
            page.get("expected_buyer_heading_visible") is not True or
            page.get("approved_internal_business_link_present") is not True or
            page.get("noindex") is not False):
            raise ValueError("published_page_not_current_verified_release:"+path)
        if path in ("/commercial","/predictive-revenue") and (
            page.get("required_consent_checkbox") is not True
            or page.get("privacy_link_inside_form") is not True):
            raise ValueError("consented_founder_form_regression:"+path)
    if (not isinstance(observed_query_pages,Mapping)
        or observed_query_pages.get("available") is not True
        or observed_query_pages.get("source") != "google_search_console"
        or observed_query_pages.get("site_url") != PROPERTY):
        raise ValueError("untrusted_gsc_page_dimensions")
    rows = observed_query_pages.get("items")
    if (not isinstance(rows,list) or len(rows)>=1000
        or observed_query_pages.get("count")!=len(rows)):
        raise ValueError("unbounded_or_truncated_query_page_dimensions")
    # Existing first-party review validates URLs, query-row uniqueness,
    # counts and date windows. Match those counts before dropping query text.
    if sum(r.get("impressions",0) for r in rows)!=current.get("impressions") or (
        sum(r.get("clicks",0) for r in rows)!=current.get("clicks")):
        raise ValueError("gsc_query_page_receipt_not_matching_review")
    tracked = {path:{"visible_query_page_impressions":0,
                     "visible_query_page_clicks":0,
                     "complete_page_performance_known":False,
                     "payable_advertiser_clicks_verified":False,
                     "commercial_enquiries_verified":None,
                     "google_indexation_independently_verified":False}
               for path in PAGE_SET}
    for item in rows:
        keys=item.get("keys")
        if not isinstance(keys,list) or len(keys)!=2:
            raise ValueError("malformed_gsc_query_page_row")
        u=urlsplit(keys[1])
        if u.scheme not in ("https","http") or u.hostname not in ("www.empire-ai.co.uk","empire-ai.co.uk"):
            raise ValueError("external_gsc_page_url")
        path=u.path.rstrip("/") or "/"
        if path in tracked:
            im=item.get("impressions");clk=item.get("clicks")
            if type(im) is not int or type(clk) is not int or not 0<=clk<=im:
                raise ValueError("malformed_page_metric")
            tracked[path]["visible_query_page_impressions"]+=im
            tracked[path]["visible_query_page_clicks"]+=clk
    if buyer_capacity_status not in {
        "NO_VERIFIED_COMMERCIAL_CAPACITY", "VERIFIED_COMMERCIAL_CAPACITY",
        "UNKNOWN_NOT_VERIFIED",
    }:
        raise ValueError("invalid_buyer_capacity_evidence")
    if www_status is not None and (type(www_status) is not int or not 100<=www_status<=599):
        raise ValueError("unverified_www_http")
    eligible_days = max(0,(window_end-RELEASE_DATE).days)
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":("PRE_PUBLICATION_SEARCH_BASELINE_ONLY"
                  if eligible_days==0 else "POST_PUBLICATION_MEASUREMENT_OBSERVED_CAUSALITY_UNKNOWN"),
        "property":PROPERTY,"release_date":RELEASE_DATE.isoformat(),
        "gsc_window":{"start":window_start.isoformat(),"end":window_end.isoformat()},
        "gsc_sitewide":{"impressions":sitewide["impressions"],
                        "clicks":sitewide["clicks"],
                        "previous_impressions":previous["impressions"],
                        "previous_clicks":previous["clicks"],
                        "visible_query_page_impressions":current["impressions"],
                        "visible_query_page_clicks":current["clicks"],
                        "query_page_data_complete":False},
        "post_release_gsc_days_in_window_max":eligible_days,
        "post_release_gsc_outcome_attributable_to_site_change":False,
        "seo_pages_verified_public":4,
        "buyer_intent_search_metadata_release_verified":metadata_release is not None,
        "original_tam_buyer_explainer_release_verified":tam_answer_release is not None,
        "six_industry_editorial_link_release_verified":industry_link_release is not None,
        "page_evidence":tracked,
        "www_host_redirect_review_needed":www_status==200,
        "buyer_capacity_status":buyer_capacity_status,
        "accepted_click_count":None,"paid_cpc_revenue":None,
        "actual_founder_enquiries_attributed_to_seo":None,
        "commercial_conversion_tracking_independently_verified":False,
        "publisher_pay_per_click_live":False,"paid_media_spend_authorized":False,
        "buyer_outbound_authorized":False,"database_writes":False,
        "production_site_modified":False,"new_scheduler_created":False,
        "next_actions":[
            "MEASURE_FOUR_PAGE_GSC_AFTER_PROCESSING_LAG",
            "VERIFY_GENUINE_CONSENTED_ENQUIRY_LINEAGE_WITH_EXISTING_FOUNDER_CRM",
            "REVIEW_WWW_CANONICAL_REDIRECT_WITH_ACTIVE_GATEWAY_OWNER",
            "VERIFY_SIGNED_BUYER_TERMS_BEFORE_PPC_OR_CALL_MONETIZATION",
        ],
        "execution_authority":"none",
    }
