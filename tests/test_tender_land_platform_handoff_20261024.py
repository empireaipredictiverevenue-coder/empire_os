"""Tender => canonical Source Intelligence review-only handoff tests."""
from __future__ import annotations

from datetime import datetime,timezone,timedelta
from pathlib import Path
import copy
import json
import os
import stat
import pytest

from empire_os.tender_land_gis_evidence import SOURCES,SOURCE_IDS,BASE,SAMPLE_OUTPUT
from empire_os.tender_land_platform_handoff_20261024 import (
    SCHEMA,OUTPUT,prepare_handoff,write_private_handoff,
)

NOW=datetime(2026,10,24,18,tzinfo=timezone.utc)


def source_fixture():
    layers=[]
    for key in SOURCE_IDS:
        d=SOURCES[key]
        features=[]
        for n in range(3):
            object_id=(100 if key=="ROI_GZT" else 200 if key=="ROI_PLANNING_SITES" else 300)+n
            coordinates=[[[[-6.1,54.0],[-6.1001,54.0],[-6.1,54.0001],[-6.1,54.0]]]]
            features.append({
                "type":"Feature","id":object_id,
                "geometry":{"type":"MultiPolygon","coordinates":coordinates},
                "properties":{"OBJECTID":object_id},
            })
        layers.append({
            "source_id":key,"status":"OFFICIAL_GIS_SAMPLE_OBSERVED_NOT_PARCEL_SCREENING",
            "licence":d["licence"],
            "catalogue":d["catalogue"],
            "attribution":d["attribution"],
            "source_service":d["service"],
            "source_response_sha256":"f"*64,
            "feature_count":3,
            "complete_coverage":False,
            "sample_geojson":{"type":"FeatureCollection","features":features},
        })
    return {
        "schema_version":"empire.tender_ca18567_official_gis_evidence.v1",
        "status":"THREE_OFFICIAL_GIS_LAYER_SAMPLES_OBSERVED_REVIEW_ONLY",
        "observed_at_utc":NOW.isoformat(),
        "site_intersections_performed":False,
        "samples_are_not_exhaustive":True,
        "bid_authorized":False,
        "land_title_checked":False,
        "layer_count":3,
        "layers":layers,
    }


def test_reuses_existing_source_intelligence_contract_and_avoids_claims():
    r=prepare_handoff(source_fixture(),assessed_at=NOW)
    assert r["schema_version"]==SCHEMA
    assert r["platform"]=="EXISTING_EMPIREOS_SOURCE_INTELLIGENCE_DATA_EXCHANGE"
    assert r["handoff_kind"]=="REVIEW_ONLY_SOURCE_ADMISSION_CANDIDATE"
    assert r["sample_record_count"]==9
    assert len(r["source_contracts"])==3
    assert {x["country_code"] for x in r["source_contracts"]}=={"IE","GB"}
    assert all(x["raw_resale_allowed"] is False for x in r["source_contracts"])
    assert all(x["provenance_strength"]==0 for x in r["source_contracts"])
    assert all("Applicant" not in "".join(x["published_attributes"]) for x in r["records"])
    assert r["canonical_empiredb_ingestion_performed"] is False
    assert r["existing_data_exchange_owner_acceptance"] is False
    assert r["customer_delivery_enabled"] is False
    assert r["rights_reviewer_approval"] is False
    assert r["revenue_verified"] is False
    assert all(x["canonical_land_entity_id"] is None for x in r["records"])
    assert all(x["buyer_intent_verified"] is False for x in r["records"])
    assert all(x["title_verified"] is False for x in r["records"])
    assert all("geometry" not in x for x in r["records"])
    assert all("geometry_sha256" in x for x in r["records"])
    assert len({x["source_record_key"] for x in r["records"]})==9
    assert all(x["record_kind"] in {"zoning_polygon","planning_application_polygon","scheduled_monument_zone"} for x in r["records"])


def test_deterministic_source_keys_and_observation_hashes():
    obj=source_fixture()
    a=prepare_handoff(obj,assessed_at=NOW)
    b=prepare_handoff(obj,assessed_at=NOW+timedelta(minutes=20))
    assert [x["source_record_key"] for x in a["records"]]==[x["source_record_key"] for x in b["records"]]
    assert [x["observation_sha256"] for x in a["records"]]==[x["observation_sha256"] for x in b["records"]]


@pytest.mark.parametrize("corrupt",[
    lambda x:x.update(status="INTEGRATED_INTO_EMPIREDB"),
    lambda x:x.update(land_title_checked=True),
    lambda x:x.update(samples_are_not_exhaustive=False),
    lambda x:x["layers"][0].update(licence="unknown"),
    lambda x:x["layers"][0].update(catalogue="https://untrusted.example"),
    lambda x:x["layers"][0].update(source_service="http://localhost:666"),
    lambda x:x["layers"][0].update(source_response_sha256="not-hash"),
    lambda x:x["layers"][0].update(complete_coverage=True),
    lambda x:x["layers"][0].update(feature_count=99),
    lambda x:x["layers"][0]["sample_geojson"]["features"][0]["properties"].update(
        {"ApplicantName":"private-person"}),
    lambda x:x["layers"][0]["sample_geojson"]["features"][0].update(id=99999),
    lambda x:x["layers"][0]["sample_geojson"]["features"][0].update(geometry=None),
    lambda x:x["layers"].append(x["layers"][0]),
    lambda x:x["layers"][0]["sample_geojson"]["features"].append(x["layers"][0]["sample_geojson"]["features"][0]),
])
def test_source_rights_identity_and_feature_reject(corrupt):
    sample=source_fixture()
    corrupt(sample)
    with pytest.raises(ValueError):
        prepare_handoff(sample,assessed_at=NOW)


def test_duplicated_source_ids_rejected():
    obj=source_fixture()
    obj["layers"][1]=copy.deepcopy(obj["layers"][0])
    with pytest.raises(ValueError):
        prepare_handoff(obj,assessed_at=NOW)


def test_stale_receipt_fails_closed():
    obj=source_fixture()
    with pytest.raises(ValueError,match="STALE_OR_FUTURE"):
        prepare_handoff(obj,assessed_at=NOW+timedelta(days=20))


def test_private_written_mode_no_db(tmp_path:Path):
    folder=tmp_path/BASE
    folder.mkdir(parents=True)
    os.chmod(folder,0o700)
    source=folder/SAMPLE_OUTPUT
    source.write_text(json.dumps(source_fixture()))
    os.chmod(source,0o600)
    r=write_private_handoff(tmp_path,now=NOW)
    assert r["sample_record_count"]==9
    p=folder/OUTPUT
    assert stat.S_IMODE(p.stat().st_mode)==0o600
    assert json.loads(p.read_text())["canonical_empiredb_ingestion_performed"] is False


def test_untrusted_private_snapshot_symlink(tmp_path:Path):
    folder=tmp_path/BASE
    folder.mkdir(parents=True)
    os.chmod(folder,0o700)
    target=tmp_path/"elsewhere.json"
    target.write_text(json.dumps(source_fixture()))
    (folder/SAMPLE_OUTPUT).symlink_to(target)
    with pytest.raises(ValueError):
        write_private_handoff(tmp_path,now=NOW)


def test_output_symlink_fails_closed(tmp_path:Path):
    folder=tmp_path/BASE
    folder.mkdir(parents=True)
    os.chmod(folder,0o700)
    source=folder/SAMPLE_OUTPUT
    source.write_text(json.dumps(source_fixture()))
    os.chmod(source,0o600)
    target=tmp_path/"protected.txt"
    target.write_text("preserve")
    (folder/OUTPUT).symlink_to(target)
    with pytest.raises(ValueError):
        write_private_handoff(tmp_path,now=NOW)
    assert target.read_text()=="preserve"
