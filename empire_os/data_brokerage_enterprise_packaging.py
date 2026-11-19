"""Materialize existing Data Brokerage professional research views from verified source receipts.

Called inside the original source-mining lock/department heartbeat. This is an
internal data-warehouse projection, NOT a new marketplace, customer API, or licence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from empire_os.data_brokerage_enterprise_feed import (
    ROOT, STATE, SCHEMA as FEED_SCHEMA, _atomic, _read_rows_from_path,
)

SNAPSHOT = Path("runtime/data_brokerage/enterprise_product_views_latest.json")
SCHEMA = "empire.data_brokerage.enterprise_product_views.v1"
# Original product/offer IDs are unchanged; these are derived internal views.
VIEWS = {
    "us_disaster_territory_activity_sample": {
        "source_id": "us_disaster_declaration_activity",
        "sku": "EAI-STORM",
        "columns": ("state", "fips_state", "fips_county", "county_designated_area",
                    "distinct_declaration_count_in_sample", "most_recent_declaration_date",
                    "oldest_declaration_date_in_sample", "incident_types_in_sample", "coverage_flag"),
        "scope": "County declaration counts in latest 1000 rows; not insurance claims.",
    },
    "uk_healthcare_territory_coverage": {
        "source_id": "uk_cqc_corporate_care_locations",
        "sku": "EAI-HEALTH",
        "columns": ("region", "local_authority", "service_type", "location_count",
                    "distinct_provider_count", "locations_with_last_check_date",
                    "source_snapshot_date", "caveat"),
        "scope": "Registration directory territory coverage; source may lag.",
    },
    "uk_renewable_projects_active_stage_research": {
        "source_id": "uk_renewable_development_projects",
        "sku": "EAI-ENERGY",
        "columns": ("project_ref", "site_name", "technology", "capacity_mw",
                    "development_status", "county", "region", "planning_authority",
                    "planning_application_ref", "record_last_updated", "source_url",
                    "evidence_flag"),
        "scope": "Published planning stages, not procurement intent or verified active builds.",
    },
    "us_fda_regulatory_enforcement_landscape": {
        "source_id": "us_fda_regulatory_enforcement_sample",
        "sku": "EAI-REGULATORY",
        "columns": ("sector", "publisher_classification", "published_state",
                    "report_month", "distinct_reports_in_sample",
                    "unverified_corporate_labels_in_sample",
                    "latest_report_date_in_group", "evidence_flag"),
        "scope": "FDA reported product enforcement by sector, class and geography;"
                 " bounded historical sample, not litigation, claimants,"
                 " regulatory advice or live recall alerts.",
    },
}

def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _encode(columns, rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")

def _fema(rows: list[dict]):
    areas = defaultdict(lambda: {"ids": set(), "types": set(), "last": "", "first": ""})
    for r in rows:
        key = tuple(r.get(k) or "" for k in ("state", "fips_state", "fips_county", "county_designated_area"))
        v = areas[key]
        v["ids"].add(r.get("disaster_number") or "")
        v["types"].add(r.get("event_type") or "")
        date = r.get("declaration_date") or ""
        if date:
            v["last"] = max(date, v["last"])
            v["first"] = min(date, v["first"]) if v["first"] else date
    return [{
        "state": key[0], "fips_state": key[1], "fips_county": key[2],
        "county_designated_area": key[3], "distinct_declaration_count_in_sample": len(v["ids"]),
        "most_recent_declaration_date": v["last"], "oldest_declaration_date_in_sample": v["first"],
        "incident_types_in_sample": "|".join(sorted(v["types"])),
        "coverage_flag": "LATEST_1000_SOURCE_ROWS_ONLY_NO_CLAIMS",
    } for key,v in sorted(areas.items())]

def _cqc_publisher_date(source_url: str) -> str:
    match = re.search(r"/(\d{1,2})_([A-Za-z]+)_(\d{4})_CQC_directory\.csv$", source_url)
    if not match:
        raise ValueError("CQC_OFFICIAL_SNAPSHOT_DATE_MISSING")
    return datetime.strptime("_".join(match.groups()), "%d_%B_%Y").date().isoformat()

def _cqc(rows: list[dict], snapshot_date: str):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", snapshot_date):
        raise ValueError("CQC_PUBLISHER_SNAPSHOT_DATE_UNVERIFIED")
    areas = defaultdict(lambda: {"ids": set(), "providers": set(), "dates": 0})
    for r in rows:
        key = tuple(r.get(k) or "" for k in ("region", "local_authority", "service_type"))
        a = areas[key]
        a["ids"].add(r.get("location_id") or "")
        a["providers"].add(r.get("provider_id") or "")
        a["dates"] += bool(r.get("last_check_date"))
    return [{
        "region": key[0], "local_authority": key[1], "service_type": key[2],
        "location_count": len(v["ids"]), "distinct_provider_count": len(v["providers"]),
        "locations_with_last_check_date": v["dates"],
        "source_snapshot_date": snapshot_date,
        "caveat": "Registration publication may lag; not a measure of demand",
    } for key,v in sorted(areas.items())]

def _repd(rows: list[dict]):
    eligible = {"Planning Permission Granted", "Planning Application Submitted", "Under Construction"}
    result = []
    for r in rows:
        if r.get("development_status") not in eligible:
            continue
        val = (r.get("capacity_mw") or "").replace(",", "")
        try:
            capacity = float(val) if val else ""
        except ValueError:
            capacity = ""
        result.append({
            "project_ref": r.get("project_ref") or "", "site_name": r.get("site_name") or "",
            "technology": r.get("technology") or "", "capacity_mw": capacity,
            "development_status": r.get("development_status") or "",
            "county": r.get("county") or "", "region": r.get("region") or "",
            "planning_authority": r.get("planning_authority") or "",
            "planning_application_ref": r.get("planning_application_ref") or "",
            "record_last_updated": r.get("record_last_updated") or "",
            "source_url": r.get("source_url") or "",
            "evidence_flag": "PUBLISHED_DEVELOPMENT_STAGE_NOT_PROCUREMENT_NEED",
        })
    return result

from empire_os.data_brokerage_fda_regulatory_research import build_regulatory_landscape

BUILDERS = {
    "us_disaster_territory_activity_sample": _fema,
    "uk_healthcare_territory_coverage": _cqc,
    "uk_renewable_projects_active_stage_research": _repd,
    "us_fda_regulatory_enforcement_landscape": build_regulatory_landscape,
}

def run_due(root: Path, *, now: datetime | None = None, allow_noncanonical=False,
            dataset_root: Path | None = None, state_path: Path | None = None,
            source_state_path: Path | None = None) -> dict:
    """One due view per owner call; no network, billing or public publication."""
    root = Path(root).resolve()
    if root != Path("/srv/empire_os") and not allow_noncanonical:
        return {"status": "NONCANONICAL_ROOT_HELD", "view_writes": 0}
    instant = now or datetime.now(timezone.utc)
    if instant.utcoffset() is None:
        raise ValueError("UTC_REQUIRED")
    target = dataset_root or ROOT
    source_path = source_state_path or root / STATE
    output_state_path = state_path or root / SNAPSHOT
    if not source_path.exists():
        return {"status": "ENTERPRISE_SOURCE_RECEIPTS_NOT_YET_VERIFIED", "view_writes": 0}
    source_state = json.loads(source_path.read_text())
    if source_state.get("schema") != FEED_SCHEMA or source_state.get("customer_delivery_authorized") is not False:
        raise ValueError("UNTRUSTED_ENTERPRISE_SOURCE_STATE")
    if output_state_path.exists():
        state = json.loads(output_state_path.read_text())
        if state.get("schema") != SCHEMA or not isinstance(state.get("views"), dict):
            raise ValueError("UNTRUSTED_EXISTING_PRODUCT_VIEWS")
    else:
        state = {"schema": SCHEMA, "views": {}}
    views = state["views"]
    due = []
    newly_held = 0
    for name,spec in VIEWS.items():
        verified = source_state.get("datasets", {}).get(spec["source_id"]) or {}
        prior = views.get(name) or {}
        if (verified.get("source_status") not in ("VERIFIED_UNCHANGED","VERIFIED_CHANGED")
                or verified.get("quality_pass") is not True):
            if prior.get("status") == "VIEW_VERIFIED_INTERNAL":
                prior["status"] = "VIEW_STALE_SOURCE_HELD"
                prior["hold_reason"] = verified.get("source_status") or "SOURCE_NOT_VERIFIED"
                prior["customer_delivery_authorized"] = False
                prior["sales_authorized"] = False
                prior["resale_licence_cleared"] = False
                views[name] = prior
                newly_held += 1
            continue
        if (prior.get("source_sha256") != verified.get("source_snapshot_sha256")
                or prior.get("publisher_source_url") != verified.get("source_url")
                or prior.get("status") != "VIEW_VERIFIED_INTERNAL"
                or not (target/(name + ".csv")).exists()):
            due.append((name, spec, verified))
    if not due:
        if newly_held:
            state.update({"schema": SCHEMA, "views": views,
                "updated_at": instant.isoformat(timespec="seconds"),
                "source_owner": "ORIGINAL_DATA_BROKERAGE_DEPARTMENT_HEARTBEAT",
                "customer_delivery_authorized": False, "sales_authorized": False,
                "public_marketplace_enabled": False, "execution_authority": "research_only"})
            _atomic(output_state_path, (json.dumps(state, indent=2, sort_keys=True) + "\n").encode())
        return {
            "status": "ALL_VERIFIED_VIEWS_CURRENT_OR_SOURCES_HELD",
            "view_writes": 0,
            "views_verified": sum(v.get("status") == "VIEW_VERIFIED_INTERNAL" for v in views.values()),
            "views_held": sum(v.get("status") == "VIEW_STALE_SOURCE_HELD" for v in views.values()),
            "products_authorized_for_sale": 0,
        }
    name, spec, verified = due[0]
    old = dict(views.get(name) or {})
    source_id = spec["source_id"]
    status = {"sku": spec["sku"], "source_id": source_id,
              "source_sha256": verified.get("source_snapshot_sha256"),
              "publisher_source_url": verified.get("source_url"),
              "customer_delivery_authorized": False,
              "resale_licence_cleared": False,
              "sales_authorized": False, "scope": spec["scope"],
              "status": "VIEW_REFRESH_HELD", "checked_at": instant.isoformat(timespec="seconds")}
    try:
        source_file = target / (source_id + ".csv")
        if not source_file.exists():
            raise ValueError("MISSING_VERIFIED_SOURCE_CSV")
        source_bytes = source_file.read_bytes()
        if (_digest(source_bytes) != verified["source_snapshot_sha256"]
                or len(_read_rows_from_path(source_id,source_file)) != verified.get("row_count")):
            raise ValueError("VERIFIED_SOURCE_RECEIPT_DIGEST_OR_COUNT_MISMATCH")
        source_rows = _read_rows_from_path(source_id, source_file)
        if name == "uk_healthcare_territory_coverage":
            materialized = _cqc(source_rows, _cqc_publisher_date(
                verified.get("source_url") or ""))
        else:
            materialized = BUILDERS[name](source_rows)
        out = _encode(spec["columns"], materialized)
        existing_path = target / (name + ".csv")
        if existing_path.exists():
            previous = existing_path.read_bytes()
            if previous != out:
                archive = target / "history" / (name+"_"+_digest(previous)[:20]+".csv")
                if not archive.exists():
                    _atomic(archive, previous)
        if not existing_path.exists() or existing_path.read_bytes() != out:
            _atomic(existing_path, out)
        status.update({"status": "VIEW_VERIFIED_INTERNAL",
            "row_count": len(materialized), "view_sha256": _digest(out),
            "source_rows_checked": len(source_rows), "error_class": None})
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        status["error_class"] = type(exc).__name__
        # No claim that an old view is aligned with the current upstream source.
        status["last_good_view_sha256"] = old.get("view_sha256")
        status["last_good_source_sha256"] = old.get("source_sha256")
    views[name] = status
    state.update({"schema": SCHEMA, "views": views,
        "updated_at": instant.isoformat(timespec="seconds"),
        "source_owner": "ORIGINAL_DATA_BROKERAGE_DEPARTMENT_HEARTBEAT",
        "customer_delivery_authorized": False, "sales_authorized": False,
        "public_marketplace_enabled": False, "execution_authority": "research_only"})
    _atomic(output_state_path, (json.dumps(state, indent=2, sort_keys=True) + "\n").encode())
    return {"status": status["status"], "view": name,
        "view_records": status.get("row_count"), "view_writes": int(status["status"]=="VIEW_VERIFIED_INTERNAL"),
        "source_rows_checked": status.get("source_rows_checked"),
        "products_authorized_for_sale": 0,
        "error_class": status.get("error_class")}
