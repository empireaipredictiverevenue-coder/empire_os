"""Deterministic OBSERVE-only geography. Intersection is exposure, never damage.

Coordinates are WGS84 lon/lat. Simple polygons use planar lon/lat predicates;
antimeridian/polar polygons are rejected. No area or polygon-distance claims.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from itertools import islice
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Mapping

from empire_os.real_world_event_intelligence import (
    AUTHORITY_FIELDS, canonical_evidence_hash, source_timestamp,
    replay_source_evidence, assess_event_truth,
)

SCHEMA_VERSION = "empire.exposure_graph.v1"
MAX_RECORDS = 100
MAX_VERTICES = 256


class SpatialPrecision(str, Enum):
    EXACT_GEOMETRY = "EXACT_GEOMETRY"
    SOURCE_GEOMETRY = "SOURCE_GEOMETRY"
    ADMIN_AREA = "ADMIN_AREA"
    POINT = "POINT"
    BOUNDING_REGION = "BOUNDING_REGION"
    TEXT_AREA_ONLY = "TEXT_AREA_ONLY"
    UNKNOWN = "UNKNOWN"


class SubjectType(str, Enum):
    PROPERTY = "property"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    ROAD = "road"
    UTILITY = "utility"
    FACILITY = "facility"
    TERRITORY = "territory"
    OTHER = "other"


def normalized(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {f.name: normalized(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (tuple, list)):
        return [normalized(v) for v in value]
    if isinstance(value, Mapping):
        return {k: normalized(v) for k, v in value.items()}
    return value


def digest(value):
    def identity(item):
        if isinstance(item, dict):
            result = {k: identity(v) for k, v in item.items()}
            if "retained_source_json" in result:
                retained = json.loads(result["retained_source_json"])
                # Re-fetching a canonical source record is not new evidence.
                if retained.get("source_truth") == "OBSERVED_SOURCE_RECORD":
                    retained.pop("retrieved_at", None)
                result["retained_source_json"] = retained
            return result
        if isinstance(item, list):
            return [identity(v) for v in item]
        return item
    return canonical_evidence_hash(identity(normalized(value)))


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("invalid_required_text")
    return value.strip()


def confidence(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("invalid_confidence")
    return value


@dataclass(frozen=True, kw_only=True)
class ObserveOnly:
    execution_authority: str = "none"
    outreach_authority: str = "none"
    traffic_authority: str = "none"
    calls_authority: str = "none"
    commercial_authority: str = "none"
    payment_authority: str = "none"
    revenue_recognition_authority: str = "none"

    def __post_init__(self):
        if any(getattr(self, k) != "none" for k in AUTHORITY_FIELDS):
            raise ValueError("authority_forbidden")


def _point(p):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        raise ValueError("invalid_coordinate")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in p):
        raise ValueError("invalid_coordinate")
    x, y = map(float, p)
    if not -180 <= x <= 180 or not -90 <= y <= 90:
        raise ValueError("invalid_coordinate")
    return (x, y)


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _on(a, b, p):
    return _cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _segments(a, b, c, d):
    return (_cross(a,b,c)*_cross(a,b,d) < 0 and _cross(c,d,a)*_cross(c,d,b) < 0) or any((_on(a,b,c), _on(a,b,d), _on(c,d,a), _on(c,d,b)))


@dataclass(frozen=True)
class SpatialLocation:
    precision: SpatialPrecision
    geometry_type: str
    coordinates: tuple = ()
    area_description: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "precision", SpatialPrecision(self.precision))
        if self.area_description is not None:
            object.__setattr__(self, "area_description", text(self.area_description))
        if self.geometry_type == "None":
            if self.coordinates or self.precision not in (SpatialPrecision.TEXT_AREA_ONLY, SpatialPrecision.ADMIN_AREA, SpatialPrecision.UNKNOWN):
                raise ValueError("precision_geometry_mismatch")
            if self.precision != SpatialPrecision.UNKNOWN and not self.area_description:
                raise ValueError("area_description_required")
            object.__setattr__(self, "coordinates", ())
            return
        if self.precision in (SpatialPrecision.TEXT_AREA_ONLY, SpatialPrecision.UNKNOWN):
            raise ValueError("precision_geometry_mismatch")
        if self.geometry_type == "Point":
            object.__setattr__(self, "coordinates", _point(self.coordinates))
            return
        if self.geometry_type != "Polygon" or self.precision == SpatialPrecision.POINT:
            raise ValueError("unsupported_geometry")
        rings = self.coordinates
        if len(rings) != 1 or not 4 <= len(rings[0]) <= MAX_VERTICES:
            raise ValueError("unsupported_polygon")
        ring = tuple(_point(p) for p in rings[0])
        if ring[0] != ring[-1] or len(set(ring[:-1])) != len(ring)-1:
            raise ValueError("invalid_ring")
        if max(p[0] for p in ring)-min(p[0] for p in ring) >= 180 or any(abs(p[1]) == 90 for p in ring):
            raise ValueError("unsupported_geographic_span")
        vertices = ring[:-1]
        for i, b in enumerate(vertices):
            a, c = vertices[i-1], vertices[(i+1) % len(vertices)]
            if _cross(a,b,c) == 0 and not _on(a,c,b):
                raise ValueError("overlapping_adjacent_edges")
        edges = list(zip(ring, ring[1:]))
        if sum(a[0]*b[1]-b[0]*a[1] for a,b in edges) == 0:
            raise ValueError("degenerate_polygon")
        for i, (a,b) in enumerate(edges):
            for j, (c,d) in enumerate(edges):
                if j > i+1 and (i,j) != (0,len(edges)-1) and _segments(a,b,c,d):
                    raise ValueError("self_intersecting_polygon")
        object.__setattr__(self, "coordinates", (ring,))


def location_from_row(row):
    return SpatialLocation(SpatialPrecision(row["precision"]), row["geometry_type"], row.get("coordinates", ()), row.get("area_description"))


@dataclass(frozen=True)
class FootprintEvidence(ObserveOnly):
    source: str
    source_record_id: str | None
    observed_at: datetime
    evidence_refs: tuple[str, ...]
    source_truth: str
    retained_source_json: str
    confidence: float | None = None

    def __post_init__(self):
        super().__post_init__()
        text(self.source)
        if self.source_record_id is not None:
            text(self.source_record_id)
        object.__setattr__(self, "observed_at", source_timestamp(self.observed_at))
        if not isinstance(self.evidence_refs, (tuple, list)) or len(self.evidence_refs) > 33:
            raise ValueError("invalid_evidence_refs")
        refs = tuple(sorted(set(text(r) for r in self.evidence_refs)))
        if not refs or len(refs) > 33:
            raise ValueError("invalid_evidence_refs")
        object.__setattr__(self, "evidence_refs", refs)
        text(self.source_truth)
        confidence(self.confidence)
        if not isinstance(self.retained_source_json, str) or len(self.retained_source_json) > 32768:
            raise ValueError("evidence_size_limit")
        payload = json.loads(self.retained_source_json)
        if not isinstance(payload, dict) or not payload:
            raise ValueError("retained_evidence_required")
        if self.source == "nws_alert":
            source = replay_source_evidence(payload)
            if source.source_record_id != self.source_record_id or source.source != self.source or source.source_truth.value != self.source_truth:
                raise ValueError("source_lineage_mismatch")
        object.__setattr__(self, "retained_source_json", json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False))

    @property
    def evidence_hash(self):
        return digest(self)


@dataclass(frozen=True)
class GeographicFootprint(ObserveOnly):
    tenant_id: str
    event_id: str
    location: SpatialLocation
    evidence: FootprintEvidence
    valid_from: datetime
    valid_until: datetime | None
    derivation_method: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        super().__post_init__()
        text(self.tenant_id); text(self.event_id); text(self.derivation_method)
        if not isinstance(self.location, SpatialLocation) or not isinstance(self.evidence, FootprintEvidence):
            raise ValueError("invalid_typed_evidence")
        object.__setattr__(self, "valid_from", source_timestamp(self.valid_from))
        object.__setattr__(self, "valid_until", source_timestamp(self.valid_until, required=False))
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("invalid_validity_window")
        source = replay_source_evidence(json.loads(self.evidence.retained_source_json))
        if (self.event_id != assess_event_truth((source,)).event_id
                or source.source != self.evidence.source
                or source.source_record_id != self.evidence.source_record_id
                or source.source_truth.value != self.evidence.source_truth
                or tuple(sorted(source.evidence_refs)) != self.evidence.evidence_refs):
            raise ValueError("event_lineage_mismatch")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid_schema")

    @property
    def footprint_id(self):
        return digest(self)

    @property
    def evidence_hash(self):
        return digest({"location": self.location, "evidence": self.evidence,
                       "derivation_method": self.derivation_method})


@dataclass(frozen=True)
class ExposedSubject(ObserveOnly):
    tenant_id: str
    subject_id: str
    subject_type: SubjectType
    location: SpatialLocation
    evidence: FootprintEvidence

    def __post_init__(self):
        super().__post_init__()
        text(self.tenant_id); text(self.subject_id)
        object.__setattr__(self, "subject_type", SubjectType(self.subject_type))
        if not isinstance(self.location, SpatialLocation) or not isinstance(self.evidence, FootprintEvidence):
            raise ValueError("invalid_typed_evidence")

    @property
    def observation_id(self):
        return digest(self)


def _inside(p, ring):
    inside = False
    for a, b in zip(ring, ring[1:]):
        if _on(a,b,p):
            return True
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside


def spatial_facts(a, b):
    """Return only supported predicates; null distance is not zero."""
    if "None" in (a.geometry_type, b.geometry_type):
        return None
    if a.geometry_type == b.geometry_type == "Point":
        lon1,lat1,lon2,lat2 = map(math.radians, (*a.coordinates, *b.coordinates))
        h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
        return a.coordinates == b.coordinates, 6371008.8*2*math.asin(math.sqrt(min(1., max(0.,h))))
    if a.geometry_type == "Point":
        return _inside(a.coordinates,b.coordinates[0]), None
    if b.geometry_type == "Point":
        return _inside(b.coordinates,a.coordinates[0]), None
    ar, br = a.coordinates[0], b.coordinates[0]
    return (any(_segments(x,y,z,w) for x,y in zip(ar,ar[1:]) for z,w in zip(br,br[1:])) or _inside(ar[0],br) or _inside(br[0],ar)), None


@dataclass(frozen=True)
class ExposureRelationship(ObserveOnly):
    tenant_id: str
    event_id: str
    footprint_id: str
    subject_id: str
    subject_observation_id: str
    relationship_type: str
    spatial_precision: tuple[SpatialPrecision, SpatialPrecision]
    intersects: bool
    distance_m: float | None
    confidence: float | None
    evidence_refs: tuple[str, ...]
    derived_at: datetime

    def __post_init__(self):
        super().__post_init__()
        if self.relationship_type not in ("EXPOSED", "POTENTIALLY_EXPOSED") or self.intersects is not True:
            raise ValueError("invalid_exposure")
        for name in ("tenant_id", "event_id", "footprint_id", "subject_id", "subject_observation_id"):
            text(getattr(self, name))
        object.__setattr__(self, "derived_at", source_timestamp(self.derived_at))
        object.__setattr__(self, "spatial_precision", tuple(SpatialPrecision(p) for p in self.spatial_precision))
        object.__setattr__(self, "evidence_refs", tuple(text(r) for r in self.evidence_refs))
        if len(self.spatial_precision) != 2 or len(self.evidence_refs) != 2:
            raise ValueError("invalid_relationship_lineage")
        if self.distance_m is not None and (not math.isfinite(self.distance_m) or self.distance_m < 0):
            raise ValueError("invalid_distance")
        confidence(self.confidence)

    @property
    def relationship_id(self):
        return digest(self)


@dataclass(frozen=True)
class ExposureGraph(ObserveOnly):
    footprints: tuple[GeographicFootprint, ...]
    subjects: tuple[ExposedSubject, ...]
    relationships: tuple[ExposureRelationship, ...]
    location_conflicts: tuple[tuple[str, str], ...]
    rejections: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        super().__post_init__()
        for name, cls, limit in (("footprints", GeographicFootprint, MAX_RECORDS),
                                 ("subjects", ExposedSubject, MAX_RECORDS),
                                 ("relationships", ExposureRelationship, MAX_RECORDS**2)):
            values = tuple(getattr(self, name))
            if len(values) > limit or any(not isinstance(v, cls) for v in values):
                raise ValueError("invalid_graph_records")
            object.__setattr__(self, name, values)
        if self.schema_version != SCHEMA_VERSION or len(self.rejections) > 100 or len(self.location_conflicts) > MAX_RECORDS:
            raise ValueError("invalid_graph_metadata")
        object.__setattr__(self, "rejections", tuple(text(v) for v in self.rejections))
        object.__setattr__(self, "location_conflicts", tuple(tuple(text(v) for v in pair) for pair in self.location_conflicts))
        fps = {fp.footprint_id: fp for fp in self.footprints}
        subs = {s.observation_id: s for s in self.subjects}
        for edge in self.relationships:
            fp, sub = fps.get(edge.footprint_id), subs.get(edge.subject_observation_id)
            if (fp is None or sub is None or edge.tenant_id != fp.tenant_id
                    or edge.tenant_id != sub.tenant_id or edge.event_id != fp.event_id
                    or edge.subject_id != sub.subject_id
                    or edge.evidence_refs != (fp.evidence_hash, sub.evidence.evidence_hash)):
                raise ValueError("invalid_graph_lineage")

    def as_dict(self):
        result = normalized(self)
        for row, fp in zip(result["footprints"], self.footprints):
            row.update(footprint_id=fp.footprint_id, evidence_hash=fp.evidence_hash)
        for row, subject in zip(result["subjects"], self.subjects):
            row["observation_id"] = subject.observation_id
        for row, rel in zip(result["relationships"], self.relationships):
            row["relationship_id"] = rel.relationship_id
        return result


def _evidence(row):
    data = dict(row)
    data["observed_at"] = source_timestamp(data["observed_at"])
    return FootprintEvidence(**data)


def footprint_from_row(row):
    data = {k:v for k,v in row.items() if k not in ("footprint_id", "evidence_hash")}
    data.update(location=location_from_row(data["location"]), evidence=_evidence(data["evidence"]))
    result = GeographicFootprint(**data)
    if row.get("footprint_id", result.footprint_id) != result.footprint_id or row.get("evidence_hash", result.evidence_hash) != result.evidence_hash:
        raise ValueError("footprint_hash_mismatch")
    return result


def subject_from_row(row):
    data = {k:v for k,v in row.items() if k != "observation_id"}
    data.update(location=location_from_row(data["location"]), evidence=_evidence(data["evidence"]))
    result = ExposedSubject(**data)
    if row.get("observation_id", result.observation_id) != result.observation_id:
        raise ValueError("subject_hash_mismatch")
    return result


def build_exposure_graph(footprints=(), subjects=()):
    rejections = []
    def collect(rows, cls, parser):
        batch = list(islice(iter(rows), MAX_RECORDS+1))
        if len(batch) > MAX_RECORDS:
            rejections.append(cls.__name__ + ":batch_limit")
            return ()
        found = {}
        for row in batch:
            try:
                obj = row if isinstance(row, cls) else parser(row)
                key = digest(obj)
                old = found.get(key)
                if old is None or json.dumps(normalized(obj), sort_keys=True) < json.dumps(normalized(old), sort_keys=True):
                    found[key] = obj
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
                rejections.append(cls.__name__ + ":invalid_record")
        return tuple(found[k] for k in sorted(found))
    fps = collect(footprints, GeographicFootprint, footprint_from_row)
    subs = collect(subjects, ExposedSubject, subject_from_row)
    locations = {}
    for sub in subs:
        locations.setdefault((sub.tenant_id,sub.subject_id), set()).add(digest(sub.location))
    conflicts = tuple(sorted(k for k,v in locations.items() if len(v)>1))
    edges = []
    for fp in fps:
        for sub in subs:
            if fp.tenant_id != sub.tenant_id:
                continue
            facts = spatial_facts(fp.location,sub.location)
            if facts is None or not facts[0]:
                continue
            precise = {SpatialPrecision.EXACT_GEOMETRY, SpatialPrecision.SOURCE_GEOMETRY, SpatialPrecision.POINT}
            kind = "EXPOSED" if (fp.location.precision in precise and sub.location.precision in precise
                                 and (sub.tenant_id, sub.subject_id) not in conflicts) else "POTENTIALLY_EXPOSED"
            confs = (fp.evidence.confidence, sub.evidence.confidence)
            edges.append(ExposureRelationship(fp.tenant_id,fp.event_id,fp.footprint_id,sub.subject_id,sub.observation_id,kind,
                (fp.location.precision,sub.location.precision),True,facts[1],None if None in confs else min(confs),
                (fp.evidence_hash,sub.evidence.evidence_hash),max(fp.evidence.observed_at,sub.evidence.observed_at)))
    return ExposureGraph(fps,subs,tuple(sorted(edges,key=lambda e:e.relationship_id)),conflicts,tuple(sorted(rejections)[:100]))


def write_exposure_snapshot(path: Path, graph: ExposureGraph, *, generated_at: datetime):
    """Write a bounded normalized replayable snapshot; generation is not evidence."""
    if max(len(graph.footprints),len(graph.subjects)) > MAX_RECORDS or len(graph.relationships)>MAX_RECORDS**2:
        raise ValueError("snapshot_limit")
    payload = graph.as_dict()
    payload["generated_at"] = normalized(source_timestamp(generated_at))
    encoded = json.dumps(payload,sort_keys=True,separators=(",", ":"),allow_nan=False)+"\n"
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent,prefix=".exposure-")
    try:
        with os.fdopen(fd,"w") as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp,path)
        fd = os.open(path.parent,os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path
