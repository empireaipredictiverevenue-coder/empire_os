"""CA18567 public GIS evidence screening: official layers, no parcel title inference.

Original EmpireOS Tender Consultant capability. Every external call is a bounded
GET to one fixed public government ArcGIS feature layer; never credentials,
customer APIs, scraped listings, submission, CRM, EmpireDB or paid services.
All coordinates supplied for intersection are UNATTESTED by this software.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

BASE = Path("runtime/acquisition_research")
SAMPLE_OUTPUT = "ca18567_official_gis_snapshot_latest.json"
SCREEN_OUTPUT = "ca18567_parcel_geometry_screen_latest.json"
SCHEMA = "empire.tender_ca18567_official_gis_evidence.v1"

# Permissions from the stated GOVERNMENT DATASET CATALOGUES, not permission to
# copy proprietary basemap tiles, cadastre or private landowner data.
SOURCES = {
    "ROI_GZT": {
        "jurisdiction": "ROI",
        "label": "MyPlan GZT Current Plan - Louth",
        "service": "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/GZT_Current_Plan/FeatureServer/0",
        "catalogue": "https://opendata.housing.gov.ie/dataset/gzt-current-plan",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "licence": "CC-BY-4.0",
        "attribution": "Department of Housing, Local Government and Heritage / MyPlan; underlying zoning provided by local authorities",
        "fixed_where": "LA_NAME = 'Louth' AND CURRENT_PLAN = 1",
        "fields": "OBJECTID,LA_NAME,PLAN_NAME,ZONE_GZT,CURRENT_PLAN,PLAN_TO",
        "warning": "Generalised zoning complements rather than replaces statutory local development plans; coverage may be incomplete.",
        "jurisdiction_bbox": (-10.8, 51.3, -5.3, 55.5),
    },
    "ROI_PLANNING_SITES": {
        "jurisdiction": "ROI",
        "label": "Irish National Planning Application Sites - Louth sample",
        "service": "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/IrishPlanningApplications/FeatureServer/1",
        "catalogue": "https://data.gov.ie/dataset/national-planning-applications",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "licence": "CC-BY-4.0",
        "attribution": "Department of Housing, Local Government and Heritage / participating Irish local authorities; National Planning Applications",
        "fixed_where": "PlanningAuthority = 'Louth County Council'",
        "fields": "OBJECTID,PlanningAuthority,ApplicationNumber,ApplicationStatus,Decision,ReceivedDate,DecisionDate,GrantDate",
        "warning": "Planning-application polygons are not cadastral parcels, proof of permission for a proposed development, or proof of ownership; independently verify decision and currency with the local authority.",
        "jurisdiction_bbox": (-10.8, 51.3, -5.3, 55.5),
    },
    "NI_HED_SCHEDULED": {
        "jurisdiction": "NI",
        "label": "Northern Ireland Historic Environment Division Scheduled Zones - County Down sample",
        "service": "https://services2.arcgis.com/BdBkthNLO9mzGAMO/arcgis/rest/services/Historic_Environment_Division_GIS_Data/FeatureServer/10",
        "catalogue": "https://admin.opendatani.gov.uk/dataset/scheduled-historic-monument-areas",
        "licence_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "licence": "UK-OGL-v3",
        "attribution": "Historic Environment Division, Department for Communities, Northern Ireland; contains public sector information licensed under the Open Government Licence v3.0",
        "fixed_where": "COUNTY = 'DOW'",
        "fields": "OBJECTID,COUNTY,SMNO,TOWNLAND",
        "warning": "Indicative Scheduled Zones only; official scheduling declaration from HERoNI required for affected land.",
        "jurisdiction_bbox": (-8.3, 54.0, -5.2, 55.5),
    },
}
SOURCE_IDS = ("ROI_GZT", "ROI_PLANNING_SITES", "NI_HED_SCHEDULED")
MAX_HTTP_BYTES = 300_000
MAX_FEATURES = 3
MAX_SCREEN_HITS = 25


def _base() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "tender_ref": "CA18567",
        "authority": "OBSERVE_ONLY",
        "qualified_land_specialist": False,
        "land_title_checked": False,
        "parcel_boundary_legally_verified": False,
        "rfq_authenticated": False,
        "issuer_evaluation_met": False,
        "land_currently_available_verified": False,
        "bid_authorized": False,
        "external_bids": 0,
        "outbound_sent": False,
        "db_writes": False,
        "crm_writes": False,
        "payment_actions": False,
        "revenue_verified": False,
    }


def _fetch_json(base_url: str, params: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Hard allowlisted fixed ArcGIS REST endpoints, bounded download."""
    if base_url not in tuple(s["service"] for s in SOURCES.values()):
        raise ValueError("UNAPPROVED_GIS_ORIGIN")
    import requests
    try:
        with requests.get(
            base_url + "/query", params=params,
            timeout=(6, 18), stream=True, allow_redirects=False,
            headers={"User-Agent": "EmpireAI-CA18567-official-research/1.0"}
        ) as response:
            if response.status_code != 200:
                raise ValueError("GIS_RESPONSE_NOT_200")
            if int(response.headers.get("Content-Length", "0")) > MAX_HTTP_BYTES:
                raise ValueError("GIS_RESPONSE_OVERSIZE")
            parts = []
            total = 0
            for chunk in response.iter_content(chunk_size=8192):
                total += len(chunk)
                if total > MAX_HTTP_BYTES:
                    raise ValueError("GIS_RESPONSE_OVERSIZE")
                parts.append(chunk)
    except requests.RequestException as exc:
        raise ValueError("GIS_NETWORK_OR_TRANSPORT_ERROR") from exc
    raw = b"".join(parts)
    if not raw:
        raise ValueError("GIS_RESPONSE_EMPTY")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("GIS_NOT_JSON") from exc
    if not isinstance(data, dict) or "error" in data:
        raise ValueError("GIS_RETURNED_ERROR")
    return data, sha256(raw).hexdigest()


def _private_path(root: Path, name: str) -> Path:
    root = root.resolve(strict=True)
    parent = root / BASE
    st = parent.lstat()
    if (parent.is_symlink() or not stat.S_ISDIR(st.st_mode)
        or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700):
        raise ValueError("REQUIRES_ORIGINAL_PRIVATE_RESEARCH_FOLDER")
    target = parent / name
    if target.is_symlink() or (target.exists() and (
        not target.is_file() or target.stat().st_uid != os.geteuid()
        or stat.S_IMODE(target.stat().st_mode) != 0o600
    )):
        raise ValueError("UNSAFE_PRIVATE_GIS_OUTPUT")
    return target


def _save(root: Path, name: str, report: dict[str, Any]) -> Path:
    target = _private_path(root, name)
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, temp = tempfile.mkstemp(prefix=".ca18567-gis-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return target


def _checked_features(document: dict[str, Any], *, max_items: int, require_geometry: bool) -> list[dict[str, Any]]:
    if document.get("type") != "FeatureCollection":
        raise ValueError("GIS_NOT_GEOJSON_FEATURECOLLECTION")
    features = document.get("features")
    if not isinstance(features, list) or len(features) > max_items:
        raise ValueError("GIS_FEATURE_LIMIT_OR_SCHEMA")
    safe = []
    for item in features:
        if not isinstance(item, dict) or item.get("type") != "Feature":
            raise ValueError("GIS_INVALID_FEATURE")
        attrs = item.get("properties")
        if not isinstance(attrs, dict):
            raise ValueError("GIS_INVALID_PROPERTIES")
        shape = item.get("geometry")
        if require_geometry and (not isinstance(shape, dict)
                                 or shape.get("type") not in ("Polygon", "MultiPolygon")
                                 or not isinstance(shape.get("coordinates"), list)):
            raise ValueError("GIS_INVALID_SPATIAL_GEOMETRY")
        safe.append({"type": "Feature", "id": item.get("id"), "properties": attrs,
                     "geometry": shape if require_geometry else None})
    return safe


def snapshot_official_layers(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Fetch bounded samples, not complete coverage, of three rights-labelled GIS layers."""
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    report = {
        **_base(), "status": "PARTIAL_PUBLIC_GIS_SNAPSHOT_REVIEW_ONLY",
        "observed_at_utc": dt.astimezone(timezone.utc).isoformat(),
        "layer_count": 0, "samples_are_not_exhaustive": True,
        "site_intersections_performed": False,
        "license_notice": "Attribution preserved. No proprietary basemap, title register, parcel geometry or landowner data downloaded.",
        "layers": [],
    }
    # Continue on source errors but never call or imply the source healthy.
    for source_id in SOURCE_IDS:
        item = SOURCES[source_id]
        row = {key: item[key] for key in (
            "label", "catalogue", "licence", "licence_url", "attribution", "warning"
        )}
        row["source_id"] = source_id
        row["feature_count"] = 0
        row["complete_coverage"] = False
        row["sample_geojson"] = {"type": "FeatureCollection", "features": []}
        row["status"] = "SOURCE_UNAVAILABLE_NOT_CLEAR"
        try:
            doc, digest = _fetch_json(item["service"], {
                "f": "geojson", "where": item["fixed_where"],
                "outFields": item["fields"], "returnGeometry": "true",
                "resultRecordCount": MAX_FEATURES,
                "orderByFields": "OBJECTID ASC", "outSR": 4326,
            })
            features = _checked_features(doc, max_items=MAX_FEATURES, require_geometry=True)
            row["sample_geojson"]["features"] = features
            row["feature_count"] = len(features)
            row["source_response_sha256"] = digest
            row["source_service"] = item["service"]
            row["source_truncated"] = bool(doc.get("properties", {}).get("exceededTransferLimit", True))
            row["status"] = "OFFICIAL_GIS_SAMPLE_OBSERVED_NOT_PARCEL_SCREENING"
            report["layer_count"] += 1
        except (ValueError, KeyError, TypeError, OSError) as exc:
            row["failure_code"] = str(exc)[:80]
        report["layers"].append(row)
    if report["layer_count"] == len(SOURCE_IDS):
        report["status"] = "THREE_OFFICIAL_GIS_LAYER_SAMPLES_OBSERVED_REVIEW_ONLY"
    _save(root, SAMPLE_OUTPUT, report)
    return report


def _validated_ring(geometry: Any, jurisdiction: str) -> list[list[float]]:
    """Caller-supplied polygon, WGS84; not a legal/cadastral boundary."""
    if jurisdiction not in ("ROI", "NI"):
        raise ValueError("INVALID_JURISDICTION")
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ValueError("ONLY_SINGLE_WGS84_POLYGON_SUPPORTED")
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1:
        raise ValueError("SINGLE_OUTER_RING_REQUIRED_NO_HOLES")
    ring = rings[0]
    if not isinstance(ring, list) or not 4 <= len(ring) <= 80:
        raise ValueError("INVALID_RING_VERTEX_COUNT")
    validated = []
    for point in ring:
        if (not isinstance(point, list) or len(point) != 2
            or any(type(v) not in (float, int) or not math.isfinite(v) for v in point)):
            raise ValueError("INVALID_WGS84_VERTEX")
        lon, lat = (float(point[0]), float(point[1]))
        validated.append([lon, lat])
    if validated[0] != validated[-1] or len(set(map(tuple, validated[:-1]))) < 3:
        raise ValueError("RING_NOT_CLOSED_OR_DEGENERATE")
    xs = [p[0] for p in validated]
    ys = [p[1] for p in validated]
    if max(xs)-min(xs) > 0.05 or max(ys)-min(ys) > 0.05:
        raise ValueError("AREA_TOO_LARGE_FOR_PARCEL_REVIEW")
    bounds = SOURCES["ROI_GZT" if jurisdiction=="ROI" else "NI_HED_SCHEDULED"]["jurisdiction_bbox"]
    if not all(bounds[0] <= x <= bounds[2] for x in xs) or not all(bounds[1] <= y <= bounds[3] for y in ys):
        raise ValueError("COORDINATES_OUTSIDE_JURISDICTION")
    # Detect repeated non-closing vertices and untrusted self-intersection risks;
    # this is not a formal topological validator (specialist GIS required).
    if len(set(map(tuple, validated[:-1]))) != len(validated)-1:
        raise ValueError("REPEATED_RING_VERTEX")
    double_area = sum(a[0]*b[1] - b[0]*a[1]
                      for a,b in zip(validated,validated[1:]))
    if abs(double_area) < 1e-12:
        raise ValueError("DEGENERATE_ZERO_AREA_RING")
    def orient(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for i in range(len(validated)-1):
        a,b=validated[i:i+2]
        for j in range(i+2,len(validated)-1):
            if i==0 and j==len(validated)-2:
                continue  # first/last adjacent by ring closure
            c,d=validated[j:j+2]
            if ((orient(a,b,c)*orient(a,b,d)<0) and
                (orient(c,d,a)*orient(c,d,b)<0)):
                raise ValueError("SELF_INTERSECTING_RING")
    return validated


def screen_unverified_parcel_geometry(
    root: Path, *, reference: str, jurisdiction: str,
    geometry: dict[str, Any], geometry_source: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """ArcGIS-backed source-specific intersection check, NOT a legal land screening."""
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    if not isinstance(reference, str) or not 1 <= len(reference) <= 60 or not all(c.isalnum() or c in "_-" for c in reference):
        raise ValueError("INVALID_PRIVATE_PARCEL_REFERENCE")
    if not isinstance(geometry_source, str) or not 5 <= len(geometry_source) <= 300:
        raise ValueError("GEOMETRY_SOURCE_DESCRIPTION_REQUIRED")
    ring = _validated_ring(geometry, jurisdiction)
    relevant_source_ids = ("ROI_GZT", "ROI_PLANNING_SITES") if jurisdiction == "ROI" else ("NI_HED_SCHEDULED",)
    source = SOURCES[relevant_source_ids[0]]
    result = {
        **_base(), "status": "UNVERIFIED_GEOMETRY_SOURCE_NOT_SPATIAL_CLEARANCE",
        "observed_at_utc": dt.astimezone(timezone.utc).isoformat(),
        "candidate_reference": reference,
        "jurisdiction": jurisdiction,
        "geometry_origin_claim_unverified": geometry_source,
        "geometry_sha256": sha256(json.dumps(ring, separators=(",", ":")).encode()).hexdigest(),
        "title_is_not_inferred_from_geometry": True,
        "licence": source["licence"],
        "licence_url": source["licence_url"],
        "attribution": source["attribution"],
        "source_catalogue": source["catalogue"],
        "source_warning": source["warning"],
        "intersections": [],
        "checked_source_ids": list(relevant_source_ids),
        "sources_observed_successfully": 0,
        "source_results": [],
        "intersections_are_only_screening_flags": True,
        "a_zero_hit_result_is_not_planning_clearance": True,
    }
    truncation = False
    source_failures = 0
    for source_id in relevant_source_ids:
        layer = SOURCES[source_id]
        layer_result = {
            "source_id": source_id,
            "catalogue": layer["catalogue"],
            "licence": layer["licence"],
            "attribution": layer["attribution"],
            "status": "UNAVAILABLE_NOT_CLEAR",
            "feature_count": 0,
        }
        try:
            doc, digest = _fetch_json(layer["service"], {
                "f": "geojson",
                "where": layer["fixed_where"],
                "geometry": json.dumps({"rings": [ring], "spatialReference": {"wkid": 4326}}, separators=(",", ":")),
                "geometryType": "esriGeometryPolygon",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": layer["fields"], "returnGeometry": "false",
                "resultRecordCount": MAX_SCREEN_HITS, "orderByFields": "OBJECTID ASC",
            })
            features = _checked_features(doc, max_items=MAX_SCREEN_HITS, require_geometry=False)
            layer_result["status"] = "SOURCE_QUERIED_RESULT_NOT_CLEARANCE"
            layer_result["feature_count"] = len(features)
            layer_result["response_sha256"] = digest
            layer_result["source_service"] = layer["service"]
            layer_result["result_limit_reached"] = bool(doc.get("properties", {}).get("exceededTransferLimit", False))
            truncation = truncation or layer_result["result_limit_reached"]
            result["sources_observed_successfully"] += 1
            result["intersections"].extend([
                {"source_id": source_id, "attributes": item["properties"]}
                for item in features
            ])
        except (ValueError, OSError, TypeError, KeyError) as exc:
            source_failures += 1
            layer_result["failure_code"] = str(exc)[:80]
        result["source_results"].append(layer_result)
    result["result_limit_reached"] = truncation
    result["status"] = (
        "GIS_LAYER_UNAVAILABLE_DO_NOT_INFER_CLEARANCE"
        if source_failures == len(relevant_source_ids) else
        "PARTIAL_GIS_SOURCES_UNAVAILABLE_DO_NOT_INFER_CLEARANCE"
        if source_failures else
        "POTENTIAL_SPATIAL_CONFLICTS_PARTIAL_RESULT_HUMAN_REVIEW"
        if truncation else
        "GIS_INTERSECTION_RESULT_NOT_LAND_OR_PLANNING_CLEARANCE"
    )
    _save(root, SCREEN_OUTPUT, result)
    return result
