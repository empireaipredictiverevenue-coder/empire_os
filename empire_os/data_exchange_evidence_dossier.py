"""Source-linked internal Construction Signals preview with OGL custody.

Produces bounded evidence a real buyer could evaluate AFTER independent
rights review. For now it is INTERNAL_ONLY, not a customer distribution.
This is source metadata, not a verified join, opportunity or prediction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_agi_bridge import _check_procurement
from empire_os.data_exchange_construction import build_construction_preview
from empire_os.data_exchange_history import build_construction_history

SCHEMA = "empire.data_exchange.construction_evidence_dossier.v1"
OGL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
MAX_SAMPLE = 8
PLANNING_RIGHTS = {
    "source_id": "gb_planning_data",
    "dataset": "brownfield-land",
    "dataset_uri": "https://www.planning.data.gov.uk/dataset/brownfield-land",
    "licence": "Open Government Licence v3.0",
    "licence_url": OGL,
    "required_attribution": "© Crown copyright and database right 2026",
    "publisher": "UK Planning Data",
    "licence_evidence_status": "OFFICIAL_DATASET_PAGE_STATES_OGL_V3",
}
PROCUREMENT_RIGHTS = {
    "source_id": "gb_find_a_tender_ocds",
    "dataset": "Find a Tender OCDS notices",
    "dataset_uri": "https://www.find-tender.service.gov.uk/Developer/Documentation",
    "licence": "Open Government Licence v3.0",
    "licence_url": OGL,
    "required_attribution": (
        "Contains public sector information licensed under the Open Government Licence v3.0."
    ),
    "publisher": "UK Cabinet Office",
    "licence_evidence_status": "OFFICIAL_DEVELOPER_DOCS_STATES_OGL_V3",
}
FIELD_RIGHTS_HOLDS = (
    "INDEPENDENT_FIELD_RIGHTS_REVIEW_REQUIRED",
    "THIRD_PARTY_RIGHTS_MUST_BE_EXCLUDED",
    "PERSONAL_DATA_NOT_COVERED_BY_OGL",
    "ATTRIBUTION_REQUIRED_FOR_EXTERNAL_DERIVATIVES",
)
NEXT_ACTIONS = (
    "review_licensed_fields_and_third_party_exceptions",
    "independently_verify_government_source_provenance",
    "obtain_true_longitudinal_change_observations",
    "establish_direct_cross_source_project_identity",
    "validate_paid_buyer_problem_and_pricing",
)


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def build_internal_construction_dossier(
    *,
    snapshots: Sequence[Mapping[str, Any]],
    procurement: Mapping[str, Any] | None,
    reviewed_at: datetime,
    max_sample: int = MAX_SAMPLE,
) -> dict[str, Any]:
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone aware")
    if type(max_sample) is not int or not 1 <= max_sample <= MAX_SAMPLE:
        raise ValueError("sample bounds required")
    now = reviewed_at.astimezone(timezone.utc)
    # Until an independently reviewed source-rights receipt is implemented,
    # upstream approvals cannot be silently promoted into licence clearance.
    if any(
        not isinstance(item, Mapping)
        or item.get("rights_review_eligible") is not False
        or item.get("assessment_status") != "HOLD"
        or item.get("rights_holds") != ["RIGHTS_REVIEW_MISSING"]
        for item in snapshots
    ):
        raise ValueError("unreviewed upstream source-rights assertion")
    history = build_construction_history(snapshots, assessed_at=now)
    # History replay alone does not mean the latest data is currently fresh.
    current_raw = snapshots[-1]
    if not isinstance(current_raw, Mapping):
        raise ValueError("latest source snapshot malformed")
    records = current_raw.get("records")
    if not isinstance(records, list):
        raise ValueError("latest source records malformed")
    accepted = build_construction_preview(
        [{key: row[key] for key in (
            "record_id", "source_id", "dataset_id", "region", "record_type",
            "source_url", "source_observed_at", "planning_permission_status",
            "site_area_hectares", "source_entry_date",
        )} for row in records],
        observed_at=now,
    )
    if accepted["dataset_record_count"] != len(records) or accepted["rejected_counts"]:
        raise ValueError("latest source coverage or freshness not valid")
    matched_proc = _check_procurement(procurement, now=now)
    changed_ids = {event["record_id"] for event in history["observed_changes"]}

    samples = []
    for row in accepted["records"][:max_sample]:
        samples.append({
            "source_id": row["source_id"],
            "source_record_id": row["record_id"],
            "source_url": row["source_url"],
            "source_entry_date": row["source_entry_date"],
            "source_observed_at": row["source_observed_at"],
            "planning_permission_status": row["planning_permission_status"],
            "site_area_hectares": row["site_area_hectares"],
            "observed_history_change": row["record_id"] in changed_ids,
            "project_commencement_verified": False,
            "buyer_intent_verified": False,
            "commercial_probability_available": False,
            "commercial_distribution_permitted": False,
        })
    notices = (
        [{"source_id": "gb_find_a_tender_ocds",
          "release_id": notice_id,
          "source_url": "https://www.find-tender.service.gov.uk/Notice/" + notice_id,
          "cross_source_site_link_verified": False}
         for notice_id in matched_proc["release_ids"]]
        if matched_proc is not None else []
    )
    attribution = [PLANNING_RIGHTS]
    if matched_proc is not None:
        attribution.append(PROCUREMENT_RIGHTS)
    # A catalogue-level OGL claim never proves each particular field is
    # licensable. No developer-supplied rights flag can change this status.
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "product": "empire_construction_signals",
        "purpose": "INTERNAL_BUYER_VALUE_VALIDATION_ONLY",
        "customer_preview_not_distributable": True,
        "source_history_sha256": history["latest_chain_sha256"],
        "history_anchor_status": "NOT_EXTERNALLY_ANCHORED",
        "source_verified_fields_by_independent_reviewer": False,
        "source_change_count": history["observed_change_count"],
        "history_held_window_count": history["held_window_count"],
        "planning_records_available": len(accepted["records"]),
        "planning_records_in_sample": len(samples),
        "sample_is_complete": len(samples) == len(accepted["records"]),
        "planning_records": samples,
        "procurement_notices_in_sample": len(notices),
        "procurement_notices": notices,
        "cross_source_project_match_count": 0,
        "cross_source_relation": "NOT_ESTABLISHED",
        "rights_catalogue": attribution,
        "licence_class": "OGL_V3_PUBLIC_SOURCE_SCOPE_CLAIM",
        "licence_review_status": "SOURCE_LICENCE_IDENTIFIED_FIELD_RIGHTS_HELD",
        "rights_blockers": list(FIELD_RIGHTS_HOLDS),
        "verification_tasks": list(NEXT_ACTIONS),
        "buyer_interest_verified": False,
        "paid_pilot_verified": False,
        "predictive_accuracy_verified": False,
        "realised_revenue_verified": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }
