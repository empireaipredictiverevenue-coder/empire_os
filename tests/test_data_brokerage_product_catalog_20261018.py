"""Data brokerage offers must keep third-party rights separate from founder IP."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.data_brokerage_product_catalog import (
    SCHEMA, PRODUCT_IDS, build_data_brokerage_product_catalog,
)
from empire_os.founder_asset_provenance import build_founder_asset_receipt

NOW = datetime(2026,10,18,9,55,tzinfo=timezone.utc)


def exchange():
    head="a"*64
    return {
        "schema_version":"empire.data_exchange.live_temporal_inspection.v16",
        "status":"CANONICAL_CUSTODY_READONLY_VERIFIED",
        "mode":"OBSERVE",
        "history_observation_count_in_window":1,
        "canonical_head_sequence":0,
        "canonical_head_sha256":head,
        "customer_delivery_enabled":False,
        "database_writes":False,
        "source_rights_cleared":False,
        "execution_authority":"NONE",
        "latest_canonical_observed_at":"2026-10-15T08:53:59.532101+00:00",
        "canonical_field_rights_docket":{
            "canonical_head_sha256":head,
            "observed_pilot_entity_count":3,
            "independent_source_licence_review_completed":False,
            "customer_delivery_enabled":False,
            "source_field_rights_cleared":False,
            "raw_source_response_privacy_review_status":"NOT_PERFORMED",
            "release_evidence_register":{
                "canonical_head_sha256":head,
                "review_controls_completed":0,
                "review_controls_pending":8,
                "data_resale_authorized":False,
                "founder_release_approved":False,
            },
        },
    }


def permit():
    return {
        "schema_version":"empire.permit_project_intelligence.v1",
        "mode":"OBSERVE",
        "buyer_matched":False,
        "automatic_sales_promotion":False,
        "paid_model_invoked":False,
        "cohort":{
            "first_imported_last_24h":62,
            "recent_original_filing_or_issuance":0,
            "historical_project_source_only":62,
            "official_provenance_url_passed":62,
        },
    }


def graph():
    return {
        "schema_version":"empire.free_dataset_intelligence.review.v1",
        "status":"REVIEWED_HISTORICAL_RESEARCH_AVAILABLE",
        "historical_relation_count":1974,
        "distinct_source_domain_count":1870,
        "confirmed_live_backlinks":0,
        "manual_review_required":True,
        "review_sha256":"b"*64,
        "empiredb_writes":False,
        "paid_api_invoked":False,
    }


def report(**updates):
    cfg={
        "assessed_at":NOW,
        "exchange_inspection":exchange(),
        "permit_intelligence":permit(),
        "graph_intelligence":graph(),
    }
    cfg.update(updates)
    return build_data_brokerage_product_catalog(**cfg)


def test_four_source_pinned_internal_products_truth_and_no_fake_sale():
    d=report()
    assert d["schema_version"]==SCHEMA
    assert d["product_count"]==4
    assert len(d["evidence_scope_sha256"])==64
    assert {p["product_id"] for p in d["products"]}==set(PRODUCT_IDS)
    assert all(not p["customer_data_export_ready"] for p in d["products"])
    assert all(not p["raw_third_party_resale_cleared"] for p in d["products"])
    assert all(not p["buyer_verified"] for p in d["products"])
    assert all(p["verified_payment_events"]==0 for p in d["products"])
    assert d["verified_payment_count"]==0
    assert d["customer_distributions_approved"]==0
    assert d["third_party_resale_authorized"] is False
    assert d["product_publication_authorized"] is False
    assert d["source_cost_budget_gbp"]==0
    assert d["canonical_database"]=="EmpireDB"
    assert d["new_database_or_service_started"] is False
    assert d["registered_founder_owned_asset_count"]==0
    a={row["product_id"]:row for row in d["products"]}
    uk=a["uk_brownfield_site_change_intelligence"]
    assert uk["source_evidence_summary"]["observations"]==1
    assert uk["source_evidence_summary"]["pinned_records"]==3
    assert uk["source_evidence_summary"]["field_review_pending"]==8
    assert uk["source_licence_state"].startswith("OGL_V3")
    assert uk["source_evidence_summary"]["rights_cleared"] is False
    nyc=a["nyc_permit_project_verification"]
    assert nyc["source_evidence_summary"]["real_new_project_events"]==0
    assert nyc["source_evidence_summary"]["historical_imports_last_24h"]==62
    historical=a["historical_competitor_domain_graph_research"]
    assert historical["source_evidence_summary"]["historical_relationships"]==1974
    assert historical["source_evidence_summary"]["confirmed_live_backlinks"]==0
    assert historical["source_evidence_summary"]["link_verification_still_required"]


def test_absent_protected_db_inspection_is_held_not_fabricated():
    d=build_data_brokerage_product_catalog(assessed_at=NOW)
    uk=d["products"][0]
    assert uk["source_evidence_summary"]["status"]=="CANONICAL_CUSTODY_NOT_INSPECTED"
    assert uk["source_evidence_summary"]["observations"] is None
    assert not uk["customer_data_export_ready"]
    assert d["registered_founder_owned_asset_count"]==0


@pytest.mark.parametrize("path,value",[
    (("customer_delivery_enabled",),True),
    (("database_writes",),True),
    (("source_rights_cleared",),True),
    (("canonical_head_sha256",),"not a sha"),
    (("canonical_field_rights_docket","independent_source_licence_review_completed"),True),
    (("canonical_field_rights_docket","raw_source_response_privacy_review_status"),"CLEARED"),
    (("canonical_field_rights_docket","release_evidence_register","data_resale_authorized"),True),
    (("canonical_field_rights_docket","release_evidence_register","founder_release_approved"),True),
    (("canonical_field_rights_docket","release_evidence_register","review_controls_completed"),8),
])
def test_false_source_rights_or_customer_release_claim_rejected(path,value):
    d=exchange()
    node=d
    for key in path[:-1]:
        node=node[key]
    node[path[-1]]=value
    with pytest.raises(ValueError):
        report(exchange_inspection=d)


def test_fabricated_permit_buyer_or_graph_verified_links_rejected():
    d=permit()
    d["buyer_matched"]=True
    with pytest.raises(ValueError):
        report(permit_intelligence=d)
    g=graph()
    g["confirmed_live_backlinks"]=4
    with pytest.raises(ValueError):
        report(graph_intelligence=g)


def test_authorship_from_founder_self_declaration_not_copyright_guarantee(tmp_path):
    file=tmp_path/"founder_research.md"
    file.write_text("# My original Empire AI research\n\nFounder authored.")
    asset=build_founder_asset_receipt(
        file,asset_id="original-market-research-v1",
        origin_class="FOUNDER_ORIGINAL",
        ai_assistance="NONE_DECLARED",
        founder_ownership_declared=True,
        third_party_components_declared=False,
    )
    catalog=report(founder_asset_receipt=asset)
    assert catalog["registered_founder_owned_asset_count"]==1
    founder=catalog["products"][3]["source_evidence_summary"]
    assert founder["status"]=="FOUNDER_ORIGIN_DECLARED_PRIVATE_REVIEW"
    assert founder["asset_sha256"]==asset["file_sha256"]
    assert founder["first_party_rights_proven"] is False
    assert not catalog["product_publication_authorized"]
    false=deepcopy(asset)
    false["founder_ownership_independently_verified"]=True
    with pytest.raises(ValueError):
        report(founder_asset_receipt=false)


def test_deterministic_source_scope_digest_depends_on_inputs_not_clock():
    a=report()
    b=report(assessed_at=NOW.replace(hour=10))
    assert a["evidence_scope_sha256"]==b["evidence_scope_sha256"]
    changed=graph()
    changed["distinct_source_domain_count"]=1871
    c=report(graph_intelligence=changed)
    assert a["evidence_scope_sha256"]!=c["evidence_scope_sha256"]


def test_non_timezone_aware_catalog_assessment_rejected():
    with pytest.raises(ValueError):
        build_data_brokerage_product_catalog(
            assessed_at=datetime(2026,10,18,9,55))
