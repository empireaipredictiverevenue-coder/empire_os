"""CA18567 => canonical EmpireOS Source Intelligence review-only handoff.

First-party Empire AI source evidence, not a second data platform. The output is
a source-admission candidate for the existing Source Intelligence / Data Exchange
owners; it grants no canonical EmpireDB write, entity match, buyer intent or
commercial distribution authority. Inputs are government GIS sample receipts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

from empire_os.source_intelligence import SourceContract
from empire_os.tender_land_gis_evidence import (
    BASE, SAMPLE_OUTPUT, SOURCE_IDS, SOURCES, _save, _private_path,
)

OUTPUT = "ca18567_data_platform_source_handoff_latest.json"
SCHEMA = "empire.ca18567.source_intelligence_handoff.v1"
SOURCE_KEYS = {
    "ROI_GZT": "ie_myplan_current_zoning",
    "ROI_PLANNING_SITES": "ie_national_planning_applications",
    "NI_HED_SCHEDULED": "gb_ni_hed_scheduled_monuments",
}
RECORD_KINDS = {
    "ROI_GZT": "zoning_polygon",
    "ROI_PLANNING_SITES": "planning_application_polygon",
    "NI_HED_SCHEDULED": "scheduled_monument_zone",
}
MAX_AGE = timedelta(days=14)
HASH = re.compile(r"^[a-f0-9]{64}$")


def _hash(payload: Any) -> str:
    return sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        allow_nan=False, ensure_ascii=True,
    ).encode("utf-8")).hexdigest()


def _read_snapshot(root: Path) -> dict[str, Any]:
    path = _private_path(root,SAMPLE_OUTPUT)
    st = path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(st.st_mode)
        or st.st_uid != os.geteuid() or st.st_nlink != 1
        or stat.S_IMODE(st.st_mode) != 0o600
        or not 200 <= st.st_size <= 200000):
        raise ValueError("PRIVATE_SOURCE_SNAPSHOT_REQUIRED")
    with path.open("rb") as f:
        opened = os.fstat(f.fileno())
        if (opened.st_ino != st.st_ino
            or opened.st_dev != st.st_dev
            or opened.st_size != st.st_size):
            raise ValueError("SOURCE_SNAPSHOT_CHANGED")
        obj = json.load(f)
    if not isinstance(obj,dict):
        raise ValueError("SOURCE_SNAPSHOT_NOT_MAPPING")
    return obj


def _time(value: Any, now: datetime) -> datetime:
    if not isinstance(value,str):
        raise ValueError("MISSING_SOURCE_TIMESTAMP")
    try:
        dt = datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("INVALID_SOURCE_TIMESTAMP") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("SOURCE_TIME_MUST_BE_AWARE")
    dt = dt.astimezone(timezone.utc)
    if dt > now or now - dt > MAX_AGE:
        raise ValueError("STALE_OR_FUTURE_SOURCE_RECEIPT")
    return dt


def _source_contract(source_id: str) -> dict[str, Any]:
    source = SOURCES[source_id]
    item = SourceContract(
        source_id=SOURCE_KEYS[source_id],
        authority=source["attribution"],
        country_code="IE" if source["jurisdiction"] == "ROI" else "GB",
        source_type="official_geospatial_layer",
        access_method="arcgis_public_feature_service",
        url=source["service"],
        niches=("land", "property", "planning", "investment_research"),
        roles=("source_geometry_digest", RECORD_KINDS[source_id], "research_screening"),
        freshness="snapshot_observed_unverified_publisher_update",
        licence=source["licence"],
        production_status="private_sample_rights_review_pending",
        provenance_strength=0,  # No independent source-admission/rights review yet.
        raw_resale_allowed=False,
        pii_class="no_contact_or_person_fields",
        allowed_uses=("internal_acquisition", "analytics"),
        notes=(
            "Official metadata-only observation and geometry digest. "
            "Field-level rights, statutory site interpretation and future "
            "customer-use grants require separate independent review."
        ),
    )
    return item.as_dict()


def _validate_props(props: Any, source_id: str) -> dict[str, Any]:
    if not isinstance(props,dict):
        raise ValueError("UNTRUSTED_GIS_ATTRIBUTES")
    allowed = set(SOURCES[source_id]["fields"].split(","))
    if not set(props).issubset(allowed) or "OBJECTID" not in props:
        raise ValueError("UNEXPECTED_GIS_ATTRIBUTE_OR_PII")
    clean: dict[str, Any] = {}
    for k,v in props.items():
        if (v is not None and type(v) not in (str,int,float)):
            raise ValueError("INVALID_ATTRIBUTE_SCALAR")
        if isinstance(v,str) and len(v)>220:
            raise ValueError("OVERSIZE_ATTRIBUTE")
        if isinstance(v,float) and not math.isfinite(v):
            raise ValueError("NONFINITE_GIS_VALUE")
        clean[k] = v
    if type(clean["OBJECTID"]) is not int or clean["OBJECTID"]<=0:
        raise ValueError("SOURCE_OBJECTID_INVALID")
    return clean


def prepare_handoff(
    snapshot: Mapping[str, Any], *, assessed_at:datetime
) -> dict[str, Any]:
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("AWARE_ASSESSMENT_REQUIRED")
    now = assessed_at.astimezone(timezone.utc)
    if not isinstance(snapshot,Mapping) or (
        snapshot.get("schema_version") != "empire.tender_ca18567_official_gis_evidence.v1"
        or snapshot.get("status") != "THREE_OFFICIAL_GIS_LAYER_SAMPLES_OBSERVED_REVIEW_ONLY"
        or snapshot.get("layer_count") != 3
        or snapshot.get("site_intersections_performed") is not False
        or snapshot.get("samples_are_not_exhaustive") is not True
        or snapshot.get("bid_authorized") is not False
        or snapshot.get("land_title_checked") is not False
    ):
        raise ValueError("OFFICIAL_BOUNDED_SOURCE_SNAPSHOT_REQUIRED")
    observed = _time(snapshot.get("observed_at_utc"),now)
    layers=snapshot.get("layers")
    if not isinstance(layers,list) or len(layers) != len(SOURCE_IDS):
        raise ValueError("EXPECTED_EXACT_SOURCE_LAYERS")
    observed_keys=set()
    records=[]
    provenance=[]
    for row in layers:
        if not isinstance(row,Mapping):
            raise ValueError("INVALID_LAYER_RECEIPT")
        source_id = row.get("source_id")
        if not isinstance(source_id,str) or source_id not in SOURCE_IDS or source_id in observed_keys:
            raise ValueError("DUPLICATED_OR_UNKNOWN_SOURCE")
        observed_keys.add(source_id)
        definition=SOURCES[source_id]
        source_hash=row.get("source_response_sha256")
        if (
            row.get("status")!="OFFICIAL_GIS_SAMPLE_OBSERVED_NOT_PARCEL_SCREENING"
            or row.get("catalogue")!=definition["catalogue"]
            or row.get("licence")!=definition["licence"]
            or row.get("source_service")!=definition["service"]
            or row.get("attribution")!=definition["attribution"]
            or not isinstance(source_hash,str) or not HASH.fullmatch(source_hash)
            or row.get("complete_coverage") is not False
        ):
            raise ValueError("SOURCE_IDENTITY_RIGHTS_OR_SAMPLE_SCOPE_MISMATCH")
        collection = row.get("sample_geojson")
        features = collection.get("features") if isinstance(collection,dict) and collection.get("type")=="FeatureCollection" else None
        if not isinstance(features,list) or not (1<=len(features)<=3) or row.get("feature_count")!=len(features):
            raise ValueError("BOUNDED_FEATURE_SAMPLE_REQUIRED")
        local_ids=set()
        for feature in features:
            if not isinstance(feature,dict) or feature.get("type")!="Feature":
                raise ValueError("INVALID_FEATURE")
            props=_validate_props(feature.get("properties"),source_id)
            if feature.get("id")!=props["OBJECTID"]:
                raise ValueError("INCONSISTENT_SOURCE_OBJECTID")
            object_id=props["OBJECTID"]
            if object_id in local_ids:
                raise ValueError("DUPLICATE_SOURCE_OBJECTID")
            local_ids.add(object_id)
            geometry=feature.get("geometry")
            if not isinstance(geometry,dict) or geometry.get("type") not in ("Polygon","MultiPolygon"):
                raise ValueError("INVALID_GIS_POLYGON")
            # Source geometry is already retained under private sampled GeoJSON.
            # Emit digest only; cross-layer geometries do not create a site ID.
            geometry_sha=_hash(geometry)
            candidate = {
                "source_id":SOURCE_KEYS[source_id],
                "source_object_id":str(object_id),
                "source_record_key":SOURCE_KEYS[source_id]+":"+str(object_id),
                "record_kind":RECORD_KINDS[source_id],
                "source_observed_at_utc":observed.isoformat(),
                "source_response_sha256":source_hash,
                "geometry_sha256":geometry_sha,
                "published_attributes":props,
                "geometry_retained_in_private_source_snapshot":True,
                "legal_parcel_id":None,
                "canonical_land_entity_id":None,
                "cross_source_entity_match_verified":False,
                "buyer_intent_verified":False,
                "title_verified":False,
                "availability_verified":False,
            }
            candidate["observation_sha256"]=_hash(candidate)
            records.append(candidate)
        provenance.append({
            "source_id":SOURCE_KEYS[source_id],
            "licence":definition["licence"],
            "licence_url":definition["licence_url"],
            "attribution":definition["attribution"],
            "dataset_catalogue_url":definition["catalogue"],
            "source_response_sha256":source_hash,
            "observed_record_count":len(features),
            "independent_field_level_rights_review":False,
            "approved_for_customer_data_redistribution":False,
        })
    if observed_keys != set(SOURCE_IDS):
        raise ValueError("MISSING_SOURCE_LAYER")
    records.sort(key=lambda x:x["source_record_key"])
    provenance.sort(key=lambda x:x["source_id"])
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "platform":"EXISTING_EMPIREOS_SOURCE_INTELLIGENCE_DATA_EXCHANGE",
        "handoff_kind":"REVIEW_ONLY_SOURCE_ADMISSION_CANDIDATE",
        "product_context":"CA18567_PILOT_NOT_SEPARATE_PLATFORM",
        "assessed_at_utc":now.isoformat(),
        "source_observed_at_utc":observed.isoformat(),
        "source_contracts":[_source_contract(x) for x in SOURCE_IDS],
        "source_evidence":provenance,
        "sample_record_count":len(records),
        "records":records,
        "not_full_geographic_coverage":True,
        "entity_resolution_state":"NONE_PERFORMED",
        "rights_reviewer_approval":False,
        "customer_delivery_enabled":False,
        "raw_data_resale_authorized":False,
        "canonical_empiredb_ingestion_performed":False,
        "existing_data_exchange_owner_acceptance":False,
        "outbound_sent":False,
        "bid_authorized":False,
        "payments":False,
        "revenue_verified":False,
    }


def write_private_handoff(root:Path, *, now:datetime|None=None) -> dict[str,Any]:
    """Create review packet only, no canonical writes or data-platform edits."""
    current=now or datetime.now(timezone.utc)
    report=prepare_handoff(_read_snapshot(root),assessed_at=current)
    _save(root,OUTPUT,report)
    return report
