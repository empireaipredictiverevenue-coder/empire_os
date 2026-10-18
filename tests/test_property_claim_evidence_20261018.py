"""Evidence-bound NYC property assertions: four pairs, no fabricated operations."""
import json
from datetime import datetime,timezone,timedelta
from hashlib import sha256

import pytest

import empire_os.property_claim_evidence_review as read
from empire_os.property_claim_receipt_runtime import (
    PATH,MANIFEST,property_claims_summary,validated_claims,supported_claim,
)
from empire_os.vertical_intelligence_runtime import build_property_intelligence_runtime
from empire_os.source_intelligence_handoff import build_source_intelligence_handoffs

NOW=datetime.now(timezone.utc)
SOURCE_HASH="a"*64


def groups():
    vals=[
      ("INDUSTRIAL_CONTEXT_CORROBORATED","4436582","4000290016",1),
      ("INDUSTRIAL_CONTEXT_CORROBORATED","2001177","2023620071",3),
      ("DOB_OTI_BBL_UNRESOLVED","1024686","1010147501",1),
      ("DOB_OTI_BBL_UNRESOLVED","2094839","2036730002",8),
    ]
    ds=[]
    for state,bin_id,lot,num in vals:
        for index in range(num):
            ds.append({
                "industrial_tax_lot_context_corroborated":
                    state=="INDUSTRIAL_CONTEXT_CORROBORATED",
                "building_tax_lot_evidence_state":(
                    "TRI_AGENCY_BIN_AND_LOT_MATCH" if
                    state=="INDUSTRIAL_CONTEXT_CORROBORATED"
                    else "BUILDING_TAX_LOT_CONFLICT"),
                "permit_building_bin":bin_id,"permit_tax_lot_bbl":lot,
                "permit_job_filing_ref":f"X{len(ds):08d}-I1",
            })
    return ds


class Response:
    def __init__(self,rows,url):
        self.content=json.dumps(rows).encode()
        self.url=url+"?selected=bounded"
    def raise_for_status(self):pass


class Fake:
    def __init__(self,change_industrial=False):
        self.calls=[]
        self.change_industrial=change_industrial

    def get(self,url,*,params,timeout,headers):
        assert timeout==15 and "$select" in params
        assert "name" not in params["$select"] and "street" not in params["$select"]
        self.calls.append(url)
        if url==read.PLUTO_URL:
            return Response([
              {"bbl":"4000290016.00000000","landuse":"6",
               "bldgclass":"E2" if not self.change_industrial else "R0","strgearea":"2500"},
              {"bbl":"2023620071.00000000","landuse":"6","bldgclass":"E9","strgearea":"2167"},
              {"bbl":"1010147501.00000000","bldgclass":"R0"},
              {"bbl":"2036730002.00000000","landuse":"4","bldgclass":"K4"},
            ],url)
        if url==read.OTI_URL:
            return Response([
              {"bin":"4436582","base_bbl":"4000290016","mappluto_bbl":"4000290016"},
              {"bin":"2001177","base_bbl":"2023620071","mappluto_bbl":"2023620071"},
              {"bin":"1024686","base_bbl":"1010140033","mappluto_bbl":"1010140033"},
              {"bin":"2094839","base_bbl":"2036730001","mappluto_bbl":"2036730001"},
            ],url)
        if url==read.COO_URL:
            return Response([{
                "bin":"1024686","bbl":"1010147501","c_of_o_status":"CO Issued",
                "c_of_o_filing_type":"Renewal Without Change"
            } for _ in range(18)],url)
        raise AssertionError("unexpected source URL")


@pytest.fixture
def observed(monkeypatch,tmp_path):
    monkeypatch.setattr(read,"_validated_full_day",lambda path:(
        {"issued_day":"2026-10-16","diagnostics":groups()},SOURCE_HASH))
    fake=Fake()
    r=read.review_property_claims(repo_root=tmp_path,client=fake,now=NOW)
    assert fake.calls==[read.PLUTO_URL,read.OTI_URL,read.COO_URL]
    return r


def write_capture(root,data):
    dest=root/PATH;manifest=root/MANIFEST
    dest.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(data,sort_keys=True,indent=2)+"\n").encode()
    dest.write_bytes(raw)
    manifest.write_text(json.dumps({
        "schema":"empire.property_claim_evidence_receipt.v1",
        "derived_evidence_sha256":sha256(raw).hexdigest(),
        "consumer_sales_release_authorized":False,
    }))
    return dest,manifest


def test_four_claim_grades_and_coo_only_supports_narrow_reference(observed):
    claims={x["entity_reference"]["bin"]:x for x in observed["claim_reviews"]}
    assert len(claims)==4
    assert claims["1024686"]["coo_issued_records_matching_same_bin_bbl"]==18
    assert claims["1024686"]["evidence_grade"]=="DOB_REFERENCE_CORROBORATED_OTI_CONFLICT_REMAINS"
    assert claims["2094839"]["evidence_grade"]=="REFERENCE_CONFLICT_UNRESOLVED"
    assert claims["2094839"]["coo_issued_records_matching_same_bin_bbl"]==0
    assert claims["2001177"]["source_dof_building_class_label"]=="MISCELLANEOUS_WAREHOUSE_BUILDING_CLASS"
    assert claims["4436582"]["source_dof_building_class_label"]=="CONTRACTORS_WAREHOUSE_BUILDING_CLASS"
    assert [claims[x]["source_pluto_storage_area_as_reported"] for x in ("2001177","4436582")]==[2167,2500]
    assert all(x["customer_claim_approved"] is False for x in claims.values())
    assert all("ACTIVE_WAREHOUSE_OPERATIONS" in x["not_proven"] for x in claims.values())
    assert observed["warehouse_operations_verified_count"]==0


def test_strict_claim_whitelist_and_source_receipt_binding(tmp_path,observed):
    write_capture(tmp_path,observed)
    assert validated_claims(tmp_path,now=NOW) is not None
    assert supported_claim(tmp_path,bin_id="4436582",dob_bbl="4000290016",
                           statement="DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",now=NOW)
    assert supported_claim(tmp_path,bin_id="1024686",dob_bbl="1010147501",
                           statement="DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT",now=NOW)
    assert not supported_claim(tmp_path,bin_id="2094839",dob_bbl="2036730002",
                           statement="DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT",now=NOW)
    for unsupported in ("ACTIVE_WAREHOUSE_OPERATIONS","VERIFIED_REVENUE",
                        "OWNER_VERIFIED","BUYER_INTENT","CONTACT_APPROVED"):
        assert not supported_claim(tmp_path,bin_id="4436582",dob_bbl="4000290016",
                                   statement=unsupported,now=NOW)


def test_tamper_and_missing_provenance_fail_closed(tmp_path,observed):
    dest,receipt=write_capture(tmp_path,observed)
    dest.write_bytes(dest.read_bytes().replace(b"2500",b"2510"))
    assert validated_claims(tmp_path,now=NOW) is None
    assert property_claims_summary(tmp_path,now=NOW)["status"]=="NO_VERIFIED_PROPERTY_CLAIM_RECEIPTS"
    write_capture(tmp_path,observed);receipt.unlink()
    assert validated_claims(tmp_path,now=NOW) is None


def test_cross_reference_source_digest_mismatch_denies_even_with_rehashed_manifest(tmp_path,observed):
    report=json.loads(json.dumps(observed))
    report["claim_reviews"][0]["evidence_receipts"][1]["selected_source_response_sha256"]="f"*64
    write_capture(tmp_path,report)
    assert validated_claims(tmp_path,now=NOW) is None


def test_claim_escalation_denied_even_with_rehashed_manifest(tmp_path,observed):
    for field,value in (
        ("customer_claim_approved",True),
        ("outbound_authorized",True),
    ):
        forged=json.loads(json.dumps(observed))
        forged["claim_reviews"][0][field]=value
        write_capture(tmp_path,forged)
        assert validated_claims(tmp_path,now=NOW) is None


def test_old_snapshot_becomes_stale_without_new_source_observation(tmp_path,observed):
    write_capture(tmp_path,observed)
    future=NOW+timedelta(days=3)
    assert validated_claims(tmp_path,now=future) is None
    assert not supported_claim(tmp_path,bin_id="4436582",dob_bbl="4000290016",
                               statement="DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",now=future)


def test_real_property_and_warehouse_read_models_only_receive_aggregates(tmp_path,observed):
    write_capture(tmp_path,observed)
    property_runtime=build_property_intelligence_runtime(tmp_path)
    claims=property_runtime["evidence_bound_property_claims"]
    assert claims["status"]=="FOUR_SOURCE_BOUND_REFERENCE_CLAIMS_REVIEWED"
    assert claims["official_warehouse_class_reference_pairs"]==2
    assert claims["active_warehouse_businesses_verified"]==0
    assert property_runtime["opportunity_count"] is None
    handoff=build_source_intelligence_handoffs(tmp_path)
    by_lane={x["lane"]:x for x in handoff["routes"]}
    assert by_lane["property"]["counts"]["source_bound_claim_reference_pairs"]==4
    assert by_lane["warehouse"]["counts"]["source_bound_dof_warehouse_class_reference_pairs"]==2
    assert by_lane["warehouse"]["counts"]["verified_operating_warehouse_businesses"]==0
    assert "CONTRACTORS_WAREHOUSE_BUILDING_CLASS" not in json.dumps(handoff)


def test_current_primary_official_class_change_fails_closed(monkeypatch,tmp_path):
    monkeypatch.setattr(read,"_validated_full_day",lambda path:(
        {"issued_day":"2026-10-16","diagnostics":groups()},SOURCE_HASH))
    with pytest.raises(ValueError,match="WAREHOUSE_CLASSIFICATION_NOT_REPRODUCED"):
        read.review_property_claims(repo_root=tmp_path,client=Fake(change_industrial=True),
                                   now=NOW)
