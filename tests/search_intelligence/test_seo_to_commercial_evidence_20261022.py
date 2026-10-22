"""GSC and canonical CRM counts stay separate absent trustworthy lineage."""
from copy import deepcopy
from datetime import date

import pytest
from empire_os.search_intelligence.weekly_two_page_outcomes import build_weekly_report
from empire_os.search_intelligence.seo_to_commercial_evidence import (
    build_commercial_bridge, CommercialEvidenceHeld,
)


def gsc_report():
    def source(path, *, params=None):
        if path=="/search-console/status":
            return {"available":True,"site_url":"sc-domain:empire-ai.co.uk"}
        return {
            "source":"google_search_console",
            "site_url":"sc-domain:empire-ai.co.uk",
            "available":True,
            "dimensions":["page"],
            "data_state":"final",
            "window":[params["start_date"],params["end_date"]],
            "count":0,"items":[],
        }
    return build_weekly_report(as_of=date(2026,10,22),get_json=source)


def crm_report(total=0):
    return {
        "schema_version":"empire.founder.sales_acquisition_crm_reconciliation.v1",
        "status":"NO_CANONICAL_SALES_ACQUISITION_OBSERVED" if total==0
                 else "NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH",
        "read_only":True, "database_writes":False, "outbound_sent":False,
        "payment_executed":False,"raw_customer_rows_read":False,
        "customer_identifiers_disclosed":False,
        "founder_crm_delivery_verified":False,
        "execution_authority":"NONE",
        "commercial_acquisition_rows":total,
        "predictive_acquisition_rows":0,
        "sales_acquisition_rows":total,
        "distinct_sales_prospects":total,
        "visible_commercial_sales_prospects":0,
        "visible_predictive_revenue_prospects":0,
        "visible_total_prospects":0,
        "source_evidence_consistent_rows":total,
    }


def test_realistic_zero_sales_not_zero_seo_enquiries():
    result=build_commercial_bridge(gsc_report(),crm_report())
    assert result["sitewide_canonical_sales_acquisitions"]==0
    assert result["founder_visible_sales_prospects"]==0
    assert result["canonical_sales_source_status"]=="NO_CANONICAL_SALES_ACQUISITION_OBSERVED"
    assert result["origin_page_to_enquiry_join_verified"] is False
    assert result["sitewide_aggregate_never_treated_as_seo_attribution"] is True
    assert all(p["attributed_consented_enquiries"] is None for p in result["page_observations"])
    assert all(p["clicks"] is None for p in result["page_observations"])
    assert result["recognised_revenue_from_seo_verified"] is False
    assert result["paid_model_calls"]==0


def test_nonzero_crm_count_never_becomes_page_conversion():
    result=build_commercial_bridge(gsc_report(),crm_report(5))
    assert result["sitewide_canonical_sales_acquisitions"]==5
    assert all(p["attributed_consented_enquiries"] is None
               and p["attributed_accepted_orders"] is None
               and p["attributed_realised_revenue"] is None
               for p in result["page_observations"])
    assert result["qualified_enquiry_from_two_pages_verified"] is False
    assert result["settlement_to_order_join_verified"] is False


def test_reject_untrusted_gsc_dimension_or_payload():
    report=deepcopy(gsc_report())
    report["dimensions"]=["query","page"]
    with pytest.raises(CommercialEvidenceHeld):
        build_commercial_bridge(report,crm_report())


def test_reject_database_mutation_or_sensitive_output():
    record=crm_report()
    record["database_writes"]=True
    with pytest.raises(CommercialEvidenceHeld):
        build_commercial_bridge(gsc_report(),record)
    record=crm_report()
    record["customer_identifiers_disclosed"]=True
    with pytest.raises(CommercialEvidenceHeld):
        build_commercial_bridge(gsc_report(),record)


def test_reject_duplicate_or_altered_page_set():
    report=deepcopy(gsc_report())
    report["current_window"]["pages"][1]["url"]="https://not-our-domain.example"
    with pytest.raises(CommercialEvidenceHeld):
        build_commercial_bridge(report,crm_report())


def test_reject_contradictory_sale_counts():
    record=crm_report(1)
    record["distinct_sales_prospects"]=3
    with pytest.raises(CommercialEvidenceHeld):
        build_commercial_bridge(gsc_report(),record)
