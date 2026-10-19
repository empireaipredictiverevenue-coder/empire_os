"""Offline parse of user-obtained California CSLB contractor licence CSV.

No network, no scraping, no DB writes, no email/phone export. Requires a
download from the official CSLB licence portal, separate terms review and
current licence verification before any business outreach or data resale.
"""
from __future__ import annotations
from collections import Counter
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from collections.abc import Mapping

from empire_os.recc_supply_sweep import _atomic_private_json
SCHEMA = "empire.us_cslb_contractor_csv_review.v1"
MAX_CSV_BYTES = 1_000_000
MAX_ROWS = 1000
SECTORS = {
    "C-39": "roofing", "C39": "roofing",
    "C-20": "hvac", "C20": "hvac",
    "C-46": "solar", "C46": "solar",
}
ALIASES = {
    "license_no": ("license number", "license #", "license no", "license_no"),
    "company": ("business name", "company name", "business_name"),
    "classification": ("classifications", "classification", "classification(s)", "class"),
    "status": ("license status", "status"),
    "city": ("city", "business city"),
}


def _pick(row: Mapping[str, str], names: tuple[str, ...]) -> str:
    low = {str(k).casefold().strip(): str(v or "").strip() for k,v in row.items()}
    return next((low[name] for name in names if low.get(name)), "")


def review_official_cslb_csv(csv_text: str, *, source_document_ref: str,
                             rights_review_ref: str) -> dict:
    if (not isinstance(csv_text, str)
            or len(csv_text.encode("utf-8")) > MAX_CSV_BYTES):
        raise ValueError("cslb_file_unbounded")
    if not all(isinstance(x, str) and 8 <= len(x) <= 200 for x in (
        source_document_ref, rights_review_ref
    )):
        raise ValueError("official_download_rights_receipts_missing")
    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames or len(reader.fieldnames) > 60:
        raise ValueError("cslb_invalid_csv_headers")
    headers = {h.casefold().strip() for h in reader.fieldnames if h is not None}
    if not all(any(n in headers for n in ALIASES[field])
               for field in ("license_no", "company", "classification", "status")):
        raise ValueError("cslb_expected_official_columns_missing")
    observations = []
    seen = set()
    rejected = Counter()
    for index, record in enumerate(reader):
        if index >= MAX_ROWS:
            raise ValueError("cslb_csv_row_budget_exceeded")
        if not isinstance(record, Mapping):
            rejected["invalid_row"] += 1
            continue
        no = _pick(record, ALIASES["license_no"])
        company = _pick(record, ALIASES["company"])
        classes = _pick(record, ALIASES["classification"]).upper()
        status = _pick(record, ALIASES["status"]).casefold()
        if not re.fullmatch(r"\d{5,10}", no) or not 4 <= len(company) <= 200:
            rejected["no_company_license_id"] += 1
            continue
        if "active" not in status or "inactive" in status:
            rejected["licence_not_active"] += 1
            continue
        found = sorted({v for key,v in SECTORS.items()
                        if re.search(r"(?<![A-Z0-9])" + re.escape(key) + r"(?![A-Z0-9])", classes)})
        if not found:
            rejected["not_roofing_hvac_solar_class"] += 1
            continue
        if no in seen:
            rejected["duplicate_license_number"] += 1
            continue
        seen.add(no)
        observations.append({
            "source_id": "us_cslb_official_contractor_csv",
            "licence_number": no, "business_name": company,
            "state": "CA", "country_code": "US",
            "source_document_ref": source_document_ref,
            "industry_niches": found,
            "license_status_as_downloaded": status,
            "current_license_independently_verified": False,
            "company_not_independently_verified": True,
            "canonical_empiredb_id": None,
            "source_link": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
            "outbound_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "LOCAL_OFFICIAL_FILE_REVIEW_ONLY",
        "state": "REVIEW_COMPLETED",
        "source_id": "us_cslb_official_contractor_csv",
        "source_document_sha256": sha256(csv_text.encode("utf-8")).hexdigest(),
        "local_official_source_receipt": source_document_ref,
        "source_rights_review_ref": rights_review_ref,
        "source_rows_reviewed": min(index + 1, MAX_ROWS) if "index" in locals() else 0,
        "distinct_business_licence_observations": len(observations),
        "niche_counts": dict(Counter(n for r in observations for n in r["industry_niches"])),
        "rejection_reasons": dict(rejected),
        "internal_observations": observations,
        "canonical_empiredb_writes": False,
        "commercial_exchange_added": 0,
        "outbound_authorized": False,
        "execution_authority": "none",
    }


def review_cslb_file(path: Path, *, source_document_ref: str,
                     rights_review_ref: str, private_output: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_CSV_BYTES:
        raise ValueError("cslb_file_missing_or_oversize")
    result = review_official_cslb_csv(
        path.read_text(encoding="utf-8-sig"),
        source_document_ref=source_document_ref,
        rights_review_ref=rights_review_ref,
    )
    observations = result.pop("internal_observations")
    _atomic_private_json(private_output, {
        "schema_version": SCHEMA, "observations": observations,
    })
    return result
