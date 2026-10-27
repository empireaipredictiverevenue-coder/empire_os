"""Per-page measurement ledger, disconnected until original approved release exists.

The existing weekly GSC observer proves *search clicks and impressions only* for
two original approved pages. The candidate factory cannot re-label those counts
as traffic or revenue from new microsites.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
import json

from empire_os.search_intelligence.weekly_two_page_outcomes import SITE_PAGES


def read_original_weekly_search_report(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256000:
        raise ValueError("SEO weekly source file unavailable")
    packet = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(packet, dict)
            or packet.get("schema_version") != "empire.search.weekly_two_page_outcome_observer.v1"
            or packet.get("status") != "READ_ONLY_WEEKLY_REPORT"
            or packet.get("source_property") != "sc-domain:empire-ai.co.uk"
            or packet.get("dimensions") != ["page"]
            or packet.get("execution_authority") != "NONE"
            or packet.get("website_mutations") is not False
            or packet.get("realised_revenue_verified") is not False
            or packet.get("qualified_buyer_enquiries_verified") is not False):
        raise ValueError("original weekly SEO report authority not verified")
    window = packet.get("current_window")
    if (not isinstance(window, Mapping) or not isinstance(window.get("pages"), list)
            or tuple(x.get("url") for x in window["pages"] if isinstance(x, dict)) != SITE_PAGES):
        raise ValueError("original measured page scope changed")
    return packet


def original_site_search_baseline(report: Mapping[str, Any] | None) -> dict[str, Any]:
    if report is None:
        return {
            "source_status": "ORIGINAL_SEO_WEEKLY_SOURCE_UNAVAILABLE",
            "baseline_pages": [],
            "new_microsite_measurement_proven": False,
        }
    if (report.get("schema_version") != "empire.search.weekly_two_page_outcome_observer.v1"
            or report.get("dimensions") != ["page"]
            or report.get("source_property") != "sc-domain:empire-ai.co.uk"):
        raise ValueError("wrong original source")
    window = report["current_window"]
    output = []
    if tuple(row.get("url") for row in window["pages"]) != SITE_PAGES:
        raise ValueError("unexpected original page set")
    for row in window["pages"]:
        state = row.get("status")
        measured = state in ("MEASURED_ZERO", "MEASURED_PAGE_METRICS")
        if measured and (type(row.get("impressions")) is not int
                         or type(row.get("clicks")) is not int
                         or row["impressions"] < row["clicks"] or row["clicks"] < 0
                         or not row.get("evidence_refs")):
            raise ValueError("SEO metrics lack original row evidence")
        output.append({
            "url": row["url"],
            "status": state,
            "impressions": row["impressions"] if measured else None,
            "search_clicks": row["clicks"] if measured else None,
            "source_evidence_refs": list(row.get("evidence_refs") or []),
            "website_sessions": None, "consented_enquiries": None,
            "buyer_accepted_events": None, "settled_revenue_minor": None,
            "is_microsite_factory_page": False,
        })
    return {
        "source_status": "ORIGINAL_TWO_PAGE_GSC_BASELINE_ONLY",
        "source_as_of": report.get("as_of"),
        "observed_window": [window.get("start_date"), window.get("end_date")],
        "baseline_pages": output,
        "new_microsite_measurement_proven": False,
    }


def build_microsite_outcome_register(
    queue: Mapping[str, Any], *,
    original_weekly_gsc: Mapping[str, Any] | None = None,
    trusted_approved_page_readback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Immutable candidate identity + future exact attribution joins.

    This implementation never accepts page-owner approval merely from user
    supplied booleans. Until the original release owner provides verifiable
    immutable readback, all candidate metrics remain missing.
    """
    if (not isinstance(queue, Mapping)
            or queue.get("schema_version") != "empire.microsite_ranked_production_research_queue.v4"
            or queue.get("execution_authority") != "none"
            or queue.get("publishable_count") != 0
            or queue.get("owner_publication_authorized") is not False
            or not isinstance(queue.get("rows"), list)):
        raise ValueError("original ranked queue required")
    if trusted_approved_page_readback is not None:
        # Original owned campaign release and industry extension do not support
        # newly minted factory identities. Do NOT accept arbitrary approvals.
        raise ValueError("original owner release adapter not yet verified for factory pages")
    rows = []
    for item in queue["rows"]:
        cid = item.get("candidate_id")
        if not isinstance(cid, str) or not cid.startswith("microsite_"):
            raise ValueError("malformed candidate identity")
        if item.get("production_slot_authorized") is not False or item.get("public_url") is not None:
            raise ValueError("untrusted candidate production state")
        rows.append({
            "candidate_id": cid,
            "research_rank": item["research_rank"],
            "keyword": item["keyword"],
            "area": item["area"],
            "measurement_state": "NOT_RELEASED_BY_ORIGINAL_SITE_OWNER",
            "public_url": None,
            "release_asset_digest": None,
            "canonical_campaign_id": None,
            "canonical_asset_id": None,
            "traffic": {
                "gsc_impressions": None,
                "gsc_clicks": None,
                "verified_website_sessions": None,
                "source_status": "NO_APPROVED_FACTORY_PAGE_OR_ORIGINAL_PAGE_METRICS",
            },
            "funnel": {
                "consented_enquiry_submissions": None,
                "qualified_enquiries": None,
                "buyer_accepted_enquiries": None,
                "fulfilled_events": None,
                "settled_revenue_minor": None,
                "settlement_currency": None,
                "attribution_join_verified": False,
            },
            "required_original_join": [
                "site_owner_immutable_asset_and_deployment_readback",
                "SEO_owner_source_page_and_window_receipt",
                "server_side_website_consent_and_first_party_campaign_id",
                "CRM_canonical_enquiry_identity_and_buyer_acceptance",
                "settlement_receipt_to_original_accepted_event",
            ],
        })
    return {
        "schema_version": "empire.microsite_page_outcomes.v4",
        "mode": "OBSERVE", "execution_authority": "none",
        "source_owner": "original_site_seo_and_canonical_commercial_systems",
        "factory_page_count": len(rows),
        "factory_pages_with_verified_sessions": 0,
        "factory_pages_with_verified_enquiries": 0,
        "factory_pages_with_verified_settlements": 0,
        "comparison_baseline": original_site_search_baseline(original_weekly_gsc),
        "pages": rows,
        "database_writes": False, "website_mutations": False,
        "payment_action": False, "outbound_sent": False,
    }
