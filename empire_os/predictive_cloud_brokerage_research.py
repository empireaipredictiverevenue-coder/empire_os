"""Existing Predictive Cloud's *internal* read-only research intake from Brokerage.

The original Data Brokerage source owner invokes this under its existing lock
and timer, after source and derived-view verification. Private CSV snapshots
are content-addressed under Predictive Cloud runtime, not copied into customer,
multi-tenant, forecast-training, or externally exposed surfaces.

No issuer/tenant/forecast/outcome attestation is inferred. Fail closed if
upstream receipts, source digests, schemas or privacy gates differ.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any

from empire_os.data_brokerage_enterprise_feed import (
    HEADERS, SOURCES, SCHEMA as SOURCE_SCHEMA, STATE as SOURCE_RECEIPT,
)
from empire_os.data_brokerage_enterprise_packaging import (
    VIEWS, SCHEMA as VIEW_SCHEMA, SNAPSHOT as VIEW_RECEIPT,
)

SCHEMA = "empire.predictive_cloud.brokerage_research_inputs.v1"
INDEX_PATH = Path("runtime/predictive_cloud/brokerage_research_private/inputs_latest.json")
DEFAULT_ORIGINAL_DATA = Path("/home/ubuntu/empire_research/enterprise_data_packs_20261118")
SOURCE_TYPES = ("original_source", "derived_research_view")
VIEW_DIMENSIONS = {
    "us_disaster_territory_activity_sample": ("state", "county_territory_rows_in_sample"),
    "uk_healthcare_territory_coverage": ("region", "service_territory_rows_in_published_directory"),
    "uk_renewable_projects_active_stage_research": ("technology", "published_development_project_rows"),
    "us_fda_regulatory_enforcement_landscape": ("sector", "published_enforcement_reports_in_bounded_sample"),
}
SCOPES = {
    "us_disaster_territory_activity_sample":
        "Latest FEMA 1000 source geography rows; territory occurrences not claims.",
    "uk_healthcare_territory_coverage":
        "CQC grouped service territories, not unique providers, demand or live licences.",
    "uk_renewable_projects_active_stage_research":
        "DESNZ published renewable development rows, not verified procurement.",
    "us_fda_regulatory_enforcement_landscape":
        "FDA historical report classifications, not claimants, lawsuits or live safety alerts.",
}
MAX_BYTES = 20_000_000
MAX_SEGMENTS_PER_VIEW = 200


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_receipt(path: Path, schema: str) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("MISSING_OR_UNSAFE_BROKERAGE_RECEIPT")
    j = json.loads(path.read_text())
    if not isinstance(j, dict) or j.get("schema") != schema:
        raise ValueError("BROKERAGE_RECEIPT_SCHEMA_HOLD")
    return j


def _read_source_bytes(path: Path, expected: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("SOURCE_FILE_MISSING_OR_LINKED")
    if not re.fullmatch(r"[a-f0-9]{64}", str(expected)):
        raise ValueError("INVALID_SOURCE_DIGEST")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
        raise ValueError("SOURCE_FILE_SIZE_OR_MODE_HELD")
    value = path.read_bytes()
    after = path.stat()
    if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
            after.st_ctime_ns):
        raise ValueError("SOURCE_MUTATED_DURING_CLOUD_READ")
    if _sha(value) != expected:
        raise ValueError("SOURCE_OWNER_SHA256_MISMATCH")
    return value


def _decode_csv(raw: bytes, expected_header: tuple[str, ...],
                expected_count: int) -> list[dict[str, str]]:
    if (not isinstance(expected_count, int) or type(expected_count) is bool
            or not 1 <= expected_count <= 100_000):
        raise ValueError("SOURCE_ROW_COUNT_INVALID")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        parser = csv.DictReader(io.StringIO(text, newline=""))
        if tuple(parser.fieldnames or ()) != tuple(expected_header):
            raise ValueError("SOURCE_FIELDS_NOT_VERIFIED")
        rows = list(parser)
    except UnicodeError:
        raise ValueError("SOURCE_ENCODING_INVALID")
    if len(rows) != expected_count or any(
            None in row or any(value is None for value in row.values())
            for row in rows):
        raise ValueError("SOURCE_ROWS_NOT_VERIFIED")
    return rows


def _atomic_secure(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("UNSAFE_CLOUD_PRIVATE_DESTINATION")
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=".cloud-input-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _segments(name: str, rows: list[dict[str, str]]) -> list[dict]:
    dimension, metric = VIEW_DIMENSIONS[name]
    counts: Counter[str] = Counter()
    for row in rows:
        key = row[dimension].strip() or "UNSPECIFIED"
        if name == "us_fda_regulatory_enforcement_landscape":
            # Derived groups are disjoint by sector/class/state/month.
            value = row.get("distinct_reports_in_sample") or ""
            if not re.fullmatch(r"\d+", value):
                raise ValueError("FDA_SEGMENT_MEASUREMENT_INVALID")
            counts[key] += int(value)
        else:
            # For healthcare we count *published service-territory groups*;
            # never sum overlapping providers/locations as unique people.
            counts[key] += 1
    if len(counts) > MAX_SEGMENTS_PER_VIEW:
        raise ValueError("RESEARCH_DIMENSION_CARDINALITY_HOLD")
    return [
        {"dimension": dimension, "value": key,
         "metric": metric, "observed_sample_count": count,
         "not_independently_verified_customer_demand": True,
         "commercial_forecast_input_admitted": False}
        for key, count in sorted(counts.items())
    ]


def _validate_owner(root: Path, dataset_root: Path,
                    now: datetime) -> tuple[dict, dict, list[dict]]:
    sources = _read_receipt(root / SOURCE_RECEIPT, SOURCE_SCHEMA)
    views = _read_receipt(root / VIEW_RECEIPT, VIEW_SCHEMA)
    if (sources.get("customer_delivery_authorized") is not False
            or sources.get("source_redistribution_approved") is not False
            or sources.get("commercial_sales_authorized") is not False
            or views.get("customer_delivery_authorized") is not False
            or views.get("sales_authorized") is not False
            or views.get("public_marketplace_enabled") is not False):
        raise ValueError("BROKERAGE_OWNER_AUTHORITY_MISMATCH")
    src_state, view_state = sources.get("datasets"), views.get("views")
    if not isinstance(src_state, dict) or set(src_state) != set(SOURCES):
        raise ValueError("BROKERAGE_SOURCE_INVENTORY_MISMATCH")
    if not isinstance(view_state, dict) or set(view_state) != set(VIEWS):
        raise ValueError("BROKERAGE_VIEW_INVENTORY_MISMATCH")
    inspected: list[dict] = []
    for key, (_, _, _, publisher) in SOURCES.items():
        r = src_state[key]
        if (not isinstance(r, dict) or r.get("quality_pass") is not True
                or r.get("source_status") not in (
                    "VERIFIED_UNCHANGED", "VERIFIED_CHANGED")
                or r.get("licence_release_approved") is not False
                or r.get("customer_delivery_authorized") is not False
                or r.get("commercial_sales_authorized") is not False
                or r.get("publisher") != publisher):
            raise ValueError("BROKERAGE_UPSTREAM_SOURCE_HOLD")
        observed_at = datetime.fromisoformat(r["last_success_at"])
        if observed_at.utcoffset() is None or observed_at > now + timedelta(minutes=5):
            raise ValueError("UPSTREAM_SOURCE_TIMESTAMP_INVALID")
        # Expired publisher-specific cadence is a held source, not live data.
        last_check = datetime.fromisoformat(r["last_checked_at"])
        if last_check.utcoffset() is None or last_check > now + timedelta(minutes=5):
            raise ValueError("UPSTREAM_SOURCE_CHECK_TIMESTAMP_INVALID")
        freshness_hours = SOURCES[key][0]
        if now - last_check > timedelta(hours=freshness_hours + 2):
            raise ValueError("BROKERAGE_UPSTREAM_OVERDUE_HOLD")
        data = _read_source_bytes(dataset_root / (key + ".csv"), r["source_snapshot_sha256"])
        rows = _decode_csv(data, HEADERS[key], r["row_count"])
        inspected.append({
            "dataset_id": key, "kind": "original_source", "source_id": key,
            "sha256": _sha(data), "rows": len(rows),
            "publisher": publisher,
            "publisher_url": r.get("source_url"),
            "publisher_last_success_at": r.get("last_success_at"),
            "publisher_last_checked_at": r.get("last_checked_at"),
            "refresh_hours": freshness_hours,
            "sample_not_complete_population": r.get("sample_not_full_population", True),
            "source_publication_metadata": r.get("publisher_publication_metadata") or {},
            "columns": list(HEADERS[key]), "data_bytes": data,
            "source_snapshot_sha256": r["source_snapshot_sha256"],
            "research_scope": "INTERNAL_PUBLISHER_RESEARCH_NOT_CUSTOMER_DATA",
            "segments": [],
        })
    for key, spec in VIEWS.items():
        r = view_state[key]
        src = src_state[spec["source_id"]]
        if (not isinstance(r, dict) or r.get("status") != "VIEW_VERIFIED_INTERNAL"
                or r.get("customer_delivery_authorized") is not False
                or r.get("sales_authorized") is not False
                or r.get("resale_licence_cleared") is not False
                or r.get("source_sha256") != src["source_snapshot_sha256"]):
            raise ValueError("BROKERAGE_DERIVED_VIEW_HOLD")
        data = _read_source_bytes(dataset_root / (key + ".csv"), r["view_sha256"])
        rows = _decode_csv(data, VIEWS[key]["columns"], r["row_count"])
        inspected.append({
            "dataset_id": key, "kind": "derived_research_view",
            "source_id": spec["source_id"],
            "sha256": _sha(data), "rows": len(rows),
            "publisher": src["publisher"], "publisher_url": r.get("publisher_source_url"),
            "source_snapshot_sha256": r["source_sha256"],
            "sample_not_complete_population": True,
            "research_scope": SCOPES[key], "sku": spec["sku"],
            "columns": list(VIEWS[key]["columns"]),
            "data_bytes": data,
            "segments": _segments(key, rows),
        })
    return sources, views, inspected


def import_brokerage_research_inputs(
    root: str | Path, *, dataset_root: Path | None = None,
    now: datetime | None = None, allow_noncanonical: bool = False,
) -> dict[str, Any]:
    """Import nine verified datasets atomically under the existing source owner.

    The latest registry is written LAST, after all source objects exist.
    Never grants model training, production inference, cross-tenant access,
    customer distribution, or sale. No additional timer or network call.
    """
    root = Path(root).resolve()
    if root != Path("/srv/empire_os") and not allow_noncanonical:
        return {"status": "NONCANONICAL_RESEARCH_IMPORT_HELD",
                "source_datasets_admitted": 0, "derived_views_admitted": 0}
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.utcoffset() is None:
        raise ValueError("RESEARCH_IMPORT_CLOCK_TZ_REQUIRED")
    timestamp = timestamp.astimezone(timezone.utc)
    original_root = dataset_root or DEFAULT_ORIGINAL_DATA
    _, _, items = _validate_owner(root, original_root, timestamp)
    private_root = root / INDEX_PATH.parent
    if private_root.is_symlink():
        raise ValueError("PRIVATE_CLOUD_DIRECTORY_SYMLINK_HELD")
    private_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(private_root, 0o700)
    object_root = private_root / "objects"
    records = []
    new_objects = 0
    for item in items:
        destination = object_root / (item["dataset_id"] + "_" +
                                     item["sha256"] + ".csv")
        if destination.exists():
            stored = _read_source_bytes(destination, item["sha256"])
            if stored != item["data_bytes"]:
                raise ValueError("EXISTING_CLOUD_OBJECT_CONTENT_CONFLICT")
        else:
            _atomic_secure(destination, item["data_bytes"])
            new_objects += 1
        metadata = {k: v for k, v in item.items() if k != "data_bytes"}
        metadata["object_id"] = destination.name
        metadata["internal_only"] = True
        metadata["tenant_id"] = None
        metadata["tenant_exposure_allowed"] = False
        metadata["source_evidence_digest_verified"] = True
        metadata["commercial_feature_admission"] = "RESEARCH_ONLY"
        records.append(metadata)
    total_source_rows = sum(x["rows"] for x in records if x["kind"] == "original_source")
    total_view_rows = sum(x["rows"] for x in records if x["kind"] == "derived_research_view")
    index = {
        "schema": SCHEMA,
        "generated_at": timestamp.isoformat(timespec="seconds"),
        "status": "VERIFIED_BROKERAGE_RESEARCH_INPUTS_INTERNAL",
        "owner": "ORIGINAL_DATA_BROKERAGE_SOURCE_MINING",
        "consumer": "EXISTING_PREDICTIVE_CLOUD_RESEARCH_LANE",
        "source_datasets_admitted": len(SOURCES),
        "derived_views_admitted": len(VIEWS),
        "source_rows_accessible": total_source_rows,
        "derived_view_rows_accessible": total_view_rows,
        "not_additive_source_and_view_rows": True,
        "dataset_records": records,
        "public_access": False,
        "tenant_exposure_authorized": False,
        "source_redistribution_authorized": False,
        "customer_downloads_authorized": False,
        "production_training_samples_admitted": 0,
        "production_forecast_features_admitted": 0,
        "authenticated_tenant_forecast_outcomes_verified": 0,
        "model_calibration_ready": False,
        "actual_revenue": False,
        "outbound_sent": False,
        "database_writes": False,
        "new_scheduler_created": False,
        "original_brokerage_retained_as_source_of_truth": True,
        "execution_authority": "none",
    }
    _atomic_secure(root / INDEX_PATH,
                   (json.dumps(index, sort_keys=True, indent=2) + "\n").encode())
    return {
        "status": index["status"],
        "source_datasets_admitted": len(SOURCES),
        "derived_views_admitted": len(VIEWS),
        "source_rows_accessible": total_source_rows,
        "derived_view_rows_accessible": total_view_rows,
        "new_objects_written": new_objects,
        "all_source_checksums_verified": True,
        "production_training_samples_admitted": 0,
        "customer_downloads_authorized": False,
        "execution_authority": "none",
    }


def read_internal_brokerage_rows(
    root: str | Path, dataset_id: str, *,
    offset: int = 0, limit: int = 50,
    filters: dict[str, str] | None = None,
    system_research_context: str = "",
    now: datetime | None = None,
) -> dict:
    """Read *actual* Cloud-ingested rows, internal-only; no customer endpoint.

    This is not an HTTP/tenant-facing method. A documented internal purpose
    must be supplied. Never accept a claimed tenant ID as an authorization.
    The underlying OS directory is 0700, files 0600 and content rehashed.
    """
    if system_research_context != "EMPIRE_INTERNAL_RESEARCH_OBSERVE":
        raise PermissionError("SYSTEM_RESEARCH_CONTEXT_REQUIRED")
    if not isinstance(dataset_id, str) or dataset_id not in set(SOURCES) | set(VIEWS):
        raise ValueError("UNKNOWN_BROKERAGE_DATASET")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("RESEARCH_ROW_PAGE_LIMIT_REQUIRED")
    if type(offset) is not int or not 0 <= offset <= 100_000:
        raise ValueError("RESEARCH_ROW_OFFSET_INVALID")
    if filters is not None and (
            type(filters) is not dict or len(filters) > 3
            or not all(isinstance(k, str) and isinstance(v, str) and len(v) <= 100
                       for k, v in filters.items())):
        raise ValueError("RESEARCH_ROW_FILTER_INVALID")
    root = Path(root).resolve()
    index = _read_receipt(root / INDEX_PATH, SCHEMA)
    if (index.get("status") != "VERIFIED_BROKERAGE_RESEARCH_INPUTS_INTERNAL"
            or index.get("tenant_exposure_authorized") is not False
            or index.get("source_redistribution_authorized") is not False
            or index.get("production_training_samples_admitted") != 0):
        raise ValueError("CLOUD_RESEARCH_INDEX_AUTHORITY_HELD")
    records = index.get("dataset_records")
    if not isinstance(records, list) or len(records) != len(SOURCES) + len(VIEWS):
        raise ValueError("CLOUD_RESEARCH_INDEX_INCOMPLETE")
    match = [x for x in records if x.get("dataset_id") == dataset_id]
    if len(match) != 1:
        raise ValueError("CLOUD_RESEARCH_DATASET_NOT_UNIQUE")
    row = match[0]
    if (row.get("tenant_exposure_allowed") is not False
            or row.get("source_evidence_digest_verified") is not True
            or row.get("commercial_feature_admission") != "RESEARCH_ONLY"):
        raise ValueError("CLOUD_RESEARCH_DATASET_AUTHORITY_HELD")
    # A previously ingested object is not automatically current. Recheck the
    # LIVE original-owner receipts before every internal research read.
    original = _read_receipt(root / SOURCE_RECEIPT, SOURCE_SCHEMA)
    source = (original.get("datasets") or {}).get(row["source_id"])
    if (original.get("customer_delivery_authorized") is not False
            or original.get("source_redistribution_approved") is not False
            or not isinstance(source, dict)
            or source.get("source_status") not in ("VERIFIED_UNCHANGED", "VERIFIED_CHANGED")
            or source.get("quality_pass") is not True
            or source.get("source_snapshot_sha256") != row["source_snapshot_sha256"]
            or source.get("customer_delivery_authorized") is not False):
        raise ValueError("CLOUD_RESEARCH_SOURCE_STALE_OR_UNTRUSTED")
    try:
        checked = datetime.fromisoformat(source["last_checked_at"])
        current_time = now or datetime.now(timezone.utc)
        if current_time.utcoffset() is None:
            raise ValueError("INVALID_RESEARCH_READER_CLOCK")
        current_time = current_time.astimezone(timezone.utc)
        if (checked.utcoffset() is None or checked > current_time + timedelta(minutes=5)
                or current_time - checked > timedelta(hours=SOURCES[row["source_id"]][0] + 2)):
            raise ValueError("SOURCE_REFRESH_OVERDUE")
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("CLOUD_RESEARCH_SOURCE_REFRESH_NOT_CURRENT") from exc
    if dataset_id in VIEWS:
        current_views = _read_receipt(root / VIEW_RECEIPT, VIEW_SCHEMA)
        current = (current_views.get("views") or {}).get(dataset_id)
        if (not isinstance(current, dict)
                or current.get("status") != "VIEW_VERIFIED_INTERNAL"
                or current.get("view_sha256") != row["sha256"]
                or current.get("source_sha256") != row["source_snapshot_sha256"]
                or current.get("customer_delivery_authorized") is not False):
            raise ValueError("CLOUD_RESEARCH_VIEW_STALE_OR_UNTRUSTED")
    expected_header = (HEADERS[dataset_id] if dataset_id in SOURCES
                       else VIEWS[dataset_id]["columns"])
    object_name = dataset_id + "_" + row["sha256"] + ".csv"
    if row.get("object_id") != object_name:
        raise ValueError("CLOUD_RESEARCH_OBJECT_ID_MISMATCH")
    p = root / INDEX_PATH.parent / "objects" / object_name
    data = _read_source_bytes(p, row["sha256"])
    data_rows = _decode_csv(data, expected_header, row["rows"])
    selected = filters or {}
    if any(k not in expected_header for k in selected):
        raise ValueError("CLOUD_RESEARCH_FILTER_FIELD_UNAVAILABLE")
    data_rows = [r for r in data_rows if all(r[k] == v for k, v in selected.items())]
    return {
        "dataset_id": dataset_id, "scope": row["research_scope"],
        "source_sha256": row["source_snapshot_sha256"],
        "dataset_sha256": row["sha256"],
        "matched_rows_in_current_snapshot": len(data_rows),
        "offset": offset, "limit": limit,
        "rows": data_rows[offset:offset + limit],
        "research_only": True,
        "tenant_exposure_authorized": False,
        "training_authorized": False,
        "commercial_forecast_ready": False,
    }
