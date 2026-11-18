"""Bounded FDA regulatory research under the ORIGINAL Data Brokerage source owner.

Research publication analysis ONLY. This is NOT patient data, mass-tort
claimant discovery, case evidence, product-safety alerting or a recall status
monitor. openFDA enforcement statuses are not maintained as live lifecycles.
Never export device GMDN terminology or person-contact details.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from urllib.parse import urlencode
import json
import re

from empire_os.data_brokerage_enterprise_feed import _get

API_ROOT = "https://api.fda.gov"
ENDPOINTS = ("food", "drug", "device")
SAMPLE_PER_SECTOR = 400
REPORT_URL = "https://open.fda.gov/apis/"
PUBLISHER_RIGHTS = "https://open.fda.gov/license/"
CORPORATE = re.compile(
    r"\b(incorporated|inc\.?|llc|l\.l\.c\.?|corp\.?|corporation|"
    r"ltd\.?|limited|plc|llp|company|co\.|laboratories|pharmaceuticals|"
    r"biopharma|manufacturing|medical devices)\b", re.I
)
ALLOWED_CLASSES = {"Class I", "Class II", "Class III", "Not Yet Classified"}
REQUIRED_KEYS = {"recall_number", "report_date", "classification", "event_id",
                 "product_type", "recall_initiation_date"}


def _safe_text(value: object, maximum: int = 300) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or "")).strip()
    if text and text[0] in "=+-@":
        text = "'" + text  # CSV spreadsheet formula injection defence.
    return text[:maximum]


def _parse_report_date(value: object) -> str:
    raw = str(value or "")
    if not re.fullmatch(r"20\d{6}", raw):
        raise ValueError("FDA_REPORT_DATE_MALFORMED")
    return datetime.strptime(raw, "%Y%m%d").date().isoformat()


def _validate_enforcement_record(record: dict, sector: str, stamp: str) -> dict:
    if not isinstance(record, dict) or not REQUIRED_KEYS.issubset(record):
        raise ValueError("FDA_ENFORCEMENT_SOURCE_SCHEMA_MISMATCH")
    recall_number = str(record.get("recall_number") or "").strip()
    if not re.fullmatch(r"[A-Z]{1,3}-\d{3,7}-\d{4}", recall_number):
        raise ValueError("FDA_RECALL_ID_INVALID")
    classification = str(record.get("classification") or "").strip()
    if classification not in ALLOWED_CLASSES:
        raise ValueError("FDA_RECALL_CLASSIFICATION_UNKNOWN")
    issued = _parse_report_date(record.get("report_date"))
    firm_raw = str(record.get("recalling_firm") or "").strip()
    corporate_candidate = _safe_text(firm_raw, 160) if CORPORATE.search(firm_raw) else ""
    return {
        "record_id": sector + ":" + recall_number,
        "sector": sector, "recall_number": recall_number,
        "event_id": _safe_text(record.get("event_id"), 40),
        "report_date": issued,
        "reported_classification": classification,
        "recall_initiation_date": _safe_text(record.get("recall_initiation_date"), 15),
        "state": _safe_text(record.get("state"), 100),
        "country": _safe_text(record.get("country"), 100),
        "published_corporate_name_candidate": corporate_candidate,
        "company_identity_verified": "false",
        "product_type": _safe_text(record.get("product_type"), 80),
        "published_product_summary": _safe_text(record.get("product_description"), 240),
        "publisher_reported_reason": _safe_text(record.get("reason_for_recall"), 240),
        "source_url": REPORT_URL + sector + "/enforcement/",
        "source_legal_terms": "CC0_GENERAL_NO_GMDN_FIELDS",
        "observed_at": stamp,
    }


def _bounded_fda_json(url: str) -> dict:
    # Only openFDA device records exceed the default 4 MB JSON byte cap;
    # never relax the shared original source reader's default budget.
    doc = json.loads(_get(url, limit=8_000_000))
    if not isinstance(doc, dict):
        raise ValueError("FDA_SOURCE_DOCUMENT_MALFORMED")
    return doc


def fetch_research_sample(stamp: str):
    """Three official requests, max 400 rows per category. No local key."""
    try:
        timestamp = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        raise ValueError("STAMP_MALFORMED")
    if timestamp.utcoffset() is None:
        raise ValueError("STAMP_TIMEZONE_MISSING")
    records, publication, populations, excluded = [], {}, {}, {}
    for sector in ENDPOINTS:
        endpoint = API_ROOT + "/" + sector + "/enforcement.json"
        url = endpoint + "?" + urlencode({
            "sort": "report_date:desc", "limit": SAMPLE_PER_SECTOR,
        })
        doc = _bounded_fda_json(url)
        meta = doc.get("meta") or {}
        updated = meta.get("last_updated")
        try:
            datetime.strptime(updated, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError("FDA_PUBLISHER_DATE_MISSING")
        result_count = (meta.get("results") or {}).get("total")
        if not isinstance(result_count, int) or result_count < SAMPLE_PER_SECTOR:
            raise ValueError("FDA_SOURCE_COUNT_UNEXPECTED")
        items = doc.get("results")
        if not isinstance(items, list) or len(items) != SAMPLE_PER_SECTOR:
            raise ValueError("FDA_SOURCE_PAGE_INCOMPLETE")
        publication[sector] = updated
        populations[sector] = result_count
        excluded[sector] = 0
        for item in items:
            if str(item.get("recall_number") or "").strip().upper() in ("", "N/A"):
                excluded[sector] += 1
                continue
            records.append(_validate_enforcement_record(item, sector, stamp))
    if len({r["record_id"] for r in records}) != len(records):
        raise ValueError("FDA_DUPLICATE_RECALL_ID")
    return records, REPORT_URL, {
        "source_network_requests": 3,
        "publisher_last_updated_by_sector": publication,
        "publisher_total_reported_by_sector": populations,
        "excluded_missing_or_na_recall_id_by_sector": excluded,
        "source_records_returned_by_publisher": SAMPLE_PER_SECTOR * len(ENDPOINTS),
        "source_records_accepted": len(records),
        "window_latest_report_date": max(r["report_date"] for r in records),
        "source_policy": "RESEARCH_NOT_RECALL_LIFECYCLE_OR_PUBLIC_ALERT",
        "source_terms_url": PUBLISHER_RIGHTS,
        "raw_resale_approved": False,
    }


def build_regulatory_landscape(rows: list[dict]) -> list[dict]:
    """Published report classifications only; sample trend, not true incidence."""
    groups = defaultdict(lambda: {"ids": set(), "organizations": set(), "last": ""})
    for r in rows:
        if r.get("sector") not in ENDPOINTS or not r.get("report_date"):
            raise ValueError("INVALID_FDA_ANALYTICAL_ROW")
        key = (r["sector"], r["reported_classification"], r["state"] or "UNSPECIFIED",
               r["report_date"][:7])
        d = groups[key]
        d["ids"].add(r["record_id"])
        if r.get("published_corporate_name_candidate"):
            d["organizations"].add(r["published_corporate_name_candidate"])
        d["last"] = max(d["last"], r["report_date"])
    return [{
        "sector": key[0], "publisher_classification": key[1],
        "published_state": key[2], "report_month": key[3],
        "distinct_reports_in_sample": len(value["ids"]),
        "unverified_corporate_labels_in_sample": len(value["organizations"]),
        "latest_report_date_in_group": value["last"],
        "evidence_flag": "FDA_RESEARCH_SAMPLE_NOT_CLAIMS_LITIGATION_OR_SAFETY_ALERT",
    } for key, value in sorted(groups.items())]
