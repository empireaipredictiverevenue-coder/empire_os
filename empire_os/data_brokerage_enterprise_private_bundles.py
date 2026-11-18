"""Reproducible private research bundles from verified original brokerage views.

Uses the ORIGINAL owner lock and timer. Archives are for founder/agent QA only,
not for customer delivery, sale, public URLs or background subscribers.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from empire_os.data_brokerage_enterprise_feed import ROOT, STATE as SOURCES_STATE, _atomic
from empire_os.data_brokerage_enterprise_packaging import SNAPSHOT as VIEWS_STATE, VIEWS

STATE = Path("runtime/data_brokerage/enterprise_private_bundles_latest.json")
SCHEMA = "empire.data_brokerage.private_research_bundles.v1"
VERSION = "V2"
COPY = {
    "EAI-STORM": "US government disaster declaration territory research; no claim, property damage or insurance need established.",
    "EAI-HEALTH": "UK regulated-care location distribution by region, local authority and service category; registry may lag.",
    "EAI-ENERGY": "UK published renewable planning-stage project analysis; not an independently verified active construction or buying signal.",
    "EAI-REGULATORY": "FDA food, drug and device public enforcement reporting patterns; not a mass-tort list, claimant dataset or safety alert.",
}
RIGHTS = {
    "EAI-STORM": "Federal public data; field and downstream-use review pending.",
    "EAI-HEALTH": "CQC Open Government Licence source; attribution and privacy/field review pending.",
    "EAI-ENERGY": "DESNZ Renewable Energy Planning Database; OGL/third-party field review pending.",
    "EAI-REGULATORY": "openFDA generally CC0; exclude restricted GMDN data, avoid implying FDA endorsement; source service terms and privacy apply.",
}


FIELD_DESCRIPTIONS = {
    "state": "FEMA publisher state code from a designated declaration geography row.",
    "fips_state": "FEMA published two-digit state FIPS code.",
    "fips_county": "FEMA published county FIPS code; may represent statewide/special designations.",
    "county_designated_area": "Official FEMA published designated geography label.",
    "distinct_declaration_count_in_sample": "Unique FEMA disaster numbers within the latest 1000 source geography rows in this location. Not affected properties.",
    "most_recent_declaration_date": "Latest official declaration date in the bounded source window.",
    "oldest_declaration_date_in_sample": "Oldest declaration date represented in the bounded source window.",
    "incident_types_in_sample": "Pipe-delimited set of publisher incident categories; not a loss estimate.",
    "coverage_flag": "Explicit source sample limitation and claims caveat.",
    "region": "Publisher-stated region, not verified economic market territory.",
    "local_authority": "CQC published local authority name.",
    "service_type": "CQC published service type; multiple values may be combined.",
    "location_count": "Distinct published CQC location IDs in this grouped territory.",
    "distinct_provider_count": "Distinct CQC provider IDs in this group, not independently verified parent companies.",
    "locations_with_last_check_date": "Count of grouped locations that have a publisher check date; NOT recent compliance certification.",
    "source_snapshot_date": "Release date parsed from the official CQC directory filename.",
    "caveat": "Publisher coverage and timeliness qualification.",
    "project_ref": "DESNZ REPD publisher project reference; not a buyer or company identifier.",
    "site_name": "DESNZ published project/site name.",
    "technology": "DESNZ published renewable technology classification.",
    "capacity_mw": "Publisher-supplied installed capacity in MWelec where parseable; not actual current production.",
    "development_status": "REPD published planning/development stage; requires independent real-world update verification.",
    "county": "DESNZ published county.",
    "planning_authority": "REPD planning authority label.",
    "planning_application_ref": "Publisher-reported planning application reference; not independently verified here.",
    "record_last_updated": "REPD source field recording a publisher update date; may be historical.",
    "source_url": "Official publisher reference page for provenance, not proof of offer or work.",
    "evidence_flag": "Research-only status and prohibited inference indicator.",
    "sector": "FDA enforcement endpoint: food, drug or device.",
    "publisher_classification": "Published FDA recall hazard classification, NOT a current alert status.",
    "published_state": "FDA enforcement reported firm state; may be blank or non-U.S. jurisdiction.",
    "report_month": "Year-month of the FDA report publication, YYYY-MM.",
    "distinct_reports_in_sample": "Distinct enforcement report IDs within a 400-row-per-sector sample, not full market incidence.",
    "unverified_corporate_labels_in_sample": "Distinct corporate-appearing publisher labels in the bounded sample; identities not verified.",
    "latest_report_date_in_group": "Most recent FDA report publication date in this grouped sample.",
}
NUMERIC_FIELDS = {
    "distinct_declaration_count_in_sample", "location_count",
    "distinct_provider_count", "locations_with_last_check_date",
    "distinct_reports_in_sample", "unverified_corporate_labels_in_sample",
}

def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_zip(data: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as z:
        for name, content in sorted(data.items()):
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                raise ValueError("ARCHIVE_PATH_UNSAFE")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            z.writestr(info, content)
    output = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(output)) as z:
        if z.testzip() is not None or sorted(z.namelist()) != sorted(data):
            raise ValueError("PRIVATE_ARCHIVE_INTEGRITY_FAILED")
    return output


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("PRIVATE_BUNDLE_JSON_SCHEMA_INVALID")
    return value


def run_due(root: Path, *, now: datetime | None = None,
            allow_noncanonical: bool = False,
            data_root: Path | None = None,
            source_state: Path | None = None,
            view_state: Path | None = None,
            bundle_state: Path | None = None) -> dict:
    """At most one checked internal research package per original owner call."""
    root = Path(root).resolve()
    if root != Path("/srv/empire_os") and not allow_noncanonical:
        return {"status": "NONCANONICAL_ROOT_HELD", "bundles_built": 0}
    instant = now or datetime.now(timezone.utc)
    if instant.utcoffset() is None:
        raise ValueError("UTC_REQUIRED")
    data_root = data_root or ROOT
    source_state = source_state or root / SOURCES_STATE
    view_state = view_state or root / VIEWS_STATE
    bundle_state = bundle_state or root / STATE
    if not source_state.is_file() or not view_state.is_file():
        return {"status": "SOURCE_OR_VIEW_RECEIPT_MISSING", "bundles_built": 0}
    sources = _read_json(source_state)
    views = _read_json(view_state)
    if (sources.get("customer_delivery_authorized") is not False
            or views.get("customer_delivery_authorized") is not False):
        raise ValueError("CUSTOMER_DELIVERY_AUTHORITY_NOT_CONSTRAINED")
    state = (_read_json(bundle_state) if bundle_state.exists()
             else {"schema": SCHEMA, "bundles": {}})
    if state.get("schema") != SCHEMA or not isinstance(state.get("bundles"), dict):
        raise ValueError("EXISTING_PRIVATE_BUNDLE_STATE_INVALID")
    catalog = views.get("views") or {}
    due = []
    held = []
    newly_held = 0
    for name, spec in VIEWS.items():
        record = catalog.get(name) or {}
        src = (sources.get("datasets") or {}).get(spec["source_id"]) or {}
        source_good = src.get("source_status") in ("VERIFIED_UNCHANGED", "VERIFIED_CHANGED")
        view_good = record.get("status") == "VIEW_VERIFIED_INTERNAL"
        source_issue = not source_good or not view_good or src.get("quality_pass") is not True
        authority_issue = (record.get("source_sha256") != src.get("source_snapshot_sha256")
                           or record.get("sales_authorized") is not False
                           or record.get("customer_delivery_authorized") is not False)
        if source_issue or authority_issue:
            held.append(name)
            prior = state["bundles"].get(name)
            if prior and prior.get("status") == "PRIVATE_RESEARCH_BUNDLE_VERIFIED":
                prior["status"] = "PRIVATE_RESEARCH_BUNDLE_SOURCE_HELD"
                prior["hold_reason"] = "SOURCE_QUALITY_OR_CUSTOMER_AUTHORITY_MISMATCH"
                prior["customer_delivery_authorized"] = False
                prior["resale_licence_cleared"] = False
                newly_held += 1
            continue
        existing = state["bundles"].get(name) or {}
        path = data_root/"internal_bundles"/(spec["sku"]+"_private_research.zip")
        actual_digest = _hash(path.read_bytes()) if path.is_file() else None
        if (existing.get("view_sha256") != record.get("view_sha256")
                or existing.get("archive_sha256") != actual_digest
                or existing.get("bundle_format_version") != VERSION
                or existing.get("status") != "PRIVATE_RESEARCH_BUNDLE_VERIFIED"):
            due.append((name, spec, record, src, path))
    if not due:
        if newly_held:
            state.update({"updated_at": instant.isoformat(timespec="seconds"),
                          "customer_delivery_authorized": False,
                          "automated_sales": False})
            _atomic(bundle_state, (json.dumps(state,sort_keys=True,indent=2)+"\n").encode())
        return {"status": "PRIVATE_RESEARCH_BUNDLES_CURRENT_OR_SOURCES_HELD",
                "bundles_built": 0,
                "bundles_current": sum(v.get("status") == "PRIVATE_RESEARCH_BUNDLE_VERIFIED"
                                       for v in state["bundles"].values()),
                "sources_or_views_held": len(held),
                "customer_downloads_enabled": False}
    name, spec, view, src, path = due[0]
    result = {
        "schema": "empire.data_brokerage.private_bundle.v1",
        "bundle_format_version": VERSION,
        "sku": spec["sku"], "view_id": name,
        "source_id": spec["source_id"], "publisher": src.get("publisher"),
        "publisher_source_url": src.get("source_url"),
        "view_sha256": view["view_sha256"],
        "source_sha256": view["source_sha256"],
        "source_publication_evidence": src.get("publisher_publication_metadata") or {},
        "source_observed_at": src.get("last_success_at"),
        "coverage": spec["scope"], "buyer_use_case": COPY[spec["sku"]],
        "data_rights": RIGHTS[spec["sku"]],
        "raw_resale_approved": False, "licence_review_status": "CUSTOMER_FIELD_REVIEW_REQUIRED",
        "allowed_action": "INTERNAL_SOURCE_QUALITY_AND_BUYER_SCOPE_RESEARCH",
        "customer_delivery_authorized": False,
        "paid_order_verified": False,
        "founder_release_approved": False,
        "distribution_prohibited_without_contract": True,
        "data_is_complete_population": False,
    }
    csv_path = data_root/(name+".csv")
    if not csv_path.is_file() or _hash(csv_path.read_bytes()) != view.get("view_sha256"):
        raise ValueError("PRIVATE_BUNDLE_VIEW_SHA256_FAILED")
    source_file = data_root/(spec["source_id"]+".csv")
    if not source_file.is_file() or _hash(source_file.read_bytes()) != view.get("source_sha256"):
        raise ValueError("PRIVATE_BUNDLE_SOURCE_SHA256_FAILED")
    csv_data = csv_path.read_bytes()
    with io.StringIO(csv_data.decode("utf-8-sig", errors="strict")) as inp:
        reader = csv.DictReader(inp)
        columns = list(reader.fieldnames or [])
        if columns != list(spec["columns"]):
            raise ValueError("PRIVATE_BUNDLE_VIEW_COLUMNS_MISMATCH")
        row_count = sum(1 for _ in reader)
    if row_count != view.get("row_count") or row_count == 0:
        raise ValueError("PRIVATE_BUNDLE_VIEW_ROW_COUNT_MISMATCH")
    result["rows"] = row_count
    result["columns"] = columns
    docs = "\n".join([
        "# Empire AI research candidate — internal use only",
        "SKU: " + spec["sku"],
        "Use: " + COPY[spec["sku"]],
        "Scope: " + spec["scope"],
        "Publisher: " + str(src.get("publisher")),
        "Records in VIEW: " + str(row_count) + " (not complete market coverage)",
        "Source SHA256: " + view["source_sha256"],
        "View SHA256: " + view["view_sha256"],
        "Rights: " + RIGHTS[spec["sku"]],
        "No buyer contract, resale approval, public alert, customer delivery or sales authority.",
        "Current source/view receipts must be checked before any permitted delivery.",
    ]) + "\n"
    quality = {
        "source_status": src.get("source_status"),
        "source_quality_pass": src.get("quality_pass"),
        "sample_not_full_population": src.get("sample_not_full_population", True),
        "source_last_checked_at": src.get("last_checked_at"),
        "source_last_success_at": src.get("last_success_at"),
        "source_records_in_snapshot": src.get("row_count"),
        "view_rows": row_count,
        "source_accepted_exclusions": src.get("publisher_publication_metadata", {}).get(
            "excluded_missing_or_na_recall_id_by_sector", {}),
        "source_window_new_ids": src.get("source_window_new_ids"),
        "source_window_changed_ids": src.get("source_window_changed_ids"),
        "source_window_absent_ids": src.get("source_window_absent_ids"),
        "change_counts_are_not_independent_real_world_events": True,
        "view_checksum_verified": True,
        "source_checksum_verified": True,
        "qualified_buyers_verified": 0,
        "licensed_customer_deliveries_verified": 0,
    }
    archive = _safe_zip({
        "data.csv": csv_data,
        "manifest.json": (json.dumps(result, sort_keys=True, indent=2) + "\n").encode(),
        "README.md": docs.encode(),
        "quality_report.json": (json.dumps(quality, sort_keys=True, indent=2) + "\n").encode(),
        "field_dictionary.json": (json.dumps({
            "columns": [{"name": col,
                         "type": ("integer" if col in NUMERIC_FIELDS else
                                  "decimal_or_empty" if col == "capacity_mw" else "string"),
                         "description": FIELD_DESCRIPTIONS[col]}
                        for col in columns],
            "source_id": spec["source_id"], "source_view": name,
            "verified_against_original_source": True,
            "customer_delivery_approved": False,
        }, indent=2)+"\n").encode(),
    })
    if path.is_file() and _hash(path.read_bytes()) != _hash(archive):
        old = path.read_bytes()
        history = data_root/"internal_bundles"/"history"/(
            spec["sku"]+"_"+_hash(old)[:20]+".zip")
        if not history.exists():
            _atomic(history,old)
    _atomic(path, archive)
    state["bundles"][name] = {
        "status": "PRIVATE_RESEARCH_BUNDLE_VERIFIED", "sku": spec["sku"],
        "bundle_format_version": VERSION,
        "view_sha256": view["view_sha256"],
        "source_sha256": view["source_sha256"],
        "archive_sha256": _hash(archive), "row_count": row_count,
        "last_verified_at": instant.isoformat(timespec="seconds"),
        "archive_path": str(path),
        "customer_delivery_authorized": False,
        "resale_licence_cleared": False,
        "revenue_verified": False,
    }
    state.update({"schema": SCHEMA, "bundles": state["bundles"],
        "updated_at": instant.isoformat(timespec="seconds"),
        "owner": "ORIGINAL_DATA_BROKERAGE_SOURCE_MINING",
        "execution_authority": "internal_research_only",
        "customer_delivery_authorized": False, "automated_sales": False,
        "new_scheduler_created": False})
    _atomic(bundle_state, (json.dumps(state,sort_keys=True,indent=2)+"\n").encode())
    return {"status": "PRIVATE_RESEARCH_BUNDLE_VERIFIED",
            "sku": spec["sku"], "dataset": name, "bundle_rows": row_count,
            "bundles_built": 1, "archive_sha256": _hash(archive),
            "customer_downloads_enabled": False}
