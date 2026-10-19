"""One owned, no-write intelligence chain: Scrapling -> identity -> Waterfall -> Sniper.

All evidence is checked against existing contracts. The final item is ONLY a
candidate review packet for EmpireDB task queue; caller cannot promote it or
send mail. Independently verified receipt strings are declarations supplied
by an operator and require separate verification by the canonical owner.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from empire_os.lead_sniper_repository import review_b2b_sniper_candidate
from empire_os.scrapling_identity_review import review_scrapling_canonical_identity
from empire_os.scrapling_waterfall_provider import build_reviewed_scrapling_waterfall
from empire_os.waterfall_source_bridge import EvidenceReview, MAX_REVIEW_RECORDS

SCHEMA = "empire.scrapling_sniper_handoff.v1"


def _hold(reasons: list[str], *, index: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OFFLINE_B2B_REVIEW_ONLY",
        "state": "HOLD",
        "source_record_index": index,
        "reasons": sorted(set(reasons)),
        "review_task_proposal": None,
        "canonical_business_link_verified": False,
        "confirmed_buyer_intent": False,
        "contact_promotion_authorized": False,
        "live_sniper_queue_authorized": False,
        "outbound_authorized": False,
        "canonical_database_writes": False,
        "execution_authority": "none",
    }


def build_scrapling_sniper_review_handoff(
    *,
    source_report: Mapping[str, Any],
    review: EvidenceReview,
    canonical_rows: Sequence[Mapping[str, Any]] | None,
    canonical_snapshot_complete: bool,
    canonical_snapshot_ref: str,
    independent_canonical_id: str,
    canonical_identity_receipt_ref: str,
    source_rights_receipt_ref: str,
    territory_receipt_ref: str,
    company_site_html: str,
    company_page_url: str,
    record_index: int = 0,
    research_score: float = 0.6,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Conservative single-firm preview, no DB writes or provider HTTP calls.

    The identity match is a proposal. A separately supplied exact canonical
    ID and business identity receipt are required before proposing a B2B
    sniper review; their presence does not independently prove legitimacy.
    """
    if type(record_index) is not int or not 0 <= record_index < MAX_REVIEW_RECORDS:
        raise ValueError("bounded record index required")
    if not isinstance(source_report, Mapping) or not isinstance(review, EvidenceReview):
        raise TypeError("invalid source report or review")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone aware")

    # Reuses the existing canonical review's record and source contract checks.
    canonical = review_scrapling_canonical_identity(
        report=source_report,
        review=review,
        canonical_rows=canonical_rows,
        canonical_snapshot_complete=canonical_snapshot_complete,
        canonical_snapshot_ref=canonical_snapshot_ref,
        now=current,
    )
    decision_rows = canonical.get("observation_decisions") or []
    if record_index >= len(decision_rows):
        return _hold(["source_record_missing"], index=record_index)
    decision = decision_rows[record_index]
    if decision["state"] != "POTENTIAL_EXISTING_REVIEW":
        return _hold(
            ["canonical_identity_not_consistently_matched", *decision["reasons"]],
            index=record_index,
        )
    if (not isinstance(independent_canonical_id, str)
            or independent_canonical_id not in decision["possible_canonical_ids"]):
        return _hold(["independently_confirmed_canonical_id_mismatch"], index=record_index)

    if not all(isinstance(x, str) and 8 <= len(x) <= 250 and x.strip() == x
               for x in (
                   canonical_identity_receipt_ref, source_rights_receipt_ref,
                   territory_receipt_ref,
               )):
        return _hold(["independent_identity_rights_territory_receipts_missing"],
                     index=record_index)

    try:
        # Factory uses OUR Waterfall, enhanced with bounded static Scrapling
        # website contact observation. enrich() is explicitly disabled.
        flow, plan = build_reviewed_scrapling_waterfall(
            source_report=dict(source_report),
            review=review,
            html=company_site_html,
            website_page_url=company_page_url,
            observed_at=current,
            record_index=record_index,
        )
    except (ValueError, RuntimeError, TypeError) as exc:
        return _hold(
            ["independent_verified_company_website_required", type(exc).__name__],
            index=record_index,
        )
    observation = flow.observe_scrapling_only({
        "company": plan["observed_business"],
    })
    if not observation["observed"]:
        return _hold(["company_website_contact_unobserved"], index=record_index)

    lead = {
        "business_name": plan["observed_business"],
        "source": plan["observed_source_id"],
        "registered_source_id": plan["observed_source_id"],
        "registered_source_evidence_url": source_report.get("source_url"),
        "canonical_business_identity_ref": (
            "canonical:" + independent_canonical_id + ":" +
            canonical_identity_receipt_ref
        ),
        "source_rights_receipt_ref": source_rights_receipt_ref,
        "source_territory_ref": territory_receipt_ref,
        "territory_code": review.jurisdiction,
        "jurisdiction_policy_ref": review.jurisdiction_policy_ref,
        "entity_kind": "company",
        "contains_consumer_claimant_or_patient_data": False,
        "outreach_authorized": False,
        "details": {
            "url": company_page_url,
            "observed_at": source_report.get("observed_at"),
        },
    }
    proposal = review_b2b_sniper_candidate(
        lead, review.vertical, research_score, now=current
    )
    if proposal["decision"] != "B2B_REVIEW_PROPOSAL":
        return _hold(proposal["reasons"], index=record_index)

    return {
        "schema_version": SCHEMA,
        "mode": "OFFLINE_B2B_REVIEW_ONLY",
        "state": "SNIPER_REVIEW_PACKET_PREPARED",
        "source_record_index": record_index,
        "source_id": plan["observed_source_id"],
        "source_document_sha256": plan["observed_document_sha256"],
        "identity_snapshot_ref": canonical_snapshot_ref,
        "identity_match_state": decision["state"],
        "legacy_sniper_endpoint": "empire.lead_sniper_canonical_review.v1",
        "waterfall_provider_order": [provider.name for provider in flow.providers],
        "waterfall_existing_gate_passed": observation["existing_gate_would_pass"],
        "website_business_contact_observed": observation["observed"],
        "review_task_proposal": proposal,
        "canonical_business_link_verified": False,
        "confirmed_buyer_intent": False,
        "contact_promotion_authorized": False,
        "live_sniper_queue_authorized": False,
        "outbound_authorized": False,
        "canonical_database_writes": False,
        "execution_authority": "none",
        "note": "All receipts are independently reviewable assertions, not permissions for launch",
    }
