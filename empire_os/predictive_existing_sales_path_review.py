"""Join EXISTING read-only public intake and scoped founder CRM observations.

This never reads a customer acquisition or asserts first-party conversion
because the canonical acquisition reconciliation requires its original owner.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "empire.predictive_revenue.first_party_sales_path_observe.v1"
PAGE_SCHEMA = "empire.founder.live_sales_page_readonly_canary.v1"
CRM_SCHEMA = "empire.predictive_revenue.existing_founder_sales_crm_bridge.v1"


def review_sales_path(page: Mapping[str, Any], crm: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "PUBLIC_OR_TENANT_SOURCE_UNVERIFIED",
        "public_intake_routes_verified": False,
        "founder_visible_commercial_prospects": None,
        "founder_visible_predictive_revenue_prospects": None,
        "canonical_acquisition_count_checked": False,
        "individual_prospect_lineage_authenticated": False,
        "founder_crm_delivery_verified": False,
        "genuine_buyer_submission_verified": False,
        "authenticated_customer_order_verified": False,
        "customer_forecast_eligible": False,
        "source_customer_contact_disclosed": False,
        "database_writes": False,
        "outbound_sent": False,
        "payment_action": False,
        "execution_authority": "none",
    }
    if not isinstance(page, Mapping) or not isinstance(crm, Mapping):
        return result
    if (page.get("schema_version") != PAGE_SCHEMA
            or page.get("mode") != "READ_ONLY"
            or page.get("execution_authority") != "none"
            or page.get("database_writes") is not False
            or page.get("outbound_sent") is not False
            or page.get("checkout_or_payment_executed") is not False
            or page.get("genuine_test_buyer_submitted") is not False
            or page.get("canonical_sales_acquisitions_checked") is not False
            or page.get("founder_crm_delivery_verified") is not False):
        result["status"] = "PUBLIC_INTAKE_REPORT_HELD"
        return result
    if (page.get("status") != "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN"
            or type(page.get("compiled_intake_routes_verified")) is not int
            or page["compiled_intake_routes_verified"] != 2
            or type(page.get("public_page_count")) is not int
            or page["public_page_count"] != 2
            or type(page.get("commercial_offer_count")) is not int
            or page["commercial_offer_count"] < 1
            or type(page.get("predictive_revenue_product_count")) is not int
            or page["predictive_revenue_product_count"] < 1):
        result["status"] = "PUBLIC_ENQUIRY_ROUTES_HELD"
        return result
    result["public_intake_routes_verified"] = True
    if (crm.get("schema_version") != CRM_SCHEMA
            or crm.get("mode") != "OBSERVE"
            or crm.get("execution_authority") != "none"
            or crm.get("crm_write_performed") is not False
            or crm.get("outbound_sent") is not False
            or crm.get("original_customer_order_authenticated") is not False
            or crm.get("crm_customer_specific_source_receipt_authenticated") is not False
            or crm.get("canonical_original_acquisition_probe_checked") is not False
            or crm.get("founder_crm_delivery_verified", False) is not False):
        result["status"] = "FOUNDER_TENANT_CRM_REPORT_HELD"
        return result
    counts = crm.get("counts")
    if not isinstance(counts, Mapping):
        result["status"] = "FOUNDER_TENANT_CRM_READER_HELD"
        return result
    keys = ("visible_commercial_sales_prospects",
            "visible_predictive_revenue_prospects", "visible_total_prospects")
    if any(type(counts.get(key)) is not int or not 0 <= counts[key] <= 1_000_000
           for key in keys):
        result["status"] = "FOUNDER_TENANT_CRM_READER_HELD"
        return result
    commercial, predictive, total = (counts[key] for key in keys)
    if (commercial + predictive > total
            or crm.get("status") != (
                "TENANT_VISIBLE_SALES_COHORT_PRESENT_SOURCE_UNVERIFIED"
                if commercial + predictive else
                "NO_TENANT_VISIBLE_SALES_PROSPECTS_SOURCE_UNVERIFIED"
            )):
        result["status"] = "FOUNDER_TENANT_CRM_READER_HELD"
        return result
    result["founder_visible_commercial_prospects"] = commercial
    result["founder_visible_predictive_revenue_prospects"] = predictive
    result["status"] = (
        "CRM_VISIBLE_SALES_REQUIRE_ORIGINAL_SOURCE_RECEIPT_MATCH"
        if commercial + predictive else
        "PUBLIC_FORMS_READY_NO_FOUNDER_VISIBLE_SALES"
    )
    result["next_original_owner_action"] = (
        "VERIFY_EXACT_GENUINE_ENQUIRY_AND_TENANT_LINEAGE"
        if commercial + predictive else
        "OBTAIN_GENUINE_CONSENTED_BUYER_ENQUIRY_THEN_RECONCILE_SOURCE_TO_CRM"
    )
    return result
