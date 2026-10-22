from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from empire_os.gtm_commercial_source_bridge import (
    JEV_SCHEMA, GSC_SCHEMA, SALES_SCHEMA, TARGETS,
    observe_product_sources, review_jev, review_organic, review_sales_counts,
)

NOW = datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)


def jev():
    return {
        "schema_version": JEV_SCHEMA,
        "mode": "OBSERVE",
        "status": "CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY",
        "execution_authority": "none",
        "generated_at_utc": NOW.isoformat(),
        "verified_individual_clients": 0,
        "verified_contracts": 0,
        "prospects_verified": 0,
        "source_rights_and_consent_verified": False,
        "crm_writes": False,
        "database_writes": False,
        "outbound_sent": 0,
        "pain_counts": {"inconsistent_lead_flow": {
            "observations": 4,
            "matched_offer_to_validate": "growth_research",
        }},
    }


def gsc():
    return {
        "schema_version": GSC_SCHEMA,
        "status": "READ_ONLY_WEEKLY_REPORT",
        "source_property": "sc-domain:empire-ai.co.uk",
        "dimensions": ["page"], "execution_authority": "NONE",
        "website_mutations": False,
        "qualified_buyer_enquiries_verified": False,
        "realised_revenue_verified": False,
        "automatic_jev_model_calls": 0,
        "source_errors": [],
        "as_of": NOW.date().isoformat(),
        "current_window": {"source_status":"FINAL_PAGE_ROWS", "pages": [
            {"url":TARGETS[0], "status":"MEASURED_PAGE_METRICS",
             "clicks": 2, "impressions": 50, "evidence_refs":["gsc-page-row-sha256:"+"a"*64]},
            {"url":TARGETS[1], "status":"NO_PAGE_IN_RETURNED_GSC_ROWS",
             "clicks": None, "impressions": None, "evidence_refs":[]},
        ]},
    }


def sales():
    return {
        "schema_version": SALES_SCHEMA, "mode":"OBSERVE",
        "read_only":True, "source":"CANONICAL_EMPIREDB",
        "status":"SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED",
        "execution_authority":"NONE", "customer_rows_disclosed":False,
        "contact_data_disclosed":False, "database_writes":False,
        "outbound_sent":False, "payment_action":False,
        "founder_crm_delivery_verified":False,
        "observed_at_utc":NOW.isoformat(),
        "commercial_acquisition_rows":1, "predictive_acquisition_rows":0,
        "sales_acquisition_rows":1, "distinct_sales_prospects":1,
        "source_evidence_consistent_rows":1,
        "entity_unlinked_acquisition_rows":0,
        "founder_binding_exact_one_rows":1,
        "founder_binding_missing_or_ambiguous_rows":0,
    }


def test_jev_evidence_is_not_buyer_or_contact_permission():
    a=review_jev(jev(),now=NOW)
    assert a["pain_theme_review_count"] == 1
    assert a["verified_buyers"] == 0
    assert a["promoted_prospects"] == 0
    assert a["pain_theme_reviews"][0]["contact_authorized"] is False


def test_jev_opt_out_or_spoofed_verified_clients_held():
    for k,v in (("verified_individual_clients",1),("source_rights_and_consent_verified",True),
                ("database_writes",True),("execution_authority","live")):
        p=jev();p[k]=v
        assert review_jev(p,now=NOW)["pain_theme_review_count"] == 0


def test_jev_staleness_and_no_themes():
    p=jev();p["pain_counts"]={}
    assert review_jev(p,now=NOW)["status"]=="NO_CONCRETE_JEV_PAIN_THEMES_IN_CURRENT_RECEIPT"
    p["generated_at_utc"]=(NOW-timedelta(days=3)).isoformat()
    assert review_jev(p,now=NOW)["status"]=="HELD_UNVERIFIED_JEV_RECEIPT"


def test_gsc_page_evidence_not_lead_conversion():
    a=review_organic(gsc(),now=NOW)
    assert a["gsc_page_metrics"][0]["gsc_clicks"]==2
    assert a["gsc_page_metrics"][1]["gsc_clicks"] is None
    assert a["search_to_enquiry_join_verified"] is False
    assert a["organic_sales_attributed"] is None


def test_gsc_wrong_site_stale_fabricated_counts_held():
    for k,v in (("source_property","sc-domain:another-site.co.uk"),
                ("qualified_buyer_enquiries_verified",True),
                ("website_mutations",True),
                ("as_of","2026-10-01")):
        p=gsc();p[k]=v
        assert review_organic(p,now=NOW)["status"]=="HELD_UNVERIFIED_GSC_RECEIPT"
    p=gsc();p["current_window"]["pages"][0]["clicks"]=51
    assert review_organic(p,now=NOW)["status"]=="HELD_UNVERIFIED_GSC_RECEIPT"


def test_genuine_enquiry_count_requires_owner_receipt_and_does_not_contact():
    empty=review_sales_counts(None,now=NOW)
    assert empty["enquiries_observed"] is None
    assert empty["status"].startswith("HELD")
    a=review_sales_counts(sales(),now=NOW)
    assert a["enquiries_observed"]==1
    assert a["consent_verified_aggregate"] is True
    assert a["crm_delivery_verified"] is False
    assert a["outbound_authorized"] is False
    assert a["search_attribution_verified"] is False


def test_enquiry_counts_reject_claimed_consent_or_stale_spoofing():
    for k,v in (("outbound_sent",True),("observed_at_utc","2026-10-20T00:00:00Z"),
                ("source","browser"),("execution_authority","send"),
                ("contact_data_disclosed",True),
                ("founder_crm_delivery_verified",True)):
        p=sales();p[k]=v
        assert review_sales_counts(p,now=NOW)["enquiries_observed"] is None
    p=sales();p["source_evidence_consistent_rows"]=2
    assert review_sales_counts(p,now=NOW)["enquiries_observed"] is None


def test_missing_sources_do_not_create_fake_zero(tmp_path):
    a=observe_product_sources(tmp_path,now=NOW,gsc_directory=tmp_path/"absent")
    assert a["jev"]["pain_theme_review_count"]==0
    assert a["organic_search"]["organic_sales_attributed"] is None
    assert a["first_party_enquiries"]["enquiries_observed"] is None
    assert a["automatic_acquisition_or_outbound_authorized"] is False


def test_aggregate_jev_and_gsc_only_no_source_contact_data(tmp_path):
    dest=tmp_path/"runtime/jev_client_pain_discovery/aggregate_latest.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(jev()))
    report_dir=tmp_path/"gsc";report_dir.mkdir()
    (report_dir/"weekly_two_page_2026-10-23.json").write_text(json.dumps(gsc()))
    a=observe_product_sources(tmp_path,now=NOW,gsc_directory=report_dir)
    assert a["jev"]["pain_theme_review_count"]==1
    assert a["organic_search"]["gsc_page_metrics"][0]["gsc_clicks"]==2
    assert a["first_party_enquiries"]["status"].startswith("HELD")
    assert "@" not in json.dumps(a)

def test_brokerage_catalog_observed_but_never_sales_authorized():
    from empire_os.gtm_commercial_source_bridge import review_brokerage_catalog
    fixture = {
        "schema_version":"empire.data_brokerage.internal_product_catalog.v1",
        "status":"FOUR_ORIGINAL_DATA_PRODUCTS_IN_INTERNAL_BROKERAGE_REVIEW",
        "mode":"OBSERVE", "execution_authority":"none",
        "canonical_database":"EmpireDB", "billing_activation_enabled":False,
        "product_publication_authorized":False,
        "third_party_resale_authorized":False,
        "external_paid_sources_used":False,
        "marketing_outbound_sent":False,
        "independently_verified_buyer_count":0, "verified_payment_count":0,
        "customer_distributions_approved":0,
        "generated_at":NOW.isoformat(),
        "product_count":4,
        "products":[{}, {}, {}, {}],
    }
    observed=review_brokerage_catalog(fixture,now=NOW)
    assert observed["internal_product_count"] == 4
    assert observed["buyer_matching_authorized"] is False
    assert observed["source_rights_cleared_for_sale"] is False
    assert observed["enquiry_receipts_verified"] is False
    fixture["third_party_resale_authorized"]=True
    assert review_brokerage_catalog(fixture,now=NOW)["internal_product_count"] is None
