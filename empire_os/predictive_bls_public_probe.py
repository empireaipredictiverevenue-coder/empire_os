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
# Explicit reference catalog; names verified against BLS original-source
# series as indexed by Federal Reserve Bank of St. Louis FRED. Not a price
# quote, local geography or an approved invoice cost allocation.
SERIES_CATALOG = {
    "PCU327320327320": {
        "name": "Ready-mix concrete manufacturing PPI",
        "sector": "construction_concrete",
        "reference": "https://www.bls.gov/ppi/notices/2013/ppi-introduces-regional-detail-for-ready-mix-concrete-indexes.htm",
    },
    "PCU324122324122": {
        "name": "Asphalt shingle and coating materials manufacturing PPI",
        "sector": "roofing_materials",
        "reference": "https://fred.stlouisfed.org/series/PCU324122324122",
    },
    "PCU333415333415": {
        "name": "Air-conditioning, refrigeration and forced-air heating equipment manufacturing PPI",
        "sector": "hvac_equipment",
        "reference": "https://fred.stlouisfed.org/series/PCU333415333415",
    },
    "PCU335313335313": {
        "name": "Switchgear and switchboard apparatus manufacturing PPI",
        "sector": "electrical_grid_solar_adjacent_not_pv_module",
        "reference": "https://fred.stlouisfed.org/series/PCU335313335313",
    },
}
SERIES_REFERENCE = SERIES_CATALOG[SERIES_ID]["reference"]
API_BASE = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
API_URL = f"{API_BASE}{SERIES_ID}"
SCHEMA = "empire.predictive_revenue.bls_public_v1_source_probe.v1"
MAX_BYTES = 256_000
MAX_POINTS = 60
NUMERIC = re.compile(r"^\d{1,8}(?:\.\d{1,6})?$")


def _hold(reason: str, *, series_id: str=SERIES_ID) -> dict[str, Any]:
    if series_id not in SERIES_CATALOG:
        raise ValueError("explicit original public series catalog required")
    info=SERIES_CATALOG[series_id]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "BLS_PUBLIC_SOURCE_PROBE_HOLD", "hold_code": reason,
        "official_public_series_id": series_id,
        "official_series_reference": info["reference"],
        "series_subject": info["name"],
        "researched_sector": info["sector"],
        "sector_is_actual_supplier_quote": False,
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


def review_public_bls_v1_response(data: Any, *, as_of: datetime, series_id: str=SERIES_ID) -> dict[str, Any]:
    if series_id not in SERIES_CATALOG:
        raise ValueError("unapproved source ID cannot enter sector basket")
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware source review clock required")
    if (not isinstance(data, dict) or data.get("status") != "REQUEST_SUCCEEDED"
            or data.get("message") != [] or not isinstance(data.get("Results"), dict)):
        return _hold("BLS_API_STATUS_OR_MESSAGES_HOLD",series_id=series_id)
    series = data["Results"].get("series")
    if (not isinstance(series, list) or len(series) != 1
            or not isinstance(series[0], dict)
            or series[0].get("seriesID") != series_id):
        return _hold("BLS_SERIES_ID_OR_COVERAGE_HOLD",series_id=series_id)
    rows = series[0].get("data")
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_POINTS:
        return _hold("BLS_ORIGINAL_MONTHS_HOLD",series_id=series_id)
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
        return _hold("BLS_INVALID_OR_CONFLICTING_SOURCE_POINT",series_id=series_id)
    latest = max(dates)
    prior = (latest[0] - 1, latest[1])
    # Do not declare a time-trend percentage without comparable data.
    if prior not in dates:
        return _hold("BLS_PRIOR_YEAR_MONTH_NOT_AVAILABLE",series_id=series_id)
    from datetime import timedelta
    observed_at = datetime(latest[0], latest[1], 1, tzinfo=timezone.utc)
    if as_of.astimezone(timezone.utc) - observed_at > timedelta(days=150):
        return _hold("BLS_OBSERVATION_OUT_OF_DATE",series_id=series_id)
    current, prelim = dates[latest]
    old = dates[prior][0]
    growth = (current / old - Decimal(1)) * Decimal(100)
    return {
        **_hold("NONE",series_id=series_id),
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


def probe_bls_public_v1(*, as_of: datetime, series_id: str=SERIES_ID) -> dict[str, Any]:
    """Single bounded HTTPS request; not a daemon, API-key user or feed writer."""
    if series_id not in SERIES_CATALOG:
        raise ValueError("public series is not in catalog")
    try:
        url=f"{API_BASE}{series_id}"
        req = Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Empire-Predictive-Research/1.0",
        })
        with urlopen(req, timeout=10) as response:
            final_url = response.geturl()
            p = urlparse(final_url)
            if (p.scheme != "https" or p.hostname != "api.bls.gov"
                    or p.path != f"/publicAPI/v1/timeseries/data/{series_id}"):
                return _hold("BLS_UNEXPECTED_API_REDIRECT",series_id=series_id)
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return _hold("BLS_API_RESPONSE_TOO_LARGE",series_id=series_id)
        return review_public_bls_v1_response(json.loads(body), as_of=as_of,series_id=series_id)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return _hold("BLS_OFFICIAL_API_READ_FAILED",series_id=series_id)


def review_bls_sector_reports(reports: list[dict[str, Any]], *, as_of: datetime) -> dict[str, Any]:
    """Combine source HEALTH, never conflate different base-year index levels.

    Source collector provenance and upstream series-title mapping are still
    research observations. No independent audit, forecast or cost allocation.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware review time required")
    if not isinstance(reports, list) or len(reports) != len(SERIES_CATALOG):
        raise ValueError("complete sector source set required, including holds")
    by_id={}
    for record in reports:
        if not isinstance(record, dict):
            raise ValueError("sector result must be an original reviewed record")
        sid=record.get("official_public_series_id")
        if sid not in SERIES_CATALOG or sid in by_id:
            raise ValueError("duplicate/unknown original public series")
        if (record.get("schema_version") != SCHEMA
                or record.get("execution_authority") != "none"
                or record.get("market_specific_cost_model_calibration_allowed") is not False
                or record.get("company_material_cost_or_profit_verified") is not False
                or record.get("source_files_written") is not False
                or record.get("database_writes") is not False
                or record.get("outbound_sent") is not False
                or record.get("series_subject") != SERIES_CATALOG[sid]["name"]
                or record.get("researched_sector") != SERIES_CATALOG[sid]["sector"]):
            raise ValueError("untrusted public source authority or series identity")
        by_id[sid]=record
    if set(by_id)!=set(SERIES_CATALOG):
        raise ValueError("all original series must be present")
    cards=[by_id[k] for k in SERIES_CATALOG]
    successes=sum(
        c.get("status")=="BLS_PUBLIC_MONTHLY_INDEX_OBSERVED_RESEARCH_ONLY"
        for c in cards
    )
    return {
        "schema_version":"empire.predictive_revenue.bls_sector_source_probe.v1",
        "status": "BLS_SECTOR_PUBLIC_RESEARCH_REVIEWED"
            if successes==len(cards) else "BLS_SECTOR_PUBLIC_RESEARCH_PARTIAL_HOLD",
        "mode":"OBSERVE",
        "source_series_count":len(cards),
        "source_series_observed_count":successes,
        "source_series_holds_count":len(cards)-successes,
        "source_research_cards":cards,
        "public_source_reference_series_ids":list(SERIES_CATALOG),
        "distinct_base_year_series_levels_must_not_be_aggregated":True,
        "sector_index_yoy_is_verified_supplier_cost_movement":False,
        "electrical_grid_index_is_solar_module_price":False,
        "original_local_supplier_invoices_authenticated":False,
        "sector_cost_shocks_approved_by_finance":False,
        "original_quant_forecast_registered":False,
        "business_revenue_or_profit_verified":False,
        "economic_twin_mutated":False,
        "background_worker_scheduled":False,
        "official_public_gets_in_this_request_max":len(cards),
        "database_writes":False,"outbound_sent":False,"execution_authority":"none",
    }


def probe_bls_sector_public_v1(*, as_of: datetime) -> dict[str, Any]:
    """Explicit four-source public research check; no owner approval or cron."""
    reports=[
        probe_bls_public_v1(as_of=as_of,series_id=series_id)
        for series_id in SERIES_CATALOG
    ]
    return review_bls_sector_reports(reports,as_of=as_of)
