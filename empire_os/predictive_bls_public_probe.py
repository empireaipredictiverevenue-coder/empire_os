"""Explicit read-only public BLS series health check for Predictive Revenue.

One fixed series, one user-requested HTTPS GET. This is source discovery only:
never an independently approved Economic/Finance source owner packet, supplier
invoice, prediction calibration label, or permission to alter production.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from typing import Any

SERIES_ID = "PCU327320327320"
# BLS original series-reference notice: ready-mix concrete manufacturing.
SERIES_REFERENCE = ("https://www.bls.gov/ppi/notices/2013/"
                    "ppi-introduces-regional-detail-for-ready-mix-concrete-indexes.htm")
API_URL = f"https://api.bls.gov/publicAPI/v1/timeseries/data/{SERIES_ID}"
SCHEMA = "empire.predictive_revenue.bls_public_v1_source_probe.v1"
MAX_BYTES = 256_000
MAX_POINTS = 60
NUMERIC = re.compile(r"^\d{1,8}(?:\.\d{1,6})?$")


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "BLS_PUBLIC_SOURCE_PROBE_HOLD", "hold_code": reason,
        "official_public_series_id": SERIES_ID,
        "official_series_reference": SERIES_REFERENCE,
        "series_subject": "Ready-mix concrete manufacturing PPI",
        "source_last_month": None, "latest_published_index": None,
        "prior_year_comparable_index": None,
        "published_index_yoy_percent": None,
        "reported_preliminary": None, "source_data_points": None,
        "independent_finance_source_owner_approval": False,
        "original_supplier_quote_authenticated": False,
        "company_material_cost_or_profit_verified": False,
        "market_specific_cost_model_calibration_allowed": False,
        "automatic_campaign_or_spending_authority": False,
        "database_writes": False, "source_files_written": False,
        "outbound_sent": False, "execution_authority": "none",
    }


def review_public_bls_v1_response(data: Any, *, as_of: datetime) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware source review clock required")
    if (not isinstance(data, dict) or data.get("status") != "REQUEST_SUCCEEDED"
            or data.get("message") != [] or not isinstance(data.get("Results"), dict)):
        return _hold("BLS_API_STATUS_OR_MESSAGES_HOLD")
    series = data["Results"].get("series")
    if (not isinstance(series, list) or len(series) != 1
            or not isinstance(series[0], dict)
            or series[0].get("seriesID") != SERIES_ID):
        return _hold("BLS_SERIES_ID_OR_COVERAGE_HOLD")
    rows = series[0].get("data")
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_POINTS:
        return _hold("BLS_ORIGINAL_MONTHS_HOLD")
    dates: dict[tuple[int, int], tuple[Decimal, bool]] = {}
    annual_skipped = 0
    try:
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("bad point")
            year, month = row.get("year"), row.get("period")
            # BLS v1 can include M13=Annual even on a monthly request.
            # Validate its original class but do not use it as December.
            if month == "M13":
                if (not isinstance(year, str) or not re.fullmatch(r"20\d\d", year)
                        or row.get("periodName") != "Annual"):
                    raise ValueError("untrusted annual source period")
                annual_skipped += 1
                continue
            raw = row.get("value")
            if (not isinstance(year, str) or not re.fullmatch(r"20\d\d", year)
                    or not isinstance(month, str)
                    or not re.fullmatch(r"M(?:0[1-9]|1[0-2])", month)
                    or not isinstance(raw, str) or not NUMERIC.fullmatch(raw)):
                raise ValueError("bad period or index")
            key = (int(year), int(month[1:]))
            if key > (as_of.year, as_of.month) or key in dates:
                raise ValueError("future or duplicate period")
            value = Decimal(raw)
            if not value.is_finite() or value <= 0:
                raise ValueError("nonpositive index")
            footnotes = row.get("footnotes")
            if not isinstance(footnotes, list) or len(footnotes) > 12:
                raise ValueError("bad footnote structure")
            prelim = any(
                isinstance(note, dict) and note.get("code") == "P"
                for note in footnotes
            )
            if not all(isinstance(note, dict) for note in footnotes):
                raise ValueError("bad footnote")
            dates[key] = (value, prelim)
    except (InvalidOperation, TypeError, ValueError):
        return _hold("BLS_INVALID_OR_CONFLICTING_SOURCE_POINT")
    latest = max(dates)
    prior = (latest[0] - 1, latest[1])
    # Do not declare a time-trend percentage without comparable data.
    if prior not in dates:
        return _hold("BLS_PRIOR_YEAR_MONTH_NOT_AVAILABLE")
    from datetime import timedelta
    observed_at = datetime(latest[0], latest[1], 1, tzinfo=timezone.utc)
    if as_of.astimezone(timezone.utc) - observed_at > timedelta(days=150):
        return _hold("BLS_OBSERVATION_OUT_OF_DATE")
    current, prelim = dates[latest]
    old = dates[prior][0]
    growth = (current / old - Decimal(1)) * Decimal(100)
    return {
        **_hold("NONE"),
        "status": "BLS_PUBLIC_MONTHLY_INDEX_OBSERVED_RESEARCH_ONLY",
        "hold_code": None,
        "source_last_month": f"{latest[0]:04d}-{latest[1]:02d}",
        "latest_published_index": str(current),
        "prior_year_comparable_index": str(old),
        "published_index_yoy_percent": round(float(growth), 4),
        "reported_preliminary": prelim,
        "source_data_points": len(dates),
        "annual_m13_points_excluded_from_monthly_analysis": annual_skipped,
        "source_api": "Official BLS v1 public GET (unregistered)",
        "source_series_owner": "U.S. Bureau of Labor Statistics",
        "original_price_index_is_actual_material_invoice": False,
        "next_owner": "existing_economic_source_materials_and_finance_owner",
        "next_action": "APPROVE_OFFICIAL_SERIES_SEMANTICS_AND_MAP_TO_REAL_COST_BASELINE",
    }


def probe_bls_public_v1(*, as_of: datetime) -> dict[str, Any]:
    """Single bounded HTTPS request; not a daemon, API-key user or feed writer."""
    try:
        req = Request(API_URL, headers={
            "Accept": "application/json",
            "User-Agent": "Empire-Predictive-Research/1.0",
        })
        with urlopen(req, timeout=10) as response:
            final_url = response.geturl()
            p = urlparse(final_url)
            if (p.scheme != "https" or p.hostname != "api.bls.gov"
                    or p.path != f"/publicAPI/v1/timeseries/data/{SERIES_ID}"):
                return _hold("BLS_UNEXPECTED_API_REDIRECT")
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return _hold("BLS_API_RESPONSE_TOO_LARGE")
        return review_public_bls_v1_response(json.loads(body), as_of=as_of)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return _hold("BLS_OFFICIAL_API_READ_FAILED")
