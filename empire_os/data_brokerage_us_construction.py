"""Bounded official U.S. construction signals for the EXISTING Data Brokerage owner.

Census BPS is state-level *residential authorisations*, not individual projects.
USAspending is historical federal *awards*, not open tenders, a list of customers,
or evidence of permission to contact an entity. No AIA directory harvesting.
The output is internal evidence for the existing market_signal_feed contract.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError

from empire_os.intelligence_data_products import get_data_product
from empire_os.source_intelligence import SOURCES

CENSUS_BASE = "https://www2.census.gov/econ/bps/State/"
AWARDS_URL = SOURCES["us_usaspending_awards"].url
CENSUS_SOURCE = "us_census_building_permits"
AWARDS_SOURCE = "us_usaspending_awards"
NAICS = ("541310", "236220")  # architectural services; commercial buildings
AWARD_FIELDS = (
    "Award ID", "Recipient Name", "Base Obligation Date", "Award Amount",
    "Awarding Agency", "Place of Performance State Code", "NAICS",
)
LIMIT = 10
MAX_CENSUS = 50_000
MAX_AWARDS = 90_000
STATE_ABBR = dict(zip(
    ("Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware "
     "District_of_Columbia Florida Georgia Hawaii Idaho Illinois Indiana Iowa "
     "Kansas Kentucky Louisiana Maine Maryland Massachusetts Michigan Minnesota "
     "Mississippi Missouri Montana Nebraska Nevada New_Hampshire New_Jersey "
     "New_Mexico New_York North_Carolina North_Dakota Ohio Oklahoma Oregon "
     "Pennsylvania Rhode_Island South_Carolina South_Dakota Tennessee Texas "
     "Utah Vermont Virginia Washington West_Virginia Wisconsin Wyoming").split(),
    ("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA "
     "MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX "
     "UT VT VA WA WV WI WY").split(),
))
STATE_ABBR = {k.replace("_", " "): v for k, v in STATE_ABBR.items()}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def census_url(month: str) -> str:
    if not re.fullmatch(r"20[0-9]{4}", month) or not 1 <= int(month[4:]) <= 12:
        raise ValueError("INVALID_CENSUS_REFERENCE_MONTH")
    return CENSUS_BASE + "st" + month[2:] + "c.txt"


def _read_official(url: str, *, body: bytes | None, cap: int, content_type: str) -> bytes:
    if url not in (AWARDS_URL,) and not re.fullmatch(
        r"https://www2\.census\.gov/econ/bps/State/st[0-9]{2}(0[1-9]|1[0-2])c\.txt", url
    ):
        raise ValueError("UNREGISTERED_OFFICIAL_URL")
    headers = {
        "Accept": "application/json" if body is not None else "text/plain",
        "User-Agent": "EmpireAI-Existing-Brokerage-Official-Research/1.0",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method="POST" if body is not None else "GET",
                      headers=headers)
    with build_opener(_NoRedirect).open(request, timeout=11) as response:
        if (response.status != 200 or response.geturl() != url or
                content_type not in response.headers.get("Content-Type", "").lower()):
            raise ValueError("OFFICIAL_SOURCE_RESPONSE_UNVERIFIED")
        raw = response.read(cap + 1)
    if len(raw) > cap:
        raise ValueError("OFFICIAL_SOURCE_TOO_LARGE")
    return raw


def official_awards_request(*, now: datetime) -> dict[str, Any]:
    if now.utcoffset() is None:
        raise ValueError("AWARE_CLOCK_REQUIRED")
    return {
        "filters": {
            "award_type_codes": ["A", "B", "C", "D"],
            "naics_codes": list(NAICS),
            "time_period": [{
                "start_date": (now.date() - timedelta(days=180)).isoformat(),
                "end_date": now.date().isoformat(),
            }],
        },
        "fields": list(AWARD_FIELDS),
        "sort": "Base Obligation Date", "order": "desc",
        "page": 1, "limit": LIMIT,
    }


def fetch_official_sources(*, now: datetime, month: str) -> tuple[str, Mapping[str, Any]]:
    """Two capped official reads. Caller controls cadence; no scheduler or writes."""
    census = _read_official(census_url(month), body=None, cap=MAX_CENSUS,
                            content_type="text/plain").decode("utf-8-sig")
    body = json.dumps(official_awards_request(now=now), separators=(",", ":")).encode()
    awards = json.loads(_read_official(AWARDS_URL, body=body, cap=MAX_AWARDS,
                                      content_type="application/json"))
    if not isinstance(awards, dict):
        raise ValueError("UNEXPECTED_AWARD_SOURCE_SHAPE")
    return census, awards



def fetch_latest_published_official_sources(
    *, now: datetime,
) -> tuple[str, str, Mapping[str, Any]]:
    """Use the latest *available* state-month file, not an assumed release date.

    State-level BPS is normally revised/published late in the next month.
    Try exactly two eligible published-month candidates, falling back only
    after a Census-file HTTP 404. All other failures fail closed; awards are
    fetched once, only after a Census file succeeds.
    """
    if now.utcoffset() is None:
        raise ValueError("AWARE_CLOCK_REQUIRED")
    candidate = (now.astimezone(timezone.utc) - timedelta(days=30)).strftime("%Y%m")
    preceding = (
        datetime.strptime(candidate + "01", "%Y%m%d").date() - timedelta(days=1)
    ).strftime("%Y%m")
    for month in (candidate, preceding):
        try:
            census, awards = fetch_official_sources(now=now, month=month)
            return month, census, awards
        except HTTPError as exc:
            if exc.code != 404 or exc.url != census_url(month):
                raise
    raise ValueError("RECENT_CENSUS_STATE_PUBLICATION_NOT_FOUND")

def parse_census(text: str, *, month: str) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) > 80 or len(rows) < 45 or len(rows[0]) < 20:
        raise ValueError("UNEXPECTED_BPS_FILE_SHAPE")
    if rows[0][:5] != ["Survey", "FIPS", "Region", "Division", "State"]:
        raise ValueError("BPS_HEADER_MISMATCH")
    if rows[1][:5] != ["Date", "State", "Code", "Code", "Name"]:
        raise ValueError("BPS_COLUMN_MISMATCH")
    unique: set[str] = set()
    states: list[dict[str, Any]] = []
    for row in rows[2:]:
        if not row or not row[0].strip():
            continue
        if len(row) < 17 or row[0].strip() != month:
            raise ValueError("BPS_REFERENCE_DATE_MISMATCH")
        # The same official file also contains US/region/division summary rows.
        # They are not states and must never be double-counted as extra regions.
        if row[1] == "US" or re.fullmatch(r"[RD][1-9]", row[1]):
            continue
        name = row[4].strip()
        abbr = STATE_ABBR.get(name)
        if not abbr or not re.fullmatch(r"[0-9]{2}", row[1]) or abbr in unique:
            raise ValueError("BPS_STATE_IDENTITY_MISMATCH")
        unique.add(abbr)
        try:
            units = [int(row[i].strip()) for i in (6, 9, 12, 15)]
        except (ValueError, IndexError) as exc:
            raise ValueError("BPS_UNIT_FIELD_INVALID") from exc
        if any(x < 0 or x > 1_000_000 for x in units):
            raise ValueError("BPS_UNIT_OUT_OF_RANGE")
        states.append({
            "state": abbr, "state_name": name,
            "new_private_residential_units_authorised": sum(units),
            "one_unit": units[0], "two_unit": units[1],
            "three_or_four_units": units[2], "five_plus_units": units[3],
        })
    if len(states) not in (50, 51):
        raise ValueError("BPS_INCOMPLETE_STATE_COVERAGE")
    return {
        "source_id": CENSUS_SOURCE, "source_url": census_url(month),
        "reference_month": month, "rows_verified": len(states),
        "national_total_not_claimed": True,
        "state_activity_ranked": sorted(
            states, key=lambda x: (-x["new_private_residential_units_authorised"], x["state"])
        )[:10],
        "state_totals_for_geographic_context_only": {
            s["state"]: s["new_private_residential_units_authorised"] for s in states
        },
        "data_semantics": "new_privately_owned_residential_units_authorised_not_starts",
        "state_values_are_estimates_or_reported": True,
        "raw_file_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def parse_awards(response: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    rows = response.get("results")
    if (response.get("limit") != LIMIT or not isinstance(rows, list)
            or len(rows) > LIMIT or not isinstance(response.get("page_metadata"), Mapping)):
        raise ValueError("AWARD_SAMPLE_SHAPE_INVALID")
    seen: set[str] = set()
    organisations = []
    rejected = 0
    for row in rows:
        if not isinstance(row, Mapping):
            rejected += 1
            continue
        award_id, recipient, agency = (
            row.get("Award ID"), row.get("Recipient Name"), row.get("Awarding Agency")
        )
        date_value = row.get("Base Obligation Date")
        naics = row.get("NAICS")
        state = row.get("Place of Performance State Code")
        if (not all(isinstance(x, str) and 2 <= len(x) <= 150
                    for x in (award_id, recipient, agency, date_value))
                or not isinstance(naics, Mapping) or naics.get("code") not in NAICS
                or not isinstance(state, str) or not re.fullmatch(r"[A-Z]{2}", state)):
            rejected += 1
            continue
        try:
            obligation_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            rejected += 1
            continue
        if not (now.date() - timedelta(days=180) <= obligation_date <= now.date()):
            rejected += 1
            continue
        identity = str(row.get("internal_id") or award_id)
        if identity in seen:
            rejected += 1
            continue
        seen.add(identity)
        organisations.append({
            "award_id": award_id,
            "award_recipient_name": recipient.strip(),
            "awarding_agency": agency.strip(),
            "award_record_date": obligation_date.isoformat(),
            "naics": naics["code"],
            "performance_state": state,
            "identity_evidence": "OFFICIAL_AWARD_RECIPIENT_NAME_NOT_LEGAL_ENTITY_VERIFIED",
            "buyer_intent": "UNKNOWN",
            "contact_permission": False,
            "open_tender": False,
        })
    return {
        "source_id": AWARDS_SOURCE, "source_url": AWARDS_URL,
        "source_rows_sampled": len(rows),
        "recipient_award_records_accepted": len(organisations),
        "records_rejected": rejected,
        "official_award_recipient_research": organisations,
        "sampling_bias": "FIRST_PAGE_ONLY_NOT_ALL_AWARDS",
        "evidence_class": "DATED_FEDERAL_AWARD_HISTORY_NOT_OPEN_PROCUREMENT",
        "source_response_sha256": _digest(response),
    }


def assess_construction_signals(
    *, now: datetime, month: str, census_text: str,
    awards_response: Mapping[str, Any],
) -> dict[str, Any]:
    """Join state-level *context* only. No firm-to-permit or customer inference."""
    if now.utcoffset() is None:
        raise ValueError("AWARE_CLOCK_REQUIRED")
    if CENSUS_SOURCE not in SOURCES or AWARDS_SOURCE not in SOURCES:
        raise ValueError("CANONICAL_SOURCE_REGISTRATION_REQUIRED")
    month_date = datetime.strptime(month + "01", "%Y%m%d").date()
    if month_date > now.date() or (now.date() - month_date).days > 90:
        raise ValueError("CENSUS_REFERENCE_TOO_OLD_OR_FUTURE")
    census = parse_census(census_text, month=month)
    awards = parse_awards(awards_response, now=now)
    geography = census["state_totals_for_geographic_context_only"]
    prospects = [
        {**item, "residential_permit_geographic_context_units":
         geography.get(item["performance_state"]),
         "entity_to_residential_permit_match_verified": False,
         "customer_buyer_verified": False,
         "pipeline_stage": "RESEARCH_ONLY"}
        for item in awards["official_award_recipient_research"]
    ]
    contract = get_data_product("market_signal_feed")
    if contract is None:
        raise ValueError("EXISTING_PRODUCT_CONTRACT_MISSING")
    return {
        "schema_version": "empire.data_brokerage.us_construction.v1",
        "mode": "EXISTING_BROKERAGE_INTERNAL_SOURCE_RESEARCH",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "contract_key": "market_signal_feed",
        "contract_name": contract.name,
        "source_ids": [CENSUS_SOURCE, AWARDS_SOURCE],
        "aia_role": "MARKET_RESEARCH_ONLY_NO_DIRECTORY_EXTRACTION",
        "census": census,
        "federal_awards": {k: v for k, v in awards.items()
                           if k != "official_award_recipient_research"},
        "research_candidates": prospects,
        "research_candidate_count": len(prospects),
        "genuine_buyer_enquiries_verified": 0,
        "external_organisation_identity_verified": 0,
        "direct_project_matches_verified": 0,
        "licensed_resale_rights_confirmed": False,
        "customer_delivery_enabled": False,
        "crm_writes": False, "outreach_sent": False,
        "source_data_resale_authorized": False, "execution_authority": "none",
    }


def summarise_for_existing_source_cycle(
    *, now: datetime, month: str, census_text: str, awards_response: Mapping[str, Any],
) -> dict[str, Any]:
    """Return only source statistics/provenance, never named organisation rows.

    The canonical 12-hour source-miner persists this projection; the manual
    operator may inspect award recipient names in-memory separately.
    """
    report = assess_construction_signals(
        now=now, month=month, census_text=census_text, awards_response=awards_response,
    )
    return {
        "status": "OFFICIAL_US_CONSTRUCTION_AGGREGATE_RESEARCH_ONLY",
        "product_contract": report["contract_key"],
        "source_ids": report["source_ids"],
        "census_reference_month": month,
        "census_state_count": report["census"]["rows_verified"],
        "top_state_residential_authorisation_units": [
            {
                "state": row["state"],
                "units": row["new_private_residential_units_authorised"],
            }
            for row in report["census"]["state_activity_ranked"][:5]
        ],
        "federal_award_rows_sampled": report["federal_awards"]["source_rows_sampled"],
        "federal_award_records_accepted_in_sample": report["research_candidate_count"],
        "source_sha256": {
            "census": report["census"]["raw_file_sha256"],
            "federal_awards": report["federal_awards"]["source_response_sha256"],
        },
        "named_award_recipients_persisted": False,
        "individual_projects_verified": 0,
        "buyer_enquiries_verified": 0,
        "source_licences_cleared_for_resale": False,
        "outreach_sent": False,
        "crm_writes": False,
        "execution_authority": "none",
    }
