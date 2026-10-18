"""Claim-specific internal previews; external release remains inaccessible."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

import empire_os.data_product_claim_gate as gate
from empire_os.data_brokerage_product_catalog import (
    build_data_brokerage_product_catalog,validate_internal_brokerage_catalog,
)
from empire_os.intelligence_data_products import data_product_catalog

NOW=datetime(2026,10,18,12,52,tzinfo=timezone.utc)
ROOT=Path("/nonexisting/internal")


def packet():
    """Two DOF warehouse-class pairs and two unresolved lot pairs."""
    combos=[
       ("4436582","4000290016","THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS",
        "E2","CONTRACTORS_WAREHOUSE_BUILDING_CLASS",2500,0),
       ("2001177","2023620071","THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS",
        "E9","MISCELLANEOUS_WAREHOUSE_BUILDING_CLASS",2167,0),
       ("1024686","1010147501","DOB_REFERENCE_CORROBORATED_OTI_CONFLICT_REMAINS",
        "R0",None,None,18),
       ("2094839","2036730002","REFERENCE_CONFLICT_UNRESOLVED",
        "K4",None,0,0),
    ]
    out=[]
    for bin_id,lot,grade,building_class,label,area,coo in combos:
        kinds=["DOB_ISSUED_PERMIT_EVENT"]
        if grade=="THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS":
            kinds += [
                "OTI_PLUTO_TAXLOT_REFERENCE_MATCH",
                "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",
                "PLUTO_PUBLISHED_STORAGE_AREA_VALUE",
            ]
        else:
            kinds.append("OTI_BBL_CONFLICT_RECORDED")
            if coo:
                kinds.append("DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT")
        out.append({
            "entity_reference":{"bin":bin_id,"dob_bbl":lot},
            "source_dof_building_class_as_reported":building_class,
            "source_dof_building_class_label":label,
            "source_pluto_storage_area_as_reported":area,
            "coo_issued_records_matching_same_bin_bbl":coo,
            "evidence_grade":grade,
            "allowed_evidence_statements":kinds,
            "not_proven":["ACTIVE_WAREHOUSE_OPERATIONS",
                          "NAMED_SITE_OWNER_OR_OPERATOR",
                          "INDIVIDUAL_CUSTOMER_OR_BUYER",
                          "VERIFIED_REVENUE_OR_TRANSACTION"],
            "evidence_receipts":[{
                 "fact":"DOB_PERMIT_SOURCE","source_dataset_id":"rbx6-tga4",
                 "local_full_day_report_sha256":"a"*64},
                {"fact":"OTI_BIN_BASE_MAPPLUTO","source_dataset_id":"5zhs-2jue",
                 "selected_source_response_sha256":"b"*64},
                {"fact":"DCP_PLUTO_LOT_CLASS_AND_AREA","source_dataset_id":"64uk-42ks",
                 "selected_source_response_sha256":"c"*64},
                {"fact":"DOB_NOW_COO_STATUS_FOR_SELECTED_BIN","source_dataset_id":"pkdm-hqz6",
                 "selected_source_response_sha256":"d"*64}],
        })
    return {
        "schema":"empire.property_claim_evidence.v1",
        "mode":"OBSERVE",
        "observed_at_utc":NOW.isoformat(),
        "source_full_day_report_sha256":"a"*64,
        "source_full_day_issued_date":"2026-10-16",
        "claim_reviews":out,
    }


def claim(kind="DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",bin_id="4436582",
          lot="4000290016"):
    return {"statement_id":kind,"bin":bin_id,"dob_bbl":lot}


@pytest.fixture()
def source(monkeypatch):
    d=packet()
    monkeypatch.setattr(gate,"_source_chain",lambda root,now:d)
    return d


def test_whitelisted_statement_is_rendered_only_from_sourced_evidence(source):
    r=gate.review_data_product_claims(
        product_key="property_intelligence_monitor",
        requested_claims=[claim()],repo_root=ROOT,now=NOW,
    )
    assert r["status"]=="PRIVATE_SOURCE_BOUND_CLAIM_PREVIEW_ONLY"
    assert r["claim_count"]==1
    assert r["internal_preview_authorized"] is True
    assert r["customer_distribution_authorized"] is False
    assert r["external_data_export_authorized"] is False
    assert r["outbound_authorized"] is False
    assert r["payment_or_invoice_authorized"] is False
    assert r["verified_revenue"] is False
    c=r["validated_claims"][0]
    assert c["official_source_dataset_ids"]==["64uk-42ks"]
    assert c["source_evidence_receipts"][0]["official_dataset_page"]==(
        "https://data.cityofnewyork.us/d/64uk-42ks")
    assert c["source_evidence_receipts"][0]["local_selected_source_digest"]=="c"*64
    assert c["source_evidence_receipts"][0]["digest_is_publisher_signature"] is False
    assert "E2 (CONTRACTORS_WAREHOUSE_BUILDING_CLASS)" in c["source_scoped_statement_text"]
    assert "warehouse operation is not verified" in c["source_scoped_statement_text"]
    assert c["full_day_report_sha256"]=="a"*64
    assert not c["external_customer_release_authorized"]


def test_unsupported_claim_aborts_entire_request_not_partial_preview(source):
    valid=claim()
    forged=claim("ACTIVE_WAREHOUSE_OPERATIONS")
    result=gate.review_data_product_claims(
        product_key="property_intelligence_monitor",
        requested_claims=[valid,forged],repo_root=ROOT,now=NOW,
    )
    assert result["internal_preview_authorized"] is False
    assert result["validated_claims"]==[]
    assert result["reason_code"]=="UNSUPPORTED_STATEMENT_OR_REFERENCE"


@pytest.mark.parametrize("field",["marketing_copy","customer_ready","verified_buyer",
                                     "source_url","delivery_authorized","revenue"])
def test_caller_provided_text_authority_or_metadata_rejected(source,field):
    req=claim();req[field]="Empire AI verified an operating site, send it"
    r=gate.review_data_product_claims(product_key="nyc_permit_project_verification",
        requested_claims=[req],repo_root=ROOT,now=NOW)
    assert r["internal_preview_authorized"] is False
    assert r["reason_code"]=="UNAPPROVED_CLAIM_FIELDS"


def test_product_mapping_blocks_cross_vertical_unproven_claims(source):
    for product in ("forecast_snapshot","entity_graph_export",
                    "private_capital_intelligence","market_signal_feed"):
        result=gate.review_data_product_claims(
            product_key=product,requested_claims=[claim()],repo_root=ROOT,now=NOW)
        assert result["internal_preview_authorized"] is False
        assert result["reason_code"]=="PRODUCT_NOT_CLAIM_MAPPED"
    assert gate.review_data_product_claims(
        product_key="permit_intelligence_feed",requested_claims=[claim()],
        repo_root=ROOT,now=NOW)["reason_code"]=="UNSUPPORTED_STATEMENT_OR_REFERENCE"
    x=gate.review_data_product_claims(
        product_key="permit_intelligence_feed",
        requested_claims=[claim("DOB_ISSUED_PERMIT_EVENT")],
        repo_root=ROOT,now=NOW)
    assert x["internal_preview_authorized"] is True
    assert x["customer_distribution_authorized"] is False


def test_claim_is_held_if_wrong_property_or_source_fails(source):
    assert gate.review_data_product_claims(
        product_key="property_intelligence_monitor",
        requested_claims=[claim(bin_id="4436583")],repo_root=ROOT,now=NOW)[
            "reason_code"]=="STATEMENT_NOT_SUPPORTED_BY_OFFICIAL_SOURCES"
    assert gate.review_data_product_claims(
        product_key="property_intelligence_monitor",
        requested_claims=[claim("DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT",
                                "2094839","2036730002")],repo_root=ROOT,now=NOW)[
            "reason_code"]=="STATEMENT_NOT_SUPPORTED_BY_OFFICIAL_SOURCES"


def test_invalid_duplicate_and_too_many_claims_fail_closed(source):
    for values in ([],[claim()]*2,[claim()]*13,[{"statement_id":"x"}]):
        r=gate.review_data_product_claims(
            product_key="nyc_permit_project_verification",
            requested_claims=values,repo_root=ROOT,now=NOW)
        assert not r["internal_preview_authorized"]


def test_underlying_full_day_hash_mismatch_suppresses_claim_chain(monkeypatch,tmp_path):
    raw=b"{\"dummy_source\":1}"
    full=tmp_path/gate.REPORT_REL
    full.parent.mkdir(parents=True)
    full.write_bytes(raw)
    d=packet()
    monkeypatch.setattr(gate,"validated_claims",lambda root,now:d)
    monkeypatch.setattr(gate,"_validated_full_day",
                        lambda path:({"issued_day":"2026-10-16"},sha256(raw).hexdigest()))
    assert gate._source_chain(tmp_path,NOW) is None
    d["source_full_day_report_sha256"]=sha256(raw).hexdigest()
    assert gate._source_chain(tmp_path,NOW) is d
    monkeypatch.setattr(gate,"_validated_full_day",
                        lambda path:({"issued_day":"2026-10-17"},sha256(raw).hexdigest()))
    assert gate._source_chain(tmp_path,NOW) is None


def test_source_receipts_missing_means_no_preview_and_no_fake_export(monkeypatch):
    monkeypatch.setattr(gate,"_source_chain",lambda root,now:None)
    p=gate.review_data_product_claims(
       product_key="nyc_permit_project_verification",
       requested_claims=[claim()],repo_root=ROOT,now=NOW)
    assert p["status"]=="HOLD_NO_EVIDENCE_BOUND_REPORT"
    assert p["reason_code"]=="MISSING_STALE_OR_MISMATCHED_SOURCE_RECEIPTS"
    assert not p["external_data_export_authorized"]


def test_catalog_and_founder_products_cannot_claim_customer_ready():
    catalog=build_data_brokerage_product_catalog(assessed_at=NOW)
    assert validate_internal_brokerage_catalog(catalog)
    assert all(p["every_material_claim_requires_source_receipt"]
               for p in catalog["products"])
    assert all(not p["customer_claim_release_ready"] for p in catalog["products"])
    assert all(not p["arbitrary_claim_text_authorized"] for p in catalog["products"])
    assert catalog["products"][1]["claim_evidence_contract"]["status"]==(
        "NO_CURRENT_VERIFIED_CLAIM_RECEIPT")
    assert all(p["every_material_claim_requires_source_receipt"]
               for p in data_product_catalog())
    assert all(not p["customer_claim_release_ready"]
               for p in data_product_catalog())
    assert all(not p["unverified_claim_output_enabled"]
               for p in data_product_catalog())


def test_fake_evidence_scope_or_claim_approval_in_catalog_fails_closed():
    original=build_data_brokerage_product_catalog(assessed_at=NOW)
    for field,value in [
        ("customer_claim_release_ready",True),
        ("every_material_claim_requires_source_receipt",False),
        ("arbitrary_claim_text_authorized",True)
    ]:
        changed=deepcopy(original)
        changed["products"][1][field]=value
        assert not validate_internal_brokerage_catalog(changed)
    altered=deepcopy(original)
    altered["products"][1]["claim_evidence_contract"]["status"]=(
        "FOUR_SOURCE_BOUND_REFERENCE_CLAIMS_FOR_INTERNAL_REVIEW")
    assert not validate_internal_brokerage_catalog(altered)
    altered=deepcopy(original)
    altered["products"][1]["claim_evidence_contract"]["customer_claim_delivery_authorized"]=True
    assert not validate_internal_brokerage_catalog(altered)


def test_brokerage_catalog_reads_only_aggregate_evidence(monkeypatch,tmp_path):
    monkeypatch.setattr(gate,"_source_chain",lambda root,now:packet())
    original=build_data_brokerage_product_catalog(assessed_at=NOW,repo_root=tmp_path)
    assert validate_internal_brokerage_catalog(original)
    p=original["products"][1]
    assert p["claim_evidence_contract"]["reference_pair_count"]==4
    assert p["claim_evidence_contract"]["warehouse_class_reference_pair_count"]==2
    assert p["claim_evidence_contract"]["customer_claim_delivery_authorized"] is False
    assert not p["customer_data_export_ready"]
    assert "4436582" not in json.dumps(original)
    assert original["verified_payment_count"]==0



def test_explicit_cli_uses_same_source_gate_and_never_writes(
    tmp_path,monkeypatch,capsys
):
    from scripts import preview_product_claims_readonly as cmd
    monkeypatch.setattr(gate,"_source_chain",lambda root,now:packet())
    argv=[
        "--read-only","--product","nyc_permit_project_verification",
        "--statement","DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",
        "--bin","4436582","--bbl","4000290016",
    ]
    assert cmd.main(argv,repo_root=tmp_path)==0
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="PRIVATE_SOURCE_BOUND_CLAIM_PREVIEW_ONLY"
    assert out["claim_count"]==1
    assert out["customer_distribution_authorized"] is False
    assert not list(tmp_path.iterdir())
    assert cmd.main(argv[1:],repo_root=tmp_path)==2
    denied=json.loads(capsys.readouterr().out)
    assert denied["status"]=="HOLD_EXPLICIT_READ_ONLY_REQUIRED"
    assert not list(tmp_path.iterdir())


def test_existing_legacy_catalog_snapshot_is_safe_read_only_but_not_claim_ready():
    from empire_os.data_brokerage_product_catalog import _digest
    original=build_data_brokerage_product_catalog(assessed_at=NOW)
    historic=deepcopy(original)
    for product in historic["products"]:
        for key in ("claim_evidence_contract",
                    "every_material_claim_requires_source_receipt",
                    "customer_claim_release_ready",
                    "arbitrary_claim_text_authorized",
                    "source_claim_support_and_delivery_rights_separate"):
            product.pop(key)
    scope=[{"product_id":p["product_id"],
            "origin":p["source_origin_class"],
            "evidence":p["source_evidence_summary"],
            "source_licence_state":p["source_licence_state"]}
           for p in historic["products"]]
    historic["evidence_scope_sha256"]=_digest(scope)
    assert validate_internal_brokerage_catalog(historic)
    assert historic["customer_distributions_approved"]==0
    mixed=deepcopy(historic)
    mixed["products"][1]["every_material_claim_requires_source_receipt"]=True
    assert not validate_internal_brokerage_catalog(mixed)
    escalated=deepcopy(historic)
    escalated["customer_distributions_approved"]=1
    assert not validate_internal_brokerage_catalog(escalated)
