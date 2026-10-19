"""Narrow NYC DCWP Home Improvement Contractor official business evidence pilot.

Only business licences with an identifiable corporate suffix are retained;
the source view also includes natural persons. All contact fields omitted.
Current licence and niche specialism still require independent verification.
No DB, outreach, resale, homeowner or customer handling.

A single request per local UTC day, <=20 rows, stable limited source page.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import re
from urllib.parse import urlencode, urlsplit
import urllib.request
from pathlib import Path

from empire_os.recc_supply_sweep import _atomic_private_json, _read_json

SCHEMA = "empire.us_nyc_home_improvement_company_pilot.v1"
HOST = "data.cityofnewyork.us"
ENDPOINT = "https://data.cityofnewyork.us/resource/acd4-wkax.json"
MAX_RESULTS = 20
CORP_SUFFIX = re.compile(
    r"(?:\bINC\.?|\bLLC|\bL\.L\.C\.|\bCORP\.?|"
    r"\bCORPORATION|\bLTD\.?|\bLIMITED|\bLLP|\bCO\.)$", re.I
)


def _url(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("timestamp_must_be_aware")
    return ENDPOINT + "?" + urlencode({
        "$select": "license_nbr,business_name,license_status,lic_expir_dd,address_city,address_state",
        "$where": "license_status = 'Active' AND lic_expir_dd > '"
            + now.astimezone(timezone.utc).strftime("%Y-%m-%dT00:00:00") + "'",
        "$order": "license_nbr ASC", "$limit": MAX_RESULTS,
    })


def _fetch(url: str, *, opener=None) -> list[dict]:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != HOST
            or parsed.path != "/resource/acd4-wkax.json"
            or parsed.username or parsed.password or parsed.port is not None):
        raise ValueError("unapproved_nyc_open_data_api")
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(
        url, headers={"User-Agent":"EmpireOS-SourceIntelligence/1.0 (contact@empire-ai.co.uk)",
                      "Accept":"application/json"}
    )
    with opener(req,timeout=18) as response:
        if response.status != 200:
            raise ValueError("nyc_open_data_http_hold")
        raw = response.read(220_001)
        if len(raw) > 220_000:
            raise ValueError("nyc_open_data_response_too_large")
        return json.loads(raw)


def review_nyc_company_licences(rows: list, *, now: datetime) -> list[dict]:
    if not isinstance(rows,list) or len(rows)>MAX_RESULTS:
        raise ValueError("unbounded_nyc_source_rows")
    unique = {}
    for r in rows:
        if not isinstance(r,dict):
            continue
        if str(r.get("license_status") or "").casefold() != "active":
            continue
        licence = str(r.get("license_nbr") or "")
        name = str(r.get("business_name") or "").strip()
        if not 6<=len(licence)<=28 or not 4<=len(name)<=180 or not CORP_SUFFIX.search(name):
            # Natural persons and ambiguous unincorporated business names
            # are held, not promoted to a B2B research list.
            continue
        try:
            exp = datetime.fromisoformat(str(r["lic_expir_dd"]).replace("Z","+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= now:
                continue
        except (ValueError, TypeError, KeyError):
            continue
        if str(r.get("address_state") or "").upper() not in ("NY", "NEW YORK"):
            continue
        if licence in unique:
            continue
        unique[licence] = {
            "source_id": "us_nyc_dcwp_home_improvement_companies",
            "license_number": licence, "business_name": name,
            "city": str(r.get("address_city") or "")[:80], "state":"NY",
            "country_code":"US",
            "licence_expires_observed": exp.date().isoformat(),
            "source_url":"https://data.cityofnewyork.us/Business/Active-Home-Improvement-Contractor-Licenses/acd4-wkax",
            "niche": "general_contractor",
            "specific_roofing_solar_hvac_trade_verified": False,
            "real_business_independently_verified": False,
            "canonical_empiredb_prospect_id": None,
            "outbound_authorized": False,
        }
    return list(unique.values())


def sweep_nyc_companies(root: Path, *, now: datetime | None=None, fetch=_fetch) -> dict:
    import fcntl
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("aware_now_required")
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    with (root/".nyc.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema_version": SCHEMA, "state":"ALREADY_RUNNING",
                    "canonical_empiredb_writes":False}
        quota = root/"quota.json"
        past = _read_json(quota,limit=5000)
        if past and past.get("schema_version")!=SCHEMA:
            raise ValueError("invalid_nyc_sweep_state")
        day = current.date().isoformat()
        if past.get("utc_day")==day:
            return {"schema_version":SCHEMA,"state":"DAILY_REQUEST_ALREADY_CONSUMED",
                    "canonical_empiredb_writes":False}
        _atomic_private_json(quota,{"schema_version":SCHEMA,"utc_day":day,"attempted":True})
        rows = fetch(_url(current))
        filtered = review_nyc_company_licences(rows,now=current)
        _atomic_private_json(root/"private_business_observations.json",{
            "schema_version":SCHEMA,"businesses":filtered,
        })
        report = {
            "schema_version":SCHEMA,"state":"COMPLETED",
            "source_id":"us_nyc_dcwp_home_improvement_companies",
            "observed_at":current.isoformat(),"source_rows_returned":len(rows),
            "corporate_business_licences_observed":len(filtered),
            "general_home_improvement_licence_only":True,
            "verified_industry_specialist_leads":0,
            "canonical_empiredb_additions":0,
            "commercial_exchange_inventory_additions":0,
            "outbound_authorized":False,
            "canonical_empiredb_writes":False,
            "execution_authority":"none",
        }
        _atomic_private_json(root/"latest.json",report)
        return report
