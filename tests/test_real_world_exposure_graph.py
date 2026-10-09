"""Synthetic fixtures here are test-only, never acquired subjects."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import math
import pytest

from empire_os.real_world_exposure_graph import (
    SpatialPrecision as P, SpatialLocation as L, FootprintEvidence,
    GeographicFootprint, ExposedSubject, SubjectType, build_exposure_graph,
    normalized, spatial_facts, write_exposure_snapshot, footprint_from_row,
    AUTHORITY_FIELDS,
)
from empire_os.spatial_physical_adapters import footprint_from_storm_event
from empire_os.storm_predictor import StormEvent

NOW = datetime(2026,10,5,tzinfo=timezone.utc)
POLYGON = (((0,0),(2,0),(2,2),(0,2),(0,0)),)


def evidence(record="fixture"):
    return FootprintEvidence("test_source",record,NOW,("test://"+record,),"SUPPLIED_SOURCE_RECORD",json.dumps({"record":record}),.8)


def event_evidence():
    from empire_os.real_world_event_intelligence import SourceEvidence, normalized_event_evidence
    source = SourceEvidence("test_source", "event", NOW, ("test://event",), "a"*64,
                            issued_at=NOW, phenomenon="test", geographic_scope="test")
    return FootprintEvidence(source.source,source.source_record_id,NOW,source.evidence_refs,
                             source.source_truth.value,json.dumps(normalized_event_evidence(source)),.8)


def footprint():
    return GeographicFootprint("tenant","event",L(P.SOURCE_GEOMETRY,"Polygon",POLYGON),event_evidence(),NOW,NOW+timedelta(hours=1),"supplied_geometry")


def subject(point=(1,1), identity="asset", tenant="tenant"):
    return ExposedSubject(tenant,identity,SubjectType.PROPERTY,L(P.POINT,"Point",point),evidence("asset"))


def nws(geometry=None):
    return StormEvent(event_id="nws:fixture",event_type="Tornado Warning",severity=4,
        area_description="Test County",retrieved_at=NOW.isoformat(),raw={
        "sent":NOW.isoformat(),"expires":(NOW+timedelta(hours=1)).isoformat(),
        "areaDesc":"Test County","certainty":"Observed","geometry":geometry})


def test_deterministic_identity_relationship_and_dedupe():
    fp, sub = footprint(), subject()
    first = build_exposure_graph([fp],[sub])
    assert fp.footprint_id == footprint().footprint_id
    assert sub.observation_id == subject().observation_id
    assert first == build_exposure_graph([fp,fp],[sub,sub])
    assert len(first.relationships) == 1
    edge = first.relationships[0]
    assert edge.relationship_id == build_exposure_graph([footprint()],[subject()]).relationships[0].relationship_id
    assert edge.relationship_type == "EXPOSED" and edge.intersects
    assert edge.confidence == .8
    assert "damage" not in json.dumps(first.as_dict()).lower()


def test_non_intersection_empty_subjects_and_tenant_boundary():
    assert not build_exposure_graph([footprint()],[subject((3,3))]).relationships
    assert not build_exposure_graph([footprint()],[]).relationships
    assert not build_exposure_graph([footprint()],[subject(tenant="other")]).relationships


def test_distance_and_boundary():
    hit, distance = spatial_facts(L(P.POINT,"Point",(0,0)),L(P.POINT,"Point",(0,1)))
    assert not hit and distance == pytest.approx(111195.08,rel=1e-6)
    assert len(build_exposure_graph([footprint()],[subject((0,1))]).relationships) == 1
    assert build_exposure_graph([footprint()],[subject()]).relationships[0].distance_m is None


def test_polygon_intersection_and_non_intersection():
    a = footprint().location
    assert spatial_facts(a,a) == (True,None)
    b = L(P.SOURCE_GEOMETRY,"Polygon",(((3,3),(4,3),(4,4),(3,4),(3,3)),))
    assert spatial_facts(a,b) == (False,None)


def test_text_area_nws_never_damage_or_fake_geometry():
    fp = footprint_from_storm_event(nws(),tenant_id="tenant")
    assert fp.location.precision == P.TEXT_AREA_ONLY
    assert fp.location.geometry_type == "None" and fp.location.coordinates == ()
    assert json.loads(fp.evidence.retained_source_json)["physical_truth"] == "UNKNOWN"
    assert not build_exposure_graph([fp],[subject()]).relationships


def test_nws_geometry_and_lineage_replay(tmp_path):
    fp = footprint_from_storm_event(nws({"type":"Polygon","coordinates":POLYGON}),tenant_id="tenant")
    graph = build_exposure_graph([fp],[subject()])
    path = write_exposure_snapshot(tmp_path/"graph.json",graph,generated_at=NOW+timedelta(days=1))
    row = json.loads(path.read_text())
    assert row["generated_at"] != row["footprints"][0]["evidence"]["observed_at"]
    assert graph == build_exposure_graph(row["footprints"],row["subjects"])
    assert graph.relationships[0].evidence_refs == (fp.evidence_hash,subject().evidence.evidence_hash)
    assert json.loads(fp.evidence.retained_source_json)["source_record_id"] == fp.event_id
    assert not list(tmp_path.glob(".exposure-*"))


def test_conflicting_locations_preserved_stable_order():
    a,b = subject(),subject((4,4))
    graph = build_exposure_graph([footprint()],[a,b])
    assert graph == build_exposure_graph([footprint()],[b,a])
    assert graph.location_conflicts == (("tenant","asset"),)
    assert len(graph.subjects) == 2 and len(graph.relationships) == 1


@pytest.mark.parametrize("point", [(181,0),(0,91),(-181,0),(0,-91),(math.nan,0),(0,math.inf),(True,0),(1,),"bad"])
def test_bad_coordinates_rejected(point):
    with pytest.raises(ValueError):
        subject(point)


@pytest.mark.parametrize("ring", [(((0,0),(1,1),(0,1),(1,0),(0,0)),), (((0,0),(1,1),(2,2),(0,0)),), (((0,0),(1,0),(1,1)),)])
def test_malformed_geometry_isolated(ring):
    row = normalized(footprint())
    row["location"]["coordinates"] = ring
    graph = build_exposure_graph([row,normalized(footprint())],[subject()])
    assert len(graph.footprints) == 1 and len(graph.relationships) == 1
    assert graph.rejections == ("GeographicFootprint:invalid_record",)


@pytest.mark.parametrize("field,value", [("valid_from",NOW.replace(tzinfo=None)),("valid_until",NOW-timedelta(seconds=1)),("tenant_id",""),("event_id","")])
def test_invalid_footprint_fields(field,value):
    with pytest.raises(ValueError):
        replace(footprint(),**{field:value})


def test_naive_observation_rejected():
    with pytest.raises(ValueError):
        replace(evidence(),observed_at=NOW.replace(tzinfo=None))


@pytest.mark.parametrize("field", AUTHORITY_FIELDS)
def test_authority_none_on_every_output(field):
    graph = build_exposure_graph([footprint()],[subject()])
    for obj in (evidence(),footprint(),subject(),graph,graph.relationships[0]):
        assert getattr(obj,field) == "none"
        with pytest.raises(ValueError):
            replace(obj,**{field:"live"})


def test_tamper_and_malformed_batch_and_limits():
    row = build_exposure_graph([footprint()],[]).as_dict()["footprints"][0]
    row["event_id"] = "tampered"
    with pytest.raises(ValueError):
        footprint_from_row(row)
    graph = build_exposure_graph([None,[],{},footprint()],[{},subject()])
    assert len(graph.relationships) == 1 and len(graph.rejections) == 4
    assert not build_exposure_graph([footprint()]*101,[]).footprints


def test_immutable_nested_data():
    coords = [1,1]
    sub = subject(coords)
    coords[0] = 50
    assert sub.location.coordinates == (1,1)


def test_storm_runtime_materializes_only_supplied_subjects():
    from empire_os.storm_service import StormService
    from empire_os.storm_intelligence_runtime import build_storm_intelligence_runtime
    row = StormService._canonical_event_row(nws())
    result = build_storm_intelligence_runtime(events=[row],now=NOW)
    graph = result["exposure_graph"]
    assert len(graph["footprints"]) == 1
    assert not graph["subjects"] and not graph["relationships"]
    assert graph["footprints"][0]["location"]["precision"] == "TEXT_AREA_ONLY"


def test_retrieval_does_not_manufacture_evidence():
    a = nws()
    b = nws()
    b.retrieved_at = (NOW+timedelta(minutes=1)).isoformat()
    fpa = footprint_from_storm_event(a,tenant_id="tenant")
    fpb = footprint_from_storm_event(b,tenant_id="tenant")
    assert fpa.footprint_id == fpb.footprint_id
    graph = build_exposure_graph([fpa,fpb],[])
    assert len(graph.footprints) == 1
    assert graph == build_exposure_graph([fpb,fpa],[])


def test_invalid_geometry_cannot_poison_storm_service_batch(monkeypatch,tmp_path):
    from empire_os.storm_service import StormService
    import empire_os.storm_service as service_module
    from types import SimpleNamespace
    bad = nws({"type":"Polygon"})
    good = nws()
    service = object.__new__(StormService)
    service.predictor = SimpleNamespace(scan=lambda: [],events=[bad,good],rejections=[])
    service.metrics = {"scans":0}
    monkeypatch.setattr(service_module,"REPO_ROOT",tmp_path)
    _, snapshot = service._scan_and_materialize()
    assert len(snapshot["exposure_graph"]["footprints"]) == 1


def test_geometry_revisions_survive_storm_service_dedupe(monkeypatch,tmp_path):
    from empire_os.storm_service import StormService
    import empire_os.storm_service as service_module
    from types import SimpleNamespace
    a,b = nws(),nws({"type":"Polygon","coordinates":POLYGON})
    service = object.__new__(StormService)
    service.predictor = SimpleNamespace(scan=lambda: [],events=[a,b],rejections=[])
    service.metrics = {"scans":0}
    monkeypatch.setattr(service_module,"REPO_ROOT",tmp_path)
    _, snapshot = service._scan_and_materialize()
    assert len(snapshot["exposure_graph"]["footprints"]) == 2


def test_runtime_parent_tenant_binding():
    from empire_os.storm_service import StormService
    from empire_os.storm_intelligence_runtime import build_storm_intelligence_runtime
    row = StormService._canonical_event_row(nws())
    row["geographic_footprint"]["tenant_id"] = "foreign"
    graph = build_storm_intelligence_runtime(events=[row],now=NOW)["exposure_graph"]
    assert not graph["footprints"] and graph["rejections"]


def test_unsupported_geometry_and_precision_fail_closed():
    for location in [dict(precision="TEXT_AREA_ONLY",geometry_type="Point",coordinates=[0,0]),
                     dict(precision="POINT",geometry_type="Polygon",coordinates=POLYGON),
                     dict(precision="SOURCE_GEOMETRY",geometry_type="MultiPolygon",coordinates=[POLYGON])]:
        row = normalized(footprint())
        row["location"] = location
        assert build_exposure_graph([row],[]).rejections


def test_atomic_write_failure_preserves_previous_snapshot(tmp_path,monkeypatch):
    import empire_os.real_world_exposure_graph as module
    path = tmp_path/"graph.json"
    graph = build_exposure_graph([footprint()],[])
    write_exposure_snapshot(path,graph,generated_at=NOW)
    before = path.read_bytes()
    def fail(*args):
        raise OSError("test-only replace failure")
    monkeypatch.setattr(module.os,"replace",fail)
    with pytest.raises(OSError):
        write_exposure_snapshot(path,graph,generated_at=NOW+timedelta(hours=1))
    assert path.read_bytes() == before and not list(tmp_path.glob(".exposure-*"))
