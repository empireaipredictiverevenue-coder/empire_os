"""Read-only custody join for EXISTING SEO backlink and editorial evidence.

A historical Common Crawl domain relationship, internal link, researched
publisher and caller-submitted live backlink observation remain distinct.
This module is not a crawler, ranking provider, outreach system or database.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .backlinks import BacklinkObservation, analyse_backlink_graph


class AuthorityEvidenceHeld(ValueError):
    pass


def reconcile_earned_authority(
    *,
    historical_review: Mapping[str, Any],
    editorial_queue: Mapping[str, Any],
    live_anchor_observations: Sequence[BacklinkObservation],
    canonical_stored_backlink_count: int | None,
) -> dict[str, Any]:
    if (not isinstance(historical_review, Mapping)
            or historical_review.get("schema_version")
                != "empire.cc.graph.referrer_review_queue.v1"
            or historical_review.get("source") != "commoncrawl_2026_domain_webgraph"
            or historical_review.get("mode") != "OBSERVE"
            or historical_review.get("no_page_level_backlink_proof") is not True
            or historical_review.get("manual_review_required_for_all") is not True
            or historical_review.get("empiredb_writes") is not False):
        raise AuthorityEvidenceHeld("EXACT_HISTORICAL_ARCHIVE_EVIDENCE_REQUIRED")
    hist_domains = historical_review.get("distinct_historical_source_domains")
    hist_cross = historical_review.get("cross_target_source_domain_count")
    historical_queue = historical_review.get("manual_review_queue")
    if (type(hist_domains) is not int or not 0 <= hist_domains <= 100_000
            or type(hist_cross) is not int or not 0 <= hist_cross <= hist_domains
            or not isinstance(historical_queue, list)
            or len(historical_queue) != hist_domains):
        raise AuthorityEvidenceHeld("HISTORICAL_GRAPH_COUNTS_INCONSISTENT")

    if (not isinstance(editorial_queue, Mapping)
            or editorial_queue.get("schema_version")
                != "empire.marketing.earned_editorial_opportunities.v1"
            or editorial_queue.get("mode") != "OBSERVE"
            or editorial_queue.get("outbound_authorized") is not False
            or editorial_queue.get("publication_authorized") is not False
            or editorial_queue.get("site_modified") is not False):
        raise AuthorityEvidenceHeld("EXISTING_EDITORIAL_RESEARCH_CUSTODY_REQUIRED")
    publishers = editorial_queue.get("publishers")
    if (not isinstance(publishers, list) or len(publishers) > 30
            or any(not isinstance(p, Mapping) for p in publishers)):
        raise AuthorityEvidenceHeld("BOUNDED_PUBLISHER_REVIEW_REQUIRED")
    prior_external = editorial_queue.get("existing_independently_verified_backlinks")
    newly_earned = editorial_queue.get("new_external_links_earned_this_run")
    first_party = editorial_queue.get("verified_live_first_party_link_additions")
    if any(type(v) is not int or v < 0 for v in (
            prior_external, newly_earned, first_party)):
        raise AuthorityEvidenceHeld("EDITORIAL_COUNTS_UNTRUSTED")

    if (not isinstance(live_anchor_observations, (list, tuple))
            or len(live_anchor_observations) > 30
            or any(type(x) is not BacklinkObservation
                   for x in live_anchor_observations)):
        raise AuthorityEvidenceHeld("BOUNDED_EXISTING_BACKLINK_OBSERVATIONS_REQUIRED")
    # Original graph analyzer validates each source/target URL and provenance.
    analysis = analyse_backlink_graph(
        tuple(live_anchor_observations), empire_domains=("empire-ai.co.uk",)
    )
    if (canonical_stored_backlink_count is not None and
            (type(canonical_stored_backlink_count) is not int
             or not 0 <= canonical_stored_backlink_count <= 100_000)):
        raise AuthorityEvidenceHeld("CANONICAL_BACKLINK_COUNT_INVALID")

    return {
        "schema_version": "empire.search.earned_authority_reconciliation.v1",
        "owner": "existing_search_intelligence_and_editorial_exchange",
        "mode": "OBSERVE",
        "historical_commoncrawl_distinct_domain_candidates": hist_domains,
        "historical_cross_target_domain_candidates": hist_cross,
        "historical_domain_graph_is_page_backlink_proof": False,
        "publisher_research_records": len(publishers),
        "publisher_research_is_accepted_placement": False,
        "original_editorial_receipt_external_backlinks": prior_external,
        "new_external_links_earned_in_editorial_receipt": newly_earned,
        "original_editorial_receipt_internal_link_additions": first_party,
        "first_party_links_are_external_backlinks": False,
        "current_caller_observed_external_links": analysis.observed_backlinks,
        "current_caller_observed_referring_domains": analysis.referring_domains,
        "current_observed_anchor_report_is_canonical_proof": False,
        "canonical_stored_backlink_count": canonical_stored_backlink_count,
        "reconciliation_needed": (
            analysis.observed_backlinks > 0 and
            canonical_stored_backlink_count is not None and
            canonical_stored_backlink_count < analysis.observed_backlinks
        ),
        "authority_score": None,
        "ranking_lift_verified": False,
        "referral_visits_verified": False,
        "qualified_buyers_verified": False,
        "revenue_verified": False,
        "next_owner_action": (
            "VERIFY_AND_ADMIT_EXACT_HTTPS_ANCHOR_RECEIPT_IN_EXISTING_EMPIREDB_BACKLINK_OWNER"
            if (analysis.observed_backlinks > 0 and
                canonical_stored_backlink_count is not None and
                canonical_stored_backlink_count < analysis.observed_backlinks)
            else "REVIEW_EDITORIAL_RESEARCH_AND_CURRENT_LINK_EVIDENCE"
        ),
        "automatic_link_exchange_authorized": False,
        "paid_placements_authorized": False,
        "publication_authorized": False,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }
