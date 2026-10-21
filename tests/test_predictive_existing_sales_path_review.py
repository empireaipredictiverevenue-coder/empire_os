"""First-party sales-path review never invents customer evidence."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from empire_os.predictive_existing_sales_path_review import review_sales_path
import scripts.review_predictive_sales_path_20261021 as cli


def page():
    return {
        "schema_version": "empire.founder.live_sales_page_readonly_canary.v1",
        "mode": "READ_ONLY",
        "status": "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN",
        "compiled_intake_routes_verified": 2,
        "public_page_count": 2,
        "commercial_offer_count": 10,
        "predictive_revenue_product_count": 5,
        "canonical_sales_acquisitions_checked": False,
        "founder_crm_delivery_verified": False,
        "genuine_test_buyer_submitted": False,
        "checkout_or_payment_executed": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def crm(commercial=0, predictive=0):
    return {
        "schema_version": "empire.predictive_revenue.existing_founder_sales_crm_bridge.v1",
        "mode": "OBSERVE",
        "status": (
            "TENANT_VISIBLE_SALES_COHORT_PRESENT_SOURCE_UNVERIFIED"
            if commercial+predictive else
            "NO_TENANT_VISIBLE_SALES_PROSPECTS_SOURCE_UNVERIFIED"
        ),
        "counts": {
            "visible_commercial_sales_prospects": commercial,
            "visible_predictive_revenue_prospects": predictive,
            "visible_total_prospects": commercial+predictive,
        },
        "execution_authority": "none",
        "crm_write_performed": False,
        "outbound_sent": False,
        "original_customer_order_authenticated": False,
        "crm_customer_specific_source_receipt_authenticated": False,
        "canonical_original_acquisition_probe_checked": False,
    }


def test_empty_funnel_does_not_promote_customer_conversion():
    result=review_sales_path(page(),crm())
    assert result["status"]=="PUBLIC_FORMS_READY_NO_FOUNDER_VISIBLE_SALES"
    assert result["public_intake_routes_verified"] is True
    assert result["founder_visible_commercial_prospects"]==0
    assert result["canonical_acquisition_count_checked"] is False
    assert result["founder_crm_delivery_verified"] is False
    assert result["customer_forecast_eligible"] is False
    assert result["database_writes"] is False
    assert result["payment_action"] is False
    assert result["next_original_owner_action"].startswith("OBTAIN_GENUINE")


def test_positive_crm_is_not_a_source_matched_sale():
    result=review_sales_path(page(),crm(2,3))
    assert result["status"]=="CRM_VISIBLE_SALES_REQUIRE_ORIGINAL_SOURCE_RECEIPT_MATCH"
    assert result["founder_visible_commercial_prospects"]==2
    assert result["founder_visible_predictive_revenue_prospects"]==3
    assert not result["founder_crm_delivery_verified"]
    assert not result["authenticated_customer_order_verified"]


@pytest.mark.parametrize("key,value", [
    ("schema_version","untrusted"),
    ("status","HELD"),
    ("compiled_intake_routes_verified",0),
    ("public_page_count",True),
    ("commercial_offer_count",0),
    ("genuine_test_buyer_submitted",True),
    ("checkout_or_payment_executed",True),
    ("database_writes",True),
    ("outbound_sent",True),
])
def test_unverified_public_page_report_cannot_pass(key,value):
    item=page()
    item[key]=value
    result=review_sales_path(item,crm())
    assert result["status"] in {"PUBLIC_INTAKE_REPORT_HELD","PUBLIC_ENQUIRY_ROUTES_HELD"}
    assert result["founder_visible_commercial_prospects"] is None


@pytest.mark.parametrize("key,value", [
    ("schema_version","untrusted"),
    ("mode","LIVE_WRITE"),
    ("crm_write_performed",True),
    ("outbound_sent",True),
    ("original_customer_order_authenticated",True),
    ("crm_customer_specific_source_receipt_authenticated",True),
    ("canonical_original_acquisition_probe_checked",True),
])
def test_unsafe_crm_report_held(key,value):
    item=crm()
    item[key]=value
    result=review_sales_path(page(),item)
    assert result["status"]=="FOUNDER_TENANT_CRM_REPORT_HELD"
    assert result["founder_crm_delivery_verified"] is False


def test_inconsistent_crm_counts_hold_and_no_private_details_exported():
    original=crm(1)
    original["counts"]["visible_total_prospects"]=0
    original["counts"]["email"]="private@example.invalid"
    result=review_sales_path(page(),original)
    assert result["status"]=="FOUNDER_TENANT_CRM_READER_HELD"
    assert "private@example.invalid" not in json.dumps(result)
    assert result["source_customer_contact_disclosed"] is False


def test_cli_uses_both_original_source_readers_without_side_effect(monkeypatch,capsys):
    monkeypatch.setattr(cli,"inspect",lambda:page())
    monkeypatch.setattr(cli,"run_existing_founder_crm_review",lambda:crm())
    assert cli.main(["--read-only"])==0
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="PUBLIC_FORMS_READY_NO_FOUNDER_VISIBLE_SALES"
    assert report["database_writes"] is False
