"""V18: per-field rights evidence docket from existing V15 canonical custody.

Accepts ONE genuine stored observation: independent rights review need not
wait for a second timestamp. Reuses existing rights preflight provenance
vocabulary, official dataset/OGL citations, protected source projection.
It DOES NOT grant a legal right, customer API, model training, sales or export.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, _guard_snapshot, parse_at, verify_custody_window,
)
from empire_os.data_exchange_change_intelligence import _validated_preview
from empire_os.data_exchange_rights_preflight import (
    PLANNING_FIELDS, REVIEWER_CHECKS, EXCLUDED_FIELDS, RESTRICTIONS,
)
from empire_os.data_exchange_evidence_dossier import PLANNING_RIGHTS
from empire_os.data_exchange_temporal_quality import PILOT_IDS

SCHEMA="empire.data_exchange.canonical_field_rights_docket.v18"
DATASET_PAGE="https://www.planning.data.gov.uk/dataset/brownfield-land"
LICENCE_PAGE="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
API_PROJECTION={
    "source_record_id":"entity",
    "source_url":"official entity permalink (constructed from verified entity ID)",
    "source_entry_date":"entry-date",
    "planning_permission_status":"planning-permission-status",
    "site_area_hectares":"hectares",
    "source_observed_at":"Empire-captured fetch timestamp, not government publication date",
    "observed_history_change":"Empire derived comparison, requires two canonical captures",
}


def build_canonical_rights_docket(
    rows: Sequence[Mapping[str, Any]], *, assessed_at: datetime,
) -> dict[str, Any]:
    if not isinstance(assessed_at,datetime) or (
        assessed_at.tzinfo is None or assessed_at.utcoffset() is None
    ):
        raise CustodyIntegrityError("rights docket requires aware assessment")
    now=assessed_at.astimezone(timezone.utc)
    proof=verify_custody_window(rows)
    latest=rows[-1]
    at=parse_at(latest["source_observed_at"])
    if at>now:
        raise CustodyIntegrityError("future official observation")
    snapshot=latest["snapshot_json"]
    _guard_snapshot(snapshot,now=at)
    by_id=_validated_preview(snapshot,at)
    if set(by_id) - PILOT_IDS:
        raise CustodyIntegrityError("source sample exceeds pinned official pilot")
    if len(by_id)!=snapshot["dataset_record_count"]:
        raise CustodyIntegrityError("custody sample count mismatch")
    # Existing provenance and official dataset catalogue must match exactly;
    # there is no path for a supplied rights-review flag or arbitrary source.
    if (PLANNING_RIGHTS["dataset_uri"]!=DATASET_PAGE
        or PLANNING_RIGHTS["licence_url"]!=LICENCE_PAGE
        or PLANNING_RIGHTS["source_id"]!="gb_planning_data"
        or PLANNING_RIGHTS["dataset"]!="brownfield-land"
        or set(PLANNING_FIELDS)!=set(API_PROJECTION)):
        raise CustodyIntegrityError("rights catalogue or field projection drift")
    fields=[]
    for name in sorted(PLANNING_FIELDS):
        origin=PLANNING_FIELDS[name]
        if origin not in ("government_published_field","empire_observation",
                          "empire_derived_evaluation"):
            raise CustodyIntegrityError("unreviewed source field provenance")
        fields.append({
            "product_field":name,
            "origin_class":origin,
            "input_field_or_derivation":API_PROJECTION[name],
            "evidence_scope":"PUBLISHED_DATASET_OGL_STATEMENT_ONLY"
                if origin=="government_published_field"
                else "FIRST_PARTY_DERIVED_NOT_COVERED_BY_PUBLISHER_LICENCE_CLAIM",
            "derivation_currently_observable":(
                len(rows)>=2 if name=="observed_history_change" else True
            ),
            "independent_field_rights_review":"NOT_COMPLETED",
            "third_party_exception_review":"NOT_COMPLETED",
            "personal_data_exclusion_review":"NOT_COMPLETED",
            "client_distribution_authorised":False,
        })
    checks=[{
        "control_id":ident,
        "required_action":summary,
        "verification_status":"PENDING_HUMAN_AND_LEGAL_EVIDENCE_REVIEW",
        "signoff_artifact_present":False,
    } for ident,summary in REVIEWER_CHECKS]
    if not checks or not fields:
        raise CustodyIntegrityError("empty rights review inventory")
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"REVIEW_DOCKET_READY_NOT_LICENSE_APPROVAL",
        "canonical_head_sequence":proof["last_sequence"],
        "canonical_head_sha256":proof["head_chain_sha256"],
        "canonical_observation_count_in_window":len(rows),
        "canonical_origin_in_window":proof["window_origin_anchored_to_genesis"],
        "local_hash_integrity":proof["hash_link_integrity"],
        "official_data_source":"gb_planning_data",
        "dataset":"brownfield-land",
        "dataset_licence_evidence_url":DATASET_PAGE,
        "licence_terms_url":LICENCE_PAGE,
        "dataset_stated_licence":"Open Government Licence v3.0",
        "dataset_stated_attribution":PLANNING_RIGHTS["required_attribution"],
        "publisher_evidence_status":"OFFICIAL_DATASET_PAGE_STATES_OGL_V3",
        "independent_source_licence_review_completed":False,
        "source_field_count":len(fields),
        "field_evidence_docket":fields,
        "review_checklist":checks,
        "excluded_fields_by_design":list(EXCLUDED_FIELDS),
        "remaining_restrictions":list(RESTRICTIONS),
        "observed_pilot_entity_count":len(by_id),
        "pinned_pilot_complete":set(by_id)==PILOT_IDS,
        "regional_coverage_claim":False,
        "source_personal_information_collected":False,
        "source_field_rights_cleared":False,
        "OGL_commercial_reuse_possible_in_principle":True,
        "independently_cleared_for_commercial_product":False,
        "independent_government_authentication":False,
        "customer_delivery_enabled":False,
        "data_resale_authorized":False,
        "outbound_enabled":False,
        "payment_execution":False,
        "production_writes":False,
        "actual_revenue_verified":False,
        "execution_authority":"NONE",
    }
