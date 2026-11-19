"""Bounded field-level OGL preflight for Empire Construction Signals.

Source pages establish general dataset licensing, not field-level legal
clearance, consent, source authenticity or permission to publish a feed.
This produces an independently reviewable release checklist and precise
provenance matrix without creating a distribution or commercial grant.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_evidence_dossier import (
    PLANNING_RIGHTS, PROCUREMENT_RIGHTS,
    build_internal_construction_dossier,
)

SCHEMA = "empire.data_exchange.rights_preflight.v1"
PROVENANCE_TYPES = {"government_published_field", "empire_observation",
                    "empire_derived_evaluation"}
PLANNING_FIELDS = {
    "source_record_id": "government_published_field",
    "source_url": "government_published_field",
    "source_entry_date": "government_published_field",
    "planning_permission_status": "government_published_field",
    "site_area_hectares": "government_published_field",
    "source_observed_at": "empire_observation",
    "observed_history_change": "empire_derived_evaluation",
}
PROCUREMENT_FIELDS = {
    "release_id": "government_published_field",
    "source_url": "government_published_field",
    "cross_source_site_link_verified": "empire_derived_evaluation",
}
RESTRICTIONS = (
    "ATTRIBUTION_IN_PRODUCT_REQUIRED",
    "FIELD_LEVEL_THIRD_PARTY_RIGHTS_REVIEW_REQUIRED",
    "PERSONAL_DATA_AND_CONTACT_FIELDS_EXCLUDED",
    "INDEPENDENT_SOURCE_IDENTITY_REVIEW_REQUIRED",
    "RETENTION_AND_REVOCATION_POLICY_REQUIRED",
    "NO_FALSE_GOVERNMENT_ENDORSEMENT",
)
EXCLUDED_FIELDS = (
    "name", "site-address", "notes", "owner", "ownership-person",
    "phone", "email", "contactPoint", "description", "tender.title",
    "tender.description", "parties", "buyer", "supplier",
)
REVIEWER_CHECKS = (
    ("source_terms", "Record the official dataset licence and applicable exceptions"),
    ("field_scope", "Verify each included field has no unlicensed third-party material"),
    ("privacy", "Confirm personal information and contact details are excluded"),
    ("attribution", "Include both source attribution statements and the OGL link"),
    ("provenance", "Check dataset record IDs, dates and immutable observation custody"),
    ("retention", "Review retention, correction and revocation procedures"),
    ("commercial_claims", "Exclude buyer intent, site-project joins and forecast claims without proof"),
    ("release_authority", "Record independent sign-off and explicit founder release authority"),
)


def _hash(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def build_rights_preflight(
    *,
    source_snapshots: Sequence[Mapping[str, Any]],
    procurement: Mapping[str, Any] | None,
    assessed_at: datetime,
) -> dict[str, Any]:
    """Rebuild the source dossier instead of trusting caller-supplied claims."""
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("assessed_at must be timezone aware")
    dossier = build_internal_construction_dossier(
        snapshots=source_snapshots,
        procurement=procurement,
        reviewed_at=assessed_at,
    )
    if (
        dossier["mode"] != "OBSERVE"
        or dossier["customer_delivery_enabled"] is not False
        or dossier["data_resale_authorized"] is not False
        or dossier["cross_source_project_match_count"] != 0
        or dossier["source_verified_fields_by_independent_reviewer"] is not False
    ):
        raise ValueError("unreviewed underlying source distribution assertion")

    source_rights = dossier["rights_catalogue"]
    expected = ([PLANNING_RIGHTS, PROCUREMENT_RIGHTS]
                if procurement is not None else [PLANNING_RIGHTS])
    if source_rights != expected:
        raise ValueError("rights attribution catalogue mismatch")

    records = dossier["planning_records"]
    notices = dossier["procurement_notices"]
    if any(set(x) != set(PLANNING_FIELDS) | {
        "source_id", "project_commencement_verified",
        "buyer_intent_verified", "commercial_probability_available",
        "commercial_distribution_permitted",
    } for x in records):
        raise ValueError("unreviewed planning field in dossier")
    if any(
        not isinstance(r["source_record_id"], str)
        or re.fullmatch(r"[0-9]{1,12}", r["source_record_id"]) is None
        or r["source_url"] != (
            "https://www.planning.data.gov.uk/entity/" + r["source_record_id"]
        )
        or any(r[k] is not False for k in (
            "project_commencement_verified", "buyer_intent_verified",
            "commercial_probability_available",
            "commercial_distribution_permitted",
        ))
        for r in records
    ):
        raise ValueError("planning source identity or commercial semantics invalid")
    if any(
        set(n) != {"source_id", *PROCUREMENT_FIELDS}
        or n["cross_source_site_link_verified"] is not False
        or n["source_url"] != (
            "https://www.find-tender.service.gov.uk/Notice/" + n["release_id"]
        )
        for n in notices
    ):
        raise ValueError("unreviewed procurement field in dossier")

    lineage = []
    for source, fields in (
        ("gb_planning_data", PLANNING_FIELDS),
        ("gb_find_a_tender_ocds", PROCUREMENT_FIELDS if procurement is not None else {}),
    ):
        lineage.extend({
            "source_id": source,
            "field_name": key,
            "field_provenance": origin,
            "published_source_licence": (
                "OGL_V3_STATED" if origin == "government_published_field"
                else "NOT_A_GOVERNMENT_SOURCE_LICENCE_CLAIM"
            ),
            "field_review_status": "PENDING_INDEPENDENT_REVIEW",
            "customer_distribution_grant": False,
        } for key, origin in fields.items())

    attribution = [{
        "source_id": item["source_id"],
        "statement": item["required_attribution"],
        "source_uri": item["dataset_uri"],
        "licence_uri": item["licence_url"],
        "external_product_rendering_verified": False,
    } for item in source_rights]

    # No provision to promote rights in this helper: a future independently
    # checked receipt and founder-gated release must live elsewhere.
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "product": "empire_construction_signals",
        "source_history_sha256": dossier["source_history_sha256"],
        "source_evidence_sha256": _hash({
            "source_history": dossier["source_history_sha256"],
            "record_ids": sorted(r["source_record_id"] for r in records),
            "notice_ids": sorted(n["release_id"] for n in notices),
            "rights_catalogue": source_rights,
        }),
        "source_record_count": dossier["planning_records_available"],
        "procurement_notice_count": dossier["procurement_notices_in_sample"],
        "field_lineage": lineage,
        "provenance_type_definitions": sorted(PROVENANCE_TYPES),
        "excluded_by_design": list(EXCLUDED_FIELDS),
        "rights_evidence": attribution,
        "source_licence_class": "OPEN_GOVERNMENT_LICENCE_V3_STATED",
        "commercial_reuse_permitted_in_principle": True,
        "commercial_use_scope_assessment": "OGL_COVERED_INFORMATION_ONLY",
        "independent_field_rights_review": "NOT_COMPLETED",
        "reviewer_checklist": [{
            "control_id": key, "required_action": explanation,
            "status": "PENDING_REVIEW",
        } for key, explanation in REVIEWER_CHECKS],
        "remaining_release_checks": list(RESTRICTIONS),
        "saleable_product_verified": False,
        "paid_buyer_validated": False,
        "source_causation_verified": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }
