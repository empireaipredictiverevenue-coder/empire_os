"""Conservative bridge: page-level GSC + canonical EmpireDB aggregate-only CRM.

Never claims SEO attribution from Google clicks or sitewide CRM totals.
No personal data, prospect IDs, wallet addresses, receipts, DB mutation,
outbound, paid inference, or revenue recognition. Aggregate comparison only.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "empire.search.two_page_seo_to_commercial_evidence.v1"
TARGETS = (
    "https://empire-ai.co.uk/predictive-revenue",
    "https://empire-ai.co.uk/industries/roofing",
)
SOURCE_ALLOWED = (
    "NO_CANONICAL_SALES_ACQUISITION_OBSERVED",
    "CANONICAL_INTAKE_EVIDENCE_INCONSISTENT",
    "IDENTITY_LINK_GAP_DETECTED",
    "TENANT_BINDING_GAP_DETECTED",
    "CRM_PROJECTION_GAP_DETECTED",
    "NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH",
)


class CommercialEvidenceHeld(ValueError):
    pass


def _count(v:Any)->int:
    if type(v) is not int or v<0 or v>1_000_000:
        raise CommercialEvidenceHeld("CANONICAL_COUNT_INVALID")
    return v


def build_commercial_bridge(
    weekly:Mapping[str,Any], sales:Mapping[str,Any]
)->dict[str,Any]:
    if (not isinstance(weekly,Mapping)
            or weekly.get("schema_version")!="empire.search.weekly_two_page_outcome_observer.v1"
            or weekly.get("status")!="READ_ONLY_WEEKLY_REPORT"
            or weekly.get("source_property")!="sc-domain:empire-ai.co.uk"
            or weekly.get("dimensions")!=["page"]
            or weekly.get("website_mutations") is not False
            or weekly.get("automatic_jev_model_calls")!=0
            or weekly.get("realised_revenue_verified") is not False
            or weekly.get("qualified_buyer_enquiries_verified") is not False
            or weekly.get("execution_authority")!="NONE"):
        raise CommercialEvidenceHeld("GSC_REPORT_UNTRUSTED_OR_WRONG_SCOPE")
    win=weekly.get("current_window")
    if (not isinstance(win,Mapping) or not isinstance(win.get("pages"),list)
            or len(win["pages"])!=2
            or tuple(p.get("url") for p in win["pages"])!=TARGETS):
        raise CommercialEvidenceHeld("TARGET_PAGE_SET_CHANGED")
    if (not isinstance(sales,Mapping)
            or sales.get("schema_version")!="empire.founder.sales_acquisition_crm_reconciliation.v1"
            or sales.get("status") not in SOURCE_ALLOWED
            or sales.get("read_only") is not True
            or sales.get("database_writes") is not False
            or sales.get("outbound_sent") is not False
            or sales.get("payment_executed") is not False
            or sales.get("customer_identifiers_disclosed") is not False
            or sales.get("raw_customer_rows_read") is not False
            or sales.get("founder_crm_delivery_verified") is not False
            or sales.get("execution_authority")!="NONE"):
        raise CommercialEvidenceHeld("CANONICAL_AGGREGATE_SOURCE_UNTRUSTED")
    count_keys=(
        "commercial_acquisition_rows",
        "predictive_acquisition_rows",
        "sales_acquisition_rows",
        "distinct_sales_prospects",
        "visible_commercial_sales_prospects",
        "visible_predictive_revenue_prospects",
        "visible_total_prospects",
        "source_evidence_consistent_rows",
    )
    nums={k:_count(sales.get(k)) for k in count_keys}
    if (nums["commercial_acquisition_rows"]+nums["predictive_acquisition_rows"]
            !=nums["sales_acquisition_rows"]
            or nums["distinct_sales_prospects"]>nums["sales_acquisition_rows"]
            or nums["source_evidence_consistent_rows"]>nums["sales_acquisition_rows"]
            or nums["visible_commercial_sales_prospects"]
               +nums["visible_predictive_revenue_prospects"]>nums["visible_total_prospects"]):
        raise CommercialEvidenceHeld("CANONICAL_COUNTERS_CONTRADICT_EACH_OTHER")
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "as_of":weekly["as_of"],
        "seo_report_status":weekly["new_postrelease_page_data_status"],
        "gsc_comparison_valid":weekly["comparison_valid_after_release"],
        "page_observations":[{
            "url":p["url"],
            "search_status":p["status"],
            "clicks":p["clicks"],
            "impressions":p["impressions"],
            "ctr":p["ctr"],
            "attributed_consented_enquiries":None,
            "attributed_accepted_orders":None,
            "attributed_realised_revenue":None,
        } for p in win["pages"]],
        "sitewide_canonical_commercial_acquisitions":nums["commercial_acquisition_rows"],
        "sitewide_canonical_predictive_acquisitions":nums["predictive_acquisition_rows"],
        "sitewide_canonical_sales_acquisitions":nums["sales_acquisition_rows"],
        "founder_visible_sales_prospects":nums["visible_total_prospects"],
        "canonical_sales_source_status":sales["status"],
        "origin_page_to_enquiry_join_verified":False,
        "visitor_referrer_record_verified":False,
        "qualified_enquiry_from_two_pages_verified":False,
        "buyer_acceptance_receipt_join_verified":False,
        "fulfilled_order_join_verified":False,
        "settlement_to_order_join_verified":False,
        "recognised_revenue_from_seo_verified":False,
        "sitewide_aggregate_never_treated_as_seo_attribution":True,
        "buyer_contact_or_personal_data_disclosed":False,
        "source_uses":"EXISTING_GSC_READER_AND_CANONICAL_EMPIREDB_COUNT_ONLY_PROBES",
        "new_data_access_roles_granted":False,
        "database_writes":False,
        "outbound_sent":False,
        "website_mutations":False,
        "paid_model_calls":0,
        "money_moved":False,
        "execution_authority":"NONE",
    }
