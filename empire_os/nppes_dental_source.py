"""Strictly bounded CMS NPPES *organization* dental identity reviewer.

One narrow official registry API request per manual sweep, NPI-2 only.
No patients, individual dentists, addresses, officer names, contact emails,
licensure claims, provider prospect promotion, public resale or outbound.
CMS expressly asks bulk consumers to use DDS files, not repeated API searches.

A research receipt is not a qualified lead and may not enter Lead Exchange.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from empire_os.recc_supply_sweep import _atomic_private_json, _read_json

SCHEMA = "empire.cms_nppes_dental_org_sweep.v1"
ENDPOINT = "https://npiregistry.cms.hhs.gov/api/"
ALLOWED_STATES = frozenset({"TX", "IL", "FL", "CA", "NY", "GA"})
ALLOWED_CITIES = frozenset({
    ("Dallas", "TX"), ("Chicago", "IL"), ("Miami", "FL"),
    ("Los Angeles", "CA"), ("New York", "NY"), ("Atlanta", "GA"),
})
MAX_RESULTS = 8
MAX_RESPONSE_BYTES = 250_000
MAX_PRIVATE_ORGANIZATIONS = 48


def _url(city: str, state: str) -> str:
    if (city, state) not in ALLOWED_CITIES:
        raise ValueError("city_state_corridor_not_registered")
    return ENDPOINT + "?" + urlencode({
        "version": "2.1",
        "enumeration_type": "NPI-2",
        "taxonomy_description": "Dentist",
        "city": city,
        "state": state,
        "limit": MAX_RESULTS,
    })


def _fetch(url: str, *, opener=None) -> dict:
    opener = opener or urllib.request.urlopen
    loc = urlsplit(url)
    if (loc.scheme != "https" or loc.hostname != "npiregistry.cms.hhs.gov"
            or loc.port is not None or loc.username or loc.password
            or loc.path != "/api/"):
        raise ValueError("unapproved_nppes_api_url")
    req = urllib.request.Request(
        url, headers={
            "User-Agent": "EmpireOS-SourceIntelligence/1.0 (contact@empire-ai.co.uk)",
            "Accept": "application/json",
        }
    )
    with opener(req, timeout=18) as response:
        if response.status != 200:
            raise ValueError("nppes_http_status_hold")
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("nppes_response_oversize")
    return json.loads(body)


def review_nppes_org_records(payload: Mapping[str, Any], *, state: str,
                             city: str, observed_at: datetime) -> list[dict]:
    if not isinstance(payload, Mapping):
        raise TypeError("nppes_response_not_mapping")
    rows = payload.get("results")
    if (not isinstance(rows, list) or len(rows) > MAX_RESULTS
            or type(payload.get("result_count")) is not int
            or payload["result_count"] != len(rows)):
        raise ValueError("unbounded_nppes_result")
    accepted = []
    for result in rows:
        if not isinstance(result, Mapping):
            continue
        if result.get("enumeration_type") != "NPI-2":
            continue
        number = str(result.get("number") or "")
        if not re.fullmatch(r"\d{10}", number):
            continue
        basic = result.get("basic")
        if not isinstance(basic, Mapping):
            continue
        company = str(basic.get("organization_name") or "").strip()
        if not 4 <= len(company) <= 200:
            continue
        taxonomies = result.get("taxonomies") or []
        if (not isinstance(taxonomies, list) or not any(
                isinstance(t, Mapping) and str(t.get("code") or "").startswith("1223")
                for t in taxonomies)):
            continue
        # Entity is selected by organizational NPI, not provider individual.
        accepted.append({
            "source_id": "us_cms_nppes_dental_npi2",
            "organization_npi": number,
            "business_name": company,
            "niche": "dental",
            "country_code": "US",
            "state": state,
            "search_city": city,
            "source_url": "https://npiregistry.cms.hhs.gov/provider-view/" + number,
            "observed_at": observed_at.isoformat(),
            "legal_entity_licensed_or_verified": False,
            "has_confirmed_buyer_intent": False,
            "canonical_empiredb_prospect_id": None,
            "consumer_or_patient_record": False,
            "outbound_authorized": False,
        })
    return accepted


def sweep_nppes_dental(
    private_root: Path, *, city: str = "Dallas", state: str = "TX",
    now: datetime | None = None,
    fetch: Callable[[str], dict] = _fetch,
) -> dict[str, Any]:
    """One explicit, narrow human-approved query per geo per UTC day.

    API response is not a bulk ingestion licence; reserve request quota even
    if interrupted. Persist no personal fields even when API returns them.
    """
    url = _url(city, state)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("aware_now_required")
    root = Path(private_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    import fcntl
    with (root / ".nppes.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema_version": SCHEMA, "state": "ALREADY_RUNNING",
                    "canonical_empiredb_writes": False}
        state_path = root / "query_quota.json"
        ledger_path = root / "organizations.json"
        state_info = _read_json(state_path, limit=10000)
        ledger = _read_json(ledger_path, limit=100_000)
        if state_info and state_info.get("schema_version") != SCHEMA:
            raise ValueError("nppes_state_schema_invalid")
        if ledger and ledger.get("schema_version") != SCHEMA:
            raise ValueError("nppes_ledger_schema_invalid")
        previous = ledger.get("organizations", [])
        if (not isinstance(previous, list)
                or len(previous) > MAX_PRIVATE_ORGANIZATIONS):
            raise ValueError("nppes_private_ledger_invalid")
        day = current.date().isoformat()
        attempted = state_info.get("queries_today", [])
        if state_info.get("utc_day") != day:
            attempted = []
        if not isinstance(attempted, list) or len(attempted) > len(ALLOWED_CITIES):
            raise ValueError("nppes_daily_budget_invalid")
        geo = city + "," + state
        if geo in attempted:
            return {
                "schema_version": SCHEMA, "state": "QUERY_GEO_ALREADY_RUN_TODAY",
                "unique_private_organization_observations": len(previous),
                "outbound_authorized": False,
                "canonical_empiredb_writes": False,
            }
        if len(attempted) >= 2:
            return {
                "schema_version": SCHEMA, "state": "DAILY_QUERY_LIMIT_REACHED",
                "unique_private_organization_observations": len(previous),
                "outbound_authorized": False,
                "canonical_empiredb_writes": False,
            }
        # Durable request accounting is a stricter limit than CMS's published
        # hourly cap; never run this as a broad query crawler.
        _atomic_private_json(state_path, {
            "schema_version": SCHEMA, "utc_day": day,
            "queries_today": attempted + [geo],
        })
        payload = fetch(url)
        fresh = review_nppes_org_records(payload, state=state, city=city,
                                         observed_at=current)
        by_npi = {
            x["organization_npi"]: x for x in previous
            if isinstance(x, Mapping) and isinstance(x.get("organization_npi"), str)
        }
        if len(by_npi) != len(previous):
            raise ValueError("nppes_duplicate_ledger")
        before = len(by_npi)
        for item in fresh:
            by_npi[item["organization_npi"]] = item
        if len(by_npi) > MAX_PRIVATE_ORGANIZATIONS:
            raise ValueError("nppes_research_ledger_capacity_hold")
        _atomic_private_json(ledger_path, {
            "schema_version": SCHEMA,
            "organizations": sorted(
                by_npi.values(), key=lambda r: r["organization_npi"]
            ),
        })
        report = {
            "schema_version": SCHEMA,
            "state": "COMPLETED",
            "source_id": "us_cms_nppes_dental_npi2",
            "observed_at": current.isoformat(),
            "state_code": state,
            "search_city": city,
            "source_results_returned": len(payload["results"]),
            "organization_only_accepted": len(fresh),
            "new_unique_business_observations": len(by_npi) - before,
            "unique_private_organization_observations": len(by_npi),
            "official_registry_not_proof_of_licensure": True,
            "canonical_empiredb_additions": 0,
            "commercial_exchange_inventory_additions": 0,
            "outbound_authorized": False,
            "canonical_empiredb_writes": False,
            "execution_authority": "none",
        }
        _atomic_private_json(root / "latest.json", report)
        return report
