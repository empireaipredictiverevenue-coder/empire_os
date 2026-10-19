"""Privacy-preserving census of historical Empire USB market archives.

Read only the chosen local file. Do not return row values, names, emails,
phone numbers, websites, ZIPs, addresses, forecast amounts per record,
credentials or other identifying data. Historical projections are NOT
verified commercial opportunities or earned revenue.

Does not import into EmpireDB, promote buyers, tune predictive models,
trigger a scan, authorize marketing, or perform any network I/O.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
import csv
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "empire.legacy_market_archive_census.v1"
MAX_JSON_BYTES = 8_000_000
MAX_CSV_BYTES = 8_000_000
MAX_RECORDS = 100_000
MAX_METROS = 50
MAX_FIELDS = 60
NAME_RE = re.compile(r"^[A-Za-z0-9_ ()-]+$")


def _file(path: Path, *, suffix: str, max_bytes: int) -> Path:
    if not isinstance(path, Path) or not path.is_file() or path.is_symlink():
        raise ValueError("local_regular_archive_required")
    if path.suffix.lower() != suffix:
        raise ValueError("archive_type_not_allowed")
    if not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("archive_size_out_of_bounds")
    return path


def _safe_result(kind: str, statistics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OFFLINE_READ_ONLY",
        "source_kind": kind,
        "source_status": "HISTORICAL_UNVERIFIED_RESEARCH_ONLY",
        "statistics": dict(statistics),
        "distinct_identities_are_not_verified_buyers": True,
        "legacy_forecasts_are_not_realised_revenue": True,
        "consent_and_suppression_proven": False,
        "independent_source_rights_verified": False,
        "canonical_empiredb_identity_reconciled": False,
        "source_ready_for_canonical_import": False,
        "model_calibration_authorized": False,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def review_metro_json(path: Path) -> dict[str, Any]:
    """Aggregate old metro file without emitting company rows or identifiers."""
    archive = _file(path, suffix=".json", max_bytes=MAX_JSON_BYTES)
    with archive.open("r", encoding="utf-8-sig") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("metros"), list):
        raise ValueError("invalid_metro_archive_schema")
    metros = data["metros"]
    if len(metros) > MAX_METROS or not isinstance(data.get("summary"), dict):
        raise ValueError("unbounded_or_invalid_metro_archive")
    total = 0
    names: set[str] = set()
    websites: set[str] = set()
    emails: set[str] = set()
    source_count = 0
    confidence_values: set[str] = set()
    all_keys = set()
    for metro in metros:
        if not isinstance(metro, dict) or not isinstance(metro.get("companies"), list):
            raise ValueError("invalid_metro_record")
        companies = metro["companies"]
        if total + len(companies) > MAX_RECORDS:
            raise ValueError("unbounded_company_archive")
        for record in companies:
            if not isinstance(record, dict) or len(record) > MAX_FIELDS:
                raise ValueError("invalid_company_record")
            total += 1
            names.add(str(record.get("name") or "").strip().casefold())
            websites.add(str(record.get("website") or "").strip().casefold())
            emails.add(str(record.get("email") or "").strip().casefold())
            all_keys.update(str(k) for k in record)
            confidence_values.add(str(record.get("confidence")))
            if (record.get("source_url") and record.get("source_observed_at")
                    and record.get("source_use_rights_verified") is True):
                source_count += 1
    # Even with full provenance, an independent licensed-source and
    # canonical company identity review is a separate authority.
    return _safe_result("legacy_metro_json", {
        "metro_groups": len(metros),
        "company_rows": total,
        "unique_names": len(names) - ("" in names),
        "unique_websites": len(websites) - ("" in websites),
        "unique_emails": len(emails) - ("" in emails),
        "duplicate_name_rows": total - len(names) + ("" in names),
        "explicit_source_observation_rights_rows": source_count,
        "unverified_source_rows": total - source_count,
        "distinct_confidence_values": len(confidence_values),
        "has_verified_revenue_field": "realised_revenue_verified" in all_keys,
        "legacy_summary_is_not_source_evidence": True,
    })


def review_expected_value_csv(path: Path) -> dict[str, Any]:
    """Review row-level modelled values; no values or ZIPs in output."""
    archive = _file(path, suffix=".csv", max_bytes=MAX_CSV_BYTES)
    keys: set[tuple[str, str, str]] = set()
    categories: set[str] = set()
    distinct_zip: set[str] = set()
    total = 0
    invalid_values = 0
    complete_provenance = 0
    fieldnames = []
    with archive.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        if (len(fieldnames) > MAX_FIELDS or len(fieldnames) != len(set(fieldnames))
                or not {"category", "service", "zipcode", "expected_value"}.issubset(fieldnames)):
            raise ValueError("unsupported_expected_value_schema")
        for row in reader:
            total += 1
            if total > MAX_RECORDS:
                raise ValueError("unbounded_expected_value_rows")
            if not isinstance(row, dict) or None in row:
                raise ValueError("malformed_expected_value_csv_row")
            category = str(row.get("category") or "").strip().casefold()
            service = str(row.get("service") or "").strip().casefold()
            zipcode = str(row.get("zipcode") or "").strip()
            keys.add((category, service, zipcode))
            categories.add(category)
            distinct_zip.add(zipcode)
            try:
                from decimal import Decimal
                value = Decimal(str(row["expected_value"]))
                if not value.is_finite() or value < 0:
                    invalid_values += 1
            except (ArithmeticError, TypeError, ValueError):
                invalid_values += 1
            if (row.get("source_url") and row.get("verified_outcome_ref")
                    and row.get("model_version") and row.get("source_use_rights_verified") == "true"):
                complete_provenance += 1
    return _safe_result("legacy_expected_value_csv", {
        "data_rows": total,
        "distinct_category_service_zip_keys": len(keys),
        "duplicate_dimension_key_rows": total - len(keys),
        "distinct_zipcodes_count_not_exported": len(distinct_zip),
        "distinct_categories": len(categories),
        "invalid_modelled_values": invalid_values,
        "rows_with_explicit_source_and_verified_outcome_evidence": complete_provenance,
        "has_observed_outcome_column": "actual_outcome" in fieldnames,
        "has_verified_revenue_column": "realised_revenue_verified" in fieldnames,
        "historical_expected_value_is_modelled_only": True,
    })
