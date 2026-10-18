"""Internal, source-rights-aware Empire AI Data Brokerage offer inventory.

Reuses existing V15-V20 UK Planning Data Exchange custody, Permit Intelligence,
reviewed Common Crawl graph and optional first-party founder-content receipts.
It builds buyer-use-case previews, NOT a public raw-data marketplace, customer
delivery, a new database, entitlement grants, or unverified revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from empire_os.data_exchange_canonical_rights_docket import (
    DATASET_PAGE, LICENCE_PAGE,
)
from empire_os.founder_asset_provenance import SCHEMA as FOUNDER_RECEIPT_SCHEMA
from empire_os.free_dataset_intelligence import SCHEMA as GRAPH_SCHEMA
from empire_os.permit_project_intelligence import SCHEMA as PERMIT_SCHEMA

SCHEMA = "empire.data_brokerage.internal_product_catalog.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
PRODUCT_IDS = (
    "uk_brownfield_site_change_intelligence",
    "nyc_permit_project_verification",
    "historical_competitor_domain_graph_research",
    "founder_original_intelligence_reports",
)
ORIGIN_KINDS = {
    "uk_brownfield_site_change_intelligence": "THIRD_PARTY_OFFICIAL_GOVERNMENT_SOURCE",
    "nyc_permit_project_verification": "THIRD_PARTY_PUBLIC_PERMIT_RECORD",
    "historical_competitor_domain_graph_research": "THIRD_PARTY_HISTORICAL_OPEN_WEB_GRAPH",
    "founder_original_intelligence_reports": "FOUNDER_ORIGINAL_DERIVED_ANALYSIS",
}
USE_CASES = {
    "uk_brownfield_site_change_intelligence": (
        "UK brownfield site and planning history research for business land,"
        " energy, construction and site-acquisition operators"
    ),
    "nyc_permit_project_verification": (
        "Company and contractor due-diligence reports from date-verified"
        " construction project evidence"
    ),
    "historical_competitor_domain_graph_research": (
        "Historical referring-domain and competitor discovery research"
        " requiring fresh link verification before SEO advice"
    ),
    "founder_original_intelligence_reports": (
        "Original founder-owned market assessments, SEO opportunity maps,"
        " sector research and predictive-revenue consultancy deliverables"
    ),
}


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf8")).hexdigest()


def _custody_review(source: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        return {"status": "CANONICAL_CUSTODY_NOT_INSPECTED",
                "observations": None, "pinned_records": None,
                "source_sha256": None, "rights_cleared": False}
    if (source.get("schema_version")
            != "empire.data_exchange.live_temporal_inspection.v16"
            or source.get("status") != "CANONICAL_CUSTODY_READONLY_VERIFIED"
            or source.get("mode") != "OBSERVE"
            or source.get("customer_delivery_enabled") is not False
            or source.get("database_writes") is not False
            or source.get("source_rights_cleared") is not False
            or source.get("execution_authority") != "NONE"):
        raise ValueError("untrusted_or_rights_elevating_exchange_inspection")
    head = source.get("canonical_head_sha256")
    seq = source.get("canonical_head_sequence")
    observations = source.get("history_observation_count_in_window")
    if (not isinstance(head, str) or not _SHA.fullmatch(head)
            or type(seq) is not int or not 0 <= seq <= 15
            or type(observations) is not int or not 1 <= observations <= 16):
        raise ValueError("invalid_canonical_custody_proof")
    docket = source.get("canonical_field_rights_docket")
    if not isinstance(docket, Mapping):
        raise ValueError("missing_v18_canonical_source_rights_review")
    register = docket.get("release_evidence_register")
    if (docket.get("canonical_head_sha256") != head
            or docket.get("independent_source_licence_review_completed") is not False
            or docket.get("customer_delivery_enabled") is not False
            or docket.get("source_field_rights_cleared") is not False
            or docket.get("raw_source_response_privacy_review_status") != "NOT_PERFORMED"
            or not isinstance(register, Mapping)
            or register.get("canonical_head_sha256") != head
            or register.get("review_controls_completed") != 0
            or register.get("review_controls_pending") != 8
            or register.get("data_resale_authorized") is not False
            or register.get("founder_release_approved") is not False):
        raise ValueError("exchange_rights_or_privacy_review_forged")
    return {
        "status": "CANONICAL_CUSTODY_OBSERVED_RELEASE_HELD",
        "observations": observations,
        "pinned_records": docket.get("observed_pilot_entity_count"),
        "source_sha256": head,
        "rights_cleared": False,
        "field_review_pending": register["review_controls_pending"],
        "last_custody_observed_at": source.get("latest_canonical_observed_at"),
        "official_dataset_page": DATASET_PAGE,
        "official_licence_page": LICENCE_PAGE,
        "attribution": "© Crown copyright and database right 2026",
    }


def _permit_review(source: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(source, Mapping) or source.get("schema_version") != PERMIT_SCHEMA:
        return {"status": "PERMIT_INTELLIGENCE_NOT_SUPPLIED",
                "retained_records": None, "real_new_project_events": None}
    cohort = source.get("cohort")
    if (source.get("mode") != "OBSERVE" or not isinstance(cohort, Mapping)
            or source.get("buyer_matched") is not False
            or source.get("automatic_sales_promotion") is not False
            or source.get("paid_model_invoked") is not False):
        raise ValueError("permit_source_claim_exceeds_readonly_observation")
    return {
        "status": "PRIVATE_SOURCE_TRIAGE_ONLY",
        "retained_records": None,  # Not in bounded first-ingested cohort.
        "newly_imported_last_24h": cohort.get("first_imported_last_24h"),
        "real_new_project_events": cohort.get("recent_original_filing_or_issuance"),
        "historical_imports_last_24h": cohort.get("historical_project_source_only"),
        "official_url_shape_verified_count": cohort.get("official_provenance_url_passed"),
        "verified_sale_or_project_buyer": False,
    }


def _graph_review(source: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(source, Mapping) or source.get("schema_version") != GRAPH_SCHEMA:
        return {"status": "HISTORICAL_GRAPH_REVIEW_NOT_SUPPLIED",
                "historical_relationships": None, "source_domains": None}
    if source.get("status") != "REVIEWED_HISTORICAL_RESEARCH_AVAILABLE":
        return {"status": "HISTORICAL_GRAPH_SOURCE_HELD",
                "historical_relationships": None, "source_domains": None}
    if (source.get("confirmed_live_backlinks") != 0
            or source.get("empiredb_writes") is not False
            or source.get("paid_api_invoked") is not False
            or source.get("manual_review_required") is not True):
        raise ValueError("graph_claim_promoted_without_link_verification")
    return {
        "status": "HISTORICAL_RESEARCH_OBSERVED_ONLY",
        "historical_relationships": source["historical_relation_count"],
        "source_domains": source["distinct_source_domain_count"],
        "historical_report_sha256": source["review_sha256"],
        "confirmed_live_backlinks": 0,
        "link_verification_still_required": True,
    }


def _founder_review(receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    if receipt is None:
        return {
            "status": "ORIGINAL_ASSET_NOT_YET_REGISTERED",
            "founder_origin_assertion_present": False,
            "first_party_rights_proven": False,
        }
    if (receipt.get("schema_version") != FOUNDER_RECEIPT_SCHEMA
            or receipt.get("origin_class") not in (
                "FOUNDER_ORIGINAL", "FOUNDER_DIRECTED_AI_ASSISTED")
            or receipt.get("founder_ownership_declared") is not True
            or receipt.get("founder_ownership_independently_verified") is not False
            or receipt.get("public_release_authorized") is not False
            or receipt.get("third_party_resale_authorized") is not False
            or receipt.get("c2pa_content_credentials_validated") is not False
            or receipt.get("paid_service_used") is not False
            or not isinstance(receipt.get("file_sha256"), str)
            or not _SHA.fullmatch(receipt["file_sha256"])):
        raise ValueError("founder_asset_origin_or_rights_claim_unverified")
    return {
        "status": "FOUNDER_ORIGIN_DECLARED_PRIVATE_REVIEW",
        "founder_origin_assertion_present": True,
        "asset_sha256": receipt["file_sha256"],
        "ai_assistance": receipt["ai_assistance"],
        "third_party_components_declared": receipt[
            "third_party_components_declared"],
        "first_party_rights_proven": False,
        "third_party_components_verified": False,
        "content_credentials_verified": False,
    }


def build_data_brokerage_product_catalog(
    *, assessed_at: datetime, exchange_inspection: Mapping[str, Any] | None = None,
    permit_intelligence: Mapping[str, Any] | None = None,
    graph_intelligence: Mapping[str, Any] | None = None,
    founder_asset_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(assessed_at, datetime) or (
        assessed_at.tzinfo is None or assessed_at.utcoffset() is None
    ):
        raise ValueError("catalog_requires_aware_time")
    custody = _custody_review(exchange_inspection)
    permit = _permit_review(permit_intelligence)
    graph = _graph_review(graph_intelligence)
    founder = _founder_review(founder_asset_receipt)
    sources = {
        PRODUCT_IDS[0]: custody,
        PRODUCT_IDS[1]: permit,
        PRODUCT_IDS[2]: graph,
        PRODUCT_IDS[3]: founder,
    }
    catalogue = []
    for ident in PRODUCT_IDS:
        source = sources[ident]
        is_founder = ident == "founder_original_intelligence_reports"
        is_gov = ident == "uk_brownfield_site_change_intelligence"
        catalogue.append({
            "product_id": ident,
            "name": ident.replace("_", " ").title(),
            "suggested_business_use_case": USE_CASES[ident],
            "source_origin_class": ORIGIN_KINDS[ident],
            "internal_source_state": source["status"],
            "source_evidence_summary": source,
            "source_licence_state": (
                "FOUNDER_SELF_DECLARED_OWNERSHIP_NOT_EXTERNAL_COPYRIGHT_PROOF"
                if is_founder else
                "OGL_V3_PUBLISHED_COVERED_FIELDS_SCOPE_NOT_CLEARED"
                if is_gov else
                "DATASET_SPECIFIC_REUSE_SCOPE_UNVERIFIED"
            ),
            "source_attribution_required": not is_founder,
            "founder_created_derived_analysis_can_be_original": True,
            "raw_third_party_resale_cleared": False,
            "customer_data_export_ready": False,
            "offer_state": "INTERNAL_PREVIEW_FOR_FOUNDER_AND_SALES_RESEARCH",
            "buyer_verified": False,
            "verified_payment_events": 0,
            "recognised_revenue": 0,
            "fulfilment_verified": False,
            "product_activation_enabled": False,
            "external_api_provisioned": False,
            "execution_authority": "none",
        })
    scope = [
        {
            "product_id": p["product_id"],
            "origin": p["source_origin_class"],
            "evidence": p["source_evidence_summary"],
            "source_licence_state": p["source_licence_state"],
        }
        for p in catalogue
    ]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "FOUR_ORIGINAL_DATA_PRODUCTS_IN_INTERNAL_BROKERAGE_REVIEW",
        "generated_at": assessed_at.astimezone(timezone.utc).isoformat(),
        "product_count": len(catalogue),
        "products": catalogue,
        "evidence_scope_sha256": _digest(scope),
        "evidence_scope_digest_is_external_signature": False,
        "canonical_database": "EmpireDB",
        "source_cost_budget_gbp": 0,
        "external_paid_sources_used": False,
        "registered_founder_owned_asset_count": int(
            founder["founder_origin_assertion_present"]),
        "UK_dataset_data_brokerage_license_status": custody["status"],
        "customer_distributions_approved": 0,
        "independently_verified_buyer_count": 0,
        "verified_payment_count": 0,
        "third_party_resale_authorized": False,
        "product_publication_authorized": False,
        "marketing_outbound_sent": False,
        "billing_activation_enabled": False,
        "new_database_or_service_started": False,
        "execution_authority": "none",
    }


def validate_internal_brokerage_catalog(payload: Mapping[str, Any]) -> bool:
    """Pure read-side trust boundary for existing department team snapshots.

    Any forged resale/entitlement/paid-buyer claim must keep the source out of
    automatic departmental routing. Digests are local consistency checks,
    not signatures or an independent authentication of the source material.
    """
    if not isinstance(payload, Mapping):
        return False
    if (payload.get("schema_version") != SCHEMA
            or payload.get("status") !=
                "FOUR_ORIGINAL_DATA_PRODUCTS_IN_INTERNAL_BROKERAGE_REVIEW"
            or payload.get("mode") != "OBSERVE"
            or payload.get("product_count") != len(PRODUCT_IDS)
            or payload.get("canonical_database") != "EmpireDB"
            or payload.get("source_cost_budget_gbp") != 0
            or payload.get("external_paid_sources_used") is not False
            or payload.get("customer_distributions_approved") != 0
            or payload.get("independently_verified_buyer_count") != 0
            or payload.get("verified_payment_count") != 0
            or payload.get("third_party_resale_authorized") is not False
            or payload.get("product_publication_authorized") is not False
            or payload.get("marketing_outbound_sent") is not False
            or payload.get("billing_activation_enabled") is not False
            or payload.get("new_database_or_service_started") is not False
            or payload.get("execution_authority") != "none"):
        return False
    products = payload.get("products")
    if (not isinstance(products, list) or len(products) != len(PRODUCT_IDS)
            or [p.get("product_id") for p in products
                if isinstance(p, Mapping)] != list(PRODUCT_IDS)
            or not all(isinstance(p, Mapping) for p in products)):
        return False
    for product in products:
        if (product.get("source_origin_class")
                != ORIGIN_KINDS[product["product_id"]]
                or product.get("buyer_verified") is not False
                or product.get("raw_third_party_resale_cleared") is not False
                or product.get("customer_data_export_ready") is not False
                or product.get("product_activation_enabled") is not False
                or product.get("verified_payment_events") != 0
                or product.get("recognised_revenue") != 0
                or product.get("execution_authority") != "none"
                or not isinstance(product.get("source_evidence_summary"), Mapping)):
            return False
    scope = [
        {
            "product_id": p["product_id"],
            "origin": p["source_origin_class"],
            "evidence": p["source_evidence_summary"],
            "source_licence_state": p["source_licence_state"],
        }
        for p in products
    ]
    return payload.get("evidence_scope_sha256") == _digest(scope)
