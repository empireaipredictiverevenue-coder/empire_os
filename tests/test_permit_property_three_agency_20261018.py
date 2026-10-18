"""Cross-agency reference and land-use truth without buyer/asset inventions."""
from __future__ import annotations

import json
from datetime import datetime,timezone

import pytest

from empire_os.permit_property_source_join import (
    FOOTPRINT_URL,PLUTO_URL,review_official_building_landuse,
)
from empire_os.lead_sources.nyc_dobnow import current_event_sample

NOW=datetime(2026,10,18,11,30,tzinfo=timezone.utc)

def event(job="B01222111-I1",bin="3002642",bbl="3002697501",**kwargs):
    r={
        "job_filing_number":job,
        "bin":bin,"bbl":bbl,
        "borough":"Brooklyn",
        "issued_date":"2026-10-16",
        "filing_reason":"Initial Permit","permit_status":"Permit Issued",
        "official_event_crosscheck":True,
    }
    r.update(kwargs)
    return r


def footprint(bin="3002642",bbl="3002697501",**kw):
    d={"bin":bin,"base_bbl":bbl,
       "doitt_id":"70000","last_status_type":"Constructed"}
    d.update(kw)
    return d


def pluto(bbl="3002697501",landuse="6",**kw):
    d={"bbl":bbl+".00000000",
       "borough":"BK","landuse":landuse,
       "bldgclass":"E1","strgearea":"93000","factryarea":"0"}
    d.update(kw)
    return d


class Response:
    def __init__(self,rows,url):
        self.content=json.dumps(rows).encode()
        self.url=url+"?example=bounded_select"
    def raise_for_status(self):
        pass


class Client:
    def __init__(self,footprints=None,lots=None):
        self.footprints=[footprint()] if footprints is None else footprints
        self.lots=[pluto()] if lots is None else lots
        self.requests=[]
    def get(self,url,*,params,timeout,headers):
        assert url in (FOOTPRINT_URL,PLUTO_URL)
        assert timeout<=15
        assert headers["Accept"]=="application/json"
        assert "$limit" in params and params["$limit"]<=120
        assert all(s not in params["$select"] for s in (
            "ownername","owner", "address", "street", "name", "the_geom",
        ))
        self.requests.append((url,params))
        return Response(self.footprints if url==FOOTPRINT_URL else self.lots,url)


def test_independent_three_agency_bin_bbl_chain_is_not_warehouse_proof():
    c=Client()
    report=review_official_building_landuse([event()],now=NOW,client=c)
    assert len(c.requests)==2
    row=report["diagnostics"][0]
    assert row["building_tax_lot_evidence_state"]=="TRI_AGENCY_BIN_AND_LOT_MATCH"
    assert row["dcp_land_use_code"]=="06"
    assert row["dcp_land_use_category"]=="INDUSTRIAL_MANUFACTURING"
    assert row["industrial_tax_lot_context_corroborated"] is True
    assert row["warehouse_operation_verified"] is False
    assert row["verified_business_buyer"] is False
    assert row["commercial_contact_authorized"] is False
    assert report["event_level_industrial_lot_context_count"]==1
    assert report["data_warehouse_or_empiredb_mutated"] is False
    assert report["execution_authority"]=="none"
    assert report["rights_review_required_for_customer_distribution"] is True
    assert report["source_selected_response_receipts"][0]["selected_response_sha256"]


def test_footprint_lot_disagreement_is_a_conflict_not_clean_match():
    out=review_official_building_landuse([event()],now=NOW,client=Client(
       footprints=[footprint(bbl="3002690001")]))
    row=out["diagnostics"][0]
    assert row["building_tax_lot_evidence_state"]=="BUILDING_TAX_LOT_CONFLICT"
    assert row["industrial_tax_lot_context_corroborated"] is False
    assert row["warehouse_operation_verified"] is False


def test_pluto_lot_only_and_missing_code_unknown():
    out=review_official_building_landuse([event()],now=NOW,client=Client(
       footprints=[],lots=[pluto(landuse=None)]))
    row=out["diagnostics"][0]
    assert row["building_tax_lot_evidence_state"]=="DCP_LOT_ONLY_BIN_UNCONFIRMED"
    assert row["dcp_land_use_category"]=="UNKNOWN"
    assert row["industrial_tax_lot_context_corroborated"] is False


def test_footprint_only_never_guesses_property_landuse():
    out=review_official_building_landuse([event()],now=NOW,client=Client(lots=[]))
    row=out["diagnostics"][0]
    assert row["building_tax_lot_evidence_state"]=="OTI_BIN_ONLY_TAX_LOT_UNCONFIRMED"
    assert row["dcp_land_use_category"]=="UNKNOWN"


def test_double_footprint_one_bin_fails_closed_ambiguity():
    x=review_official_building_landuse([event()],now=NOW,client=Client(
      footprints=[footprint(),footprint(doitt_id="70001")]))
    row=x["diagnostics"][0]
    assert row["building_tax_lot_evidence_state"]=="AMBIGUOUS_SOURCE_IDENTITY"
    assert row["industrial_tax_lot_context_corroborated"] is False


def test_double_pluto_lot_is_ambiguous():
    x=review_official_building_landuse([event()],now=NOW,client=Client(
      lots=[pluto(),pluto(bldgclass="E4")]))
    assert x["diagnostics"][0]["building_tax_lot_evidence_state"]=="AMBIGUOUS_SOURCE_IDENTITY"
    assert x["diagnostics"][0]["industrial_tax_lot_context_corroborated"] is False


def test_dcp_borough_conflict_invalidates_industrial_join():
    x=review_official_building_landuse([event()],now=NOW,client=Client(
      lots=[pluto(borough="QN")]))
    assert x["diagnostics"][0]["building_tax_lot_evidence_state"]=="DCP_BOROUGH_CONFLICT"
    assert x["diagnostics"][0]["dcp_land_use_category"]=="UNKNOWN"


def test_landuse_01_03_05_06_and_04_are_distinct_categories():
    expect={"1":"ONE_TWO_FAMILY","3":"MULTIFAMILY_ELEVATOR",
            "4":"MIXED_RESIDENTIAL_COMMERCIAL",
            "5":"COMMERCIAL_OFFICE","6":"INDUSTRIAL_MANUFACTURING"}
    for category,taxon in expect.items():
        x=review_official_building_landuse([event()],now=NOW,client=Client(
            lots=[pluto(landuse=category)]))
        assert x["diagnostics"][0]["dcp_land_use_category"]==taxon


def test_duplicate_jobs_refused_even_if_different_building():
    c=Client()
    with pytest.raises(ValueError,match="DUPLICATE_JOB"):
        review_official_building_landuse([event(),event(bbl="3002690001")],
                                          now=NOW,client=c)
    assert c.requests==[]


def test_unverified_or_injected_source_event_never_queries_endpoint():
    c=Client()
    bad=[
      event(job="B01222111-I1' UNION SELECT *"),
      event(bin="3002' OR 1=1"),
      event(bbl="999.99"),
      event(official_event_crosscheck=False),
      event(permit_status="Disapproved"),
    ]
    for v in bad:
        with pytest.raises(ValueError,match="UNTRUSTED_SOURCE_EVENTS"):
            review_official_building_landuse([v],now=NOW,client=c)
    assert not c.requests


def test_many_events_max_bounded_and_no_provider_call():
    c=Client()
    items=[event(job=f"B{i:08d}-I1") for i in range(41)]
    with pytest.raises(ValueError,match="UNBOUNDED_PERMIT_PROPERTY_REVIEW"):
        review_official_building_landuse(items,now=NOW,client=c)
    assert not c.requests


def test_provider_error_fails_closed_not_partial():
    class Dead:
        def get(self,*a,**k):
            raise TimeoutError("Source unavailable")
    with pytest.raises(TimeoutError):
        review_official_building_landuse([event()],now=NOW,client=Dead())


def test_oti_footprint_multi_rows_at_exact_provider_limit_do_not_imply_unique():
    c=Client(footprints=[footprint() for _ in range(120)])
    with pytest.raises(ValueError,match="TRUNCATED_PROPERTY_SOURCE_RESULT"):
        review_official_building_landuse([event()],now=NOW,client=c)


def test_existing_property_intelligence_consumes_only_sanitised_reference_counts(
    tmp_path
):
    from empire_os.property_source_evidence_runtime import (
        FILENAME,load_property_reference_summary,
    )
    from empire_os.vertical_intelligence_runtime import build_property_intelligence_runtime
    from empire_os.source_intelligence_handoff import build_source_intelligence_handoffs
    p=tmp_path/FILENAME
    p.parent.mkdir(parents=True)
    out=review_official_building_landuse([event()],now=NOW,client=Client())
    p.write_text(json.dumps(out))
    summary=load_property_reference_summary(tmp_path,now=NOW)
    assert summary["status"]=="OFFICIAL_SOURCE_REFERENCES_REVIEWED"
    assert summary["three_agency_bin_bbl_reference_match_count"]==1
    assert summary["industrial_manufacturing_tax_lot_context_count"]==1
    assert summary["warehouse_operation_verified_count"]==0
    assert summary["source_reference_only"] is True
    projection=build_property_intelligence_runtime(tmp_path)
    assert projection["opportunity_count"] is None
    assert projection["three_agency_source_reference_review"]["reviewed_permit_event_count"]==1
    assert projection["source_reference_matches_not_extra_properties"] is True
    dispatch=build_source_intelligence_handoffs(tmp_path,now=NOW)
    routes={r["lane"]:r for r in dispatch["routes"]}
    assert routes["property"]["counts"]["tri_agency_bin_bbl_reference_match_count"]==1
    assert routes["warehouse"]["counts"]["industrial_manufacturing_lot_context_only_count"]==1
    assert routes["warehouse"]["counts"]["warehouse_operation_verified_count"]==0
    assert routes["warehouse"]["counts"]["verified_warehouse_opportunity_count"] is None
    assert "NYC DOB NOW Permit" not in json.dumps(dispatch)


def test_private_read_model_rejects_fabricated_industrial_match(tmp_path):
    from empire_os.property_source_evidence_runtime import FILENAME,load_property_reference_summary
    source=review_official_building_landuse([event()],now=NOW,client=Client())
    path=tmp_path/FILENAME;path.parent.mkdir(parents=True)
    source["diagnostics"][0]["building_tax_lot_evidence_state"]="DCP_LOT_ONLY_BIN_UNCONFIRMED"
    path.write_text(json.dumps(source))
    assert load_property_reference_summary(tmp_path,now=NOW)["status"]=="UNTRUSTED_REVIEW_FILE"


def test_missing_or_stale_private_review_never_claims_revenue(tmp_path):
    from empire_os.property_source_evidence_runtime import FILENAME,load_property_reference_summary
    assert load_property_reference_summary(tmp_path,now=NOW)["status"]=="NO_REVIEW_FILE"
    out=review_official_building_landuse([event()],now=NOW,client=Client())
    p=tmp_path/FILENAME;p.parent.mkdir(parents=True)
    p.write_text(json.dumps(out))
    older=NOW.replace(day=21)
    x=load_property_reference_summary(tmp_path,now=older)
    assert x["status"]=="STALE_SOURCE_REVIEW"
    assert x["verified_property_opportunity_count"] is None


def test_mappluto_condo_billing_lot_resolves_non_base_building_reference():
    # Per official NYC OTI metadata, MAPPLUTO_BBL is the PLUTO join key,
    # while BASE_BBL is the footprint's underlying physical tax lot.
    c=Client(footprints=[footprint(
        bbl="3002690001", mappluto_bbl="3002697501")])
    report=review_official_building_landuse([event()],now=NOW,client=c)
    row=report["diagnostics"][0]
    assert row["building_tax_lot_evidence_state"]=="TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH"
    assert row["reference_match_basis"]=="MAPPLUTO_BILLING_LOT"
    assert row["footprint_base_bbl"]=="3002690001"
    assert row["footprint_mappluto_bbl"]=="3002697501"
    assert row["industrial_tax_lot_context_corroborated"] is True
    assert row["warehouse_operation_verified"] is False
    assert report["event_level_join_status_counts"]=={
        "TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH":1
    }


def test_explicit_mappluto_join_mismatch_is_not_overridden_by_base_lot():
    c=Client(footprints=[footprint(
        bbl="3002697501", mappluto_bbl="3002690001")])
    x=review_official_building_landuse([event()],now=NOW,client=c)
    row=x["diagnostics"][0]
    assert row["building_tax_lot_evidence_state"]=="BUILDING_TAX_LOT_CONFLICT"
    assert row["industrial_tax_lot_context_corroborated"] is False


def test_different_base_and_mappluto_bbl_are_both_unmatched():
    c=Client(footprints=[footprint(
        bbl="3002690001", mappluto_bbl="3002690002")])
    x=review_official_building_landuse([event()],now=NOW,client=c)
    assert x["diagnostics"][0]["building_tax_lot_evidence_state"]=="BUILDING_TAX_LOT_CONFLICT"
