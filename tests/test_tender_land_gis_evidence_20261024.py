"""CA18567 official GIS integration: strict bounded source and fail-closed checks."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import pytest

import empire_os.tender_land_gis_evidence as m

NOW=datetime(2026,10,24,15,0,tzinfo=timezone.utc)
ROI={"type":"Polygon","coordinates":[[
    [-6.418,54.002],[-6.415,54.002],[-6.415,54.004],[-6.418,54.002]
]]}
NI={"type":"Polygon","coordinates":[[
    [-5.851,54.644],[-5.850,54.644],[-5.850,54.645],[-5.851,54.644]
]]}


@pytest.fixture
def root(tmp_path:Path) -> Path:
    folder=tmp_path/"runtime/acquisition_research"
    folder.mkdir(parents=True,mode=0o700)
    os.chmod(folder,0o700)
    return tmp_path


def test_fixed_sources_licences():
    assert set(m.SOURCES)=={"ROI_GZT","ROI_PLANNING_SITES","NI_HED_SCHEDULED"}
    assert m.SOURCES["ROI_PLANNING_SITES"]["licence"]=="CC-BY-4.0"
    assert m.SOURCES["ROI_GZT"]["licence"]=="CC-BY-4.0"
    assert m.SOURCES["NI_HED_SCHEDULED"]["licence"]=="UK-OGL-v3"
    assert all(x["catalogue"].startswith("https://") for x in m.SOURCES.values())


def test_unknown_origin_never_called():
    with pytest.raises(ValueError,match="UNAPPROVED_GIS_ORIGIN"):
        m._fetch_json("http://localhost:9999",{})


def test_sample_not_full_cover(root,monkeypatch):
    requested=[]
    def fetch(url,params):
        requested.append((url,params))
        return {"type":"FeatureCollection","features":[
            {"type":"Feature","id":21,
             "geometry":{"type":"Polygon","coordinates":[[[-6,54],[-6.1,54],[-6,54.1],[-6,54]]]},
             "properties":{"OBJECTID":21}}
        ],"properties":{"exceededTransferLimit":True}},"a"*64
    monkeypatch.setattr(m,"_fetch_json",fetch)
    result=m.snapshot_official_layers(root,now=NOW)
    assert result["status"]=="THREE_OFFICIAL_GIS_LAYER_SAMPLES_OBSERVED_REVIEW_ONLY"
    assert result["layer_count"]==3
    assert result["site_intersections_performed"] is False
    assert result["bid_authorized"] is False
    assert result["db_writes"] is False
    assert all(x["source_truncated"] is True for x in result["layers"])
    assert requested[0][1]["where"]=="LA_NAME = 'Louth' AND CURRENT_PLAN = 1"
    assert requested[1][1]["where"]=="PlanningAuthority = 'Louth County Council'"
    assert requested[2][1]["where"]=="COUNTY = 'DOW'"
    path=root/m.BASE/m.SAMPLE_OUTPUT
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    persisted=json.loads(path.read_text())
    assert persisted["layers"][0]["sample_geojson"]["features"][0]["geometry"]["type"]=="Polygon"


def test_source_failure_does_not_claim_complete(root,monkeypatch):
    def fail(url,params):
        raise ValueError("GIS_RESPONSE_NOT_200")
    monkeypatch.setattr(m,"_fetch_json",fail)
    result=m.snapshot_official_layers(root,now=NOW)
    assert result["layer_count"]==0
    assert all(x["status"]=="SOURCE_UNAVAILABLE_NOT_CLEAR" for x in result["layers"])


def test_roi_polygon_intersection_is_not_legal_clearance(root,monkeypatch):
    called=[]
    def fetch(url,params):
        called.append(params)
        return {"type":"FeatureCollection","features":[
            {"type":"Feature","geometry":None,"properties":{"OBJECTID":1,"ZONE_GZT":"C2.1"}}
        ],"properties":{"exceededTransferLimit":False}},"0"*64
    monkeypatch.setattr(m,"_fetch_json",fetch)
    r=m.screen_unverified_parcel_geometry(root,reference="LOUTH-SYNTH-TEST",
        jurisdiction="ROI",geometry=ROI,geometry_source="SYNTHETIC UNIT TEST ONLY",now=NOW)
    assert r["status"]=="GIS_INTERSECTION_RESULT_NOT_LAND_OR_PLANNING_CLEARANCE"
    assert len(r["intersections"])==2
    assert {x["source_id"] for x in r["intersections"]}=={"ROI_GZT","ROI_PLANNING_SITES"}
    assert r["sources_observed_successfully"]==2
    assert r["parcel_boundary_legally_verified"] is False
    assert r["title_is_not_inferred_from_geometry"] is True
    assert r["land_currently_available_verified"] is False
    assert r["bid_authorized"] is False
    assert called[0]["spatialRel"]=="esriSpatialRelIntersects"
    assert called[0]["where"]=="LA_NAME = 'Louth' AND CURRENT_PLAN = 1"
    assert called[1]["where"]=="PlanningAuthority = 'Louth County Council'"
    assert stat.S_IMODE((root/m.BASE/m.SCREEN_OUTPUT).stat().st_mode)==0o600


def test_partial_roi_source_failure_cannot_be_reported_as_clear(root,monkeypatch):
    def half_fail(url,params):
        if "IrishPlanningApplications" in url:
            raise ValueError("GIS_NETWORK_OR_TRANSPORT_ERROR")
        return {"type":"FeatureCollection","features":[],"properties":{"exceededTransferLimit":False}},"c"*64
    monkeypatch.setattr(m,"_fetch_json",half_fail)
    r=m.screen_unverified_parcel_geometry(
        root,reference="LOUTH-SYNTH-FAIL",
        jurisdiction="ROI",geometry=ROI,
        geometry_source="SYNTHETIC NEGATIVE CONTROL ONLY",now=NOW
    )
    assert r["status"]=="PARTIAL_GIS_SOURCES_UNAVAILABLE_DO_NOT_INFER_CLEARANCE"
    assert r["sources_observed_successfully"]==1
    assert r["intersections"]==[]
    assert r["a_zero_hit_result_is_not_planning_clearance"] is True
    assert r["bid_authorized"] is False


def test_roi_planning_source_minimises_personal_data():
    source=m.SOURCES["ROI_PLANNING_SITES"]
    assert source["fixed_where"]=="PlanningAuthority = 'Louth County Council'"
    assert "ApplicationNumber" in source["fields"]
    assert "Applicant" not in source["fields"]
    assert "DevelopmentAddress" not in source["fields"]
    assert "DevelopmentDescription" not in source["fields"]


def test_ni_source_holds_on_service_error(root,monkeypatch):
    def fail(url,params):
        raise ValueError("GIS_NOT_JSON")
    monkeypatch.setattr(m,"_fetch_json",fail)
    r=m.screen_unverified_parcel_geometry(root,reference="DOWN-SYNTH-TEST",
        jurisdiction="NI",geometry=NI,geometry_source="SYNTHETIC UNIT TEST ONLY",now=NOW)
    assert r["status"]=="GIS_LAYER_UNAVAILABLE_DO_NOT_INFER_CLEARANCE"
    assert r["intersections"]==[]
    assert r["bid_authorized"] is False


@pytest.mark.parametrize("geometry",[
    {"type":"Point","coordinates":[-6,54]},
    {"type":"Polygon","coordinates":[[[-6,54],[-6.1,54],[-6,54.1]]]},
    {"type":"Polygon","coordinates":[[[-6,54],[-6.1,54],[-6.1,54.1],[-6,54.1],[-6,54]]]},
    {"type":"Polygon","coordinates":[[[-6,54],[-6,54],[-6,54],[-6,54]]]},
    {"type":"Polygon","coordinates":[[[500,54],[501,54],[500,55],[500,54]]]},
    {"type":"Polygon","coordinates":[[[-6,54],[-6.001,54],[-6.001,float('nan')],[-6,54]]]},
    {"type":"Polygon","coordinates":[[[-6,54],[-6.001,54],[-6.1,54.01],[-6,54]]]},
    {"type":"Polygon","coordinates":[[[-6,54],[-6,54.001],[-6,54.002],[-6,54]]]},
])
def test_bad_geometry_rejected(geometry):
    with pytest.raises(ValueError):
        m._validated_ring(geometry,"ROI")


def test_valid_ni_ring():
    ring=m._validated_ring(NI,"NI")
    assert len(ring)==4


def test_fail_on_unapproved_reference_or_blank_provenance(root,monkeypatch):
    monkeypatch.setattr(m,"_fetch_json",lambda *_: (_ for _ in ()).throw(AssertionError("should not fetch")))
    with pytest.raises(ValueError):
        m.screen_unverified_parcel_geometry(root,reference="../bad",
            jurisdiction="ROI",geometry=ROI,geometry_source="unit test",now=NOW)
    with pytest.raises(ValueError):
        m.screen_unverified_parcel_geometry(root,reference="good",
            jurisdiction="ROI",geometry=ROI,geometry_source="x",now=NOW)


def test_symlink_output_rejected(root,monkeypatch):
    victim=root/"otherfile"
    victim.write_text("unchanged")
    (root/m.BASE/m.SAMPLE_OUTPUT).symlink_to(victim)
    with pytest.raises(ValueError,match="UNSAFE_PRIVATE_GIS_OUTPUT"):
        m._save(root,m.SAMPLE_OUTPUT,m._base())
    assert victim.read_text()=="unchanged"
