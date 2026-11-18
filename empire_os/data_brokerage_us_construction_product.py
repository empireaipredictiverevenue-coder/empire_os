"""Private US construction market brief on the original Market Signal Feed.

Bounded official-source analytical transformation. No contacts, individual
job-site claims, customer export, pricing, direct API entitlements, or outreach.
Use the existing 12-hour Data Brokerage owner to refresh its private preview.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError
import json
import os
import re
import tempfile

from empire_os.data_brokerage_us_construction import (
    CENSUS_BASE, AWARDS_URL, CENSUS_SOURCE, AWARDS_SOURCE, STATE_ABBR,
    MAX_CENSUS, census_url, _read_official, parse_census, parse_awards,
    fetch_latest_published_official_sources,
)
from empire_os.intelligence_data_products import get_data_product
from empire_os.lead_sources.nyc_dobnow import (
    DATASET_PAGE as NYC_DOBNOW_PAGE,
    FILINGS_ID as NYC_DOBNOW_FILINGS_ID,
    ISSUED_ID as NYC_DOBNOW_ISSUED_ID,
    JOB as NYC_DOBNOW_JOB,
    current_event_sample as current_nyc_project_events,
)
from empire_os.permit_property_source_join import (
    SCHEMA as NYC_PROPERTY_JOIN_SCHEMA,
    FOOTPRINT_ID as NYC_FOOTPRINT_ID,
    PLUTO_ID as NYC_PLUTO_ID,
    LAND_USE as NYC_LAND_USE,
    review_official_building_landuse,
)

SCHEMA = "empire.data_brokerage.us_construction_market_product.v1"
STATE_PATH = Path("runtime/data_brokerage/us_construction_market_product_latest.json")
MAX_PRIVATE_BYTES = 72_000
MAX_AGE = timedelta(hours=40)
EXPECTED_STATE_COUNT = 51
MAX_NYC_SAMPLE = 40
BOROUGHS = frozenset({"Brooklyn", "Queens", "Manhattan", "Bronx", "Staten Island"})
WORK_TYPE = re.compile(r"[A-Za-z0-9 /&+()._-]{1,60}")


def _sha(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _parsed_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def reference_months(latest: str) -> tuple[str, str]:
    """Last published month -> preceding month and same month last year."""
    if not re.fullmatch(r"20[0-9]{4}", latest) or not 1 <= int(latest[4:]) <= 12:
        raise ValueError("BAD_REFERENCE_MONTH")
    target = datetime.strptime(latest + "01", "%Y%m%d")
    before = (target - timedelta(days=1)).strftime("%Y%m")
    year_ago = f"{target.year-1:04d}{target.month:02d}"
    return before, year_ago


def _pct(now: int, prior: int) -> float | None:
    return round((now - prior) * 100 / prior, 1) if prior > 0 else None


def acquire_official_market_inputs(
    *, now: datetime,
) -> tuple[str, Mapping[str, str], Mapping[str, Any]]:
    """Four capped official reads: latest+prior+year ago Census; federal awards.

    Latest-publication discovery may add one 404 read. Any other failure holds
    the release. No broad site search or directory extraction.
    """
    if now.utcoffset() is None:
        raise ValueError("UTC_AWARE_CLOCK_REQUIRED")
    month, recent, award_response = fetch_latest_published_official_sources(now=now)
    previous, prior_year = reference_months(month)
    texts: dict[str, str] = {month: recent}
    for reference in (previous, prior_year):
        texts[reference] = _read_official(
            census_url(reference), body=None, cap=MAX_CENSUS,
            content_type="text/plain",
        ).decode("utf-8-sig")
    return month, texts, award_response



def build_nyc_project_evidence(
    source: Mapping[str, Any] | None, *, now: datetime,
) -> dict[str, Any]:
    """Project event receipts from the EXISTING bounded two-DOB-source reader.

    This is an issuance review, not customer matching. Names, addresses,
    phone numbers, emails and underlying property references never pass
    into the product snapshot or founder UI.
    """
    empty = {
        "status": "NOT_OBSERVED_YET",
        "scope": "NYC_FIRST_ISSUANCE_TWO_DOB_DATASETS",
        "citywide_coverage_claimed": False,
        "sample_may_be_incomplete": True,
        "source_issued_rows_sampled": 0,
        "distinct_crosschecked_jobs": 0,
        "project_records": [],
        "source_receipts": [],
        "buyer_or_owner_identified": False,
        "site_address_exported": False,
        "property_identity_cross_source_verified": False,
        "source_resale_rights_cleared": False,
        "outreach_authorized": False,
    }
    if source is None:
        return empty
    if not isinstance(source, Mapping) or now.utcoffset() is None:
        raise ValueError("NYC_PROJECT_INPUT_UNTRUSTED")
    if (source.get("status") == "NO_BOUNDED_INITIAL_PERMIT_ROWS"
            and source.get("mode") == "OBSERVE"
            and source.get("no_sales_authority") is True
            and source.get("events") == []
            and source.get("query_rows") == 0):
        return {**empty, "status": "OFFICIAL_NYC_SAMPLE_EMPTY"}
    if (source.get("status") != "OFFICIAL_BOUNDED_EVENT_CROSSCHECK"
            or source.get("mode") != "OBSERVE"
            or source.get("no_sales_authority") is not True
            or source.get("independent_site_or_buyer_verified") is not False
            or source.get("source_datasets")
            != [NYC_DOBNOW_FILINGS_ID, NYC_DOBNOW_ISSUED_ID]):
        raise ValueError("NYC_PROJECT_ORIGINAL_OWNER_PROOF_MISSING")
    observed = _parsed_date(source.get("observed_at_utc"))
    if (observed is None or observed > now.astimezone(timezone.utc)
            or now.astimezone(timezone.utc) - observed > timedelta(hours=24)):
        raise ValueError("NYC_PROJECT_SOURCE_OBSERVATION_STALE")
    rows = source.get("events")
    count = source.get("query_rows")
    hashes = source.get("source_response_sha256")
    if (not isinstance(rows, list) or len(rows) > MAX_NYC_SAMPLE
            or type(count) is not int or not 0 <= count <= MAX_NYC_SAMPLE
            or len(rows) > count
            or source.get("distinct_crosschecked_jobs") != len(rows)
            or source.get("sample_may_be_incomplete") is not (count == MAX_NYC_SAMPLE)
            or not isinstance(hashes, Mapping)
            or set(hashes) != {"permits", "filings"}
            or any(not isinstance(x, str) or
                   not re.fullmatch(r"[0-9a-f]{64}", x)
                   for x in hashes.values())):
        raise ValueError("NYC_PROJECT_SOURCE_SAMPLE_UNTRUSTED")
    by_job: dict[str, dict[str, Any]] = {}
    upstream_fields = {
        "job_filing_number", "filing_date", "first_permit_date",
        "issued_date", "filing_reason", "permit_status", "work_type",
        "work_types", "underlying_permit_row_count", "borough", "bin",
        "bbl", "solar_work_type", "general_construction_work_type",
        "official_event_crosscheck",
    }
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != upstream_fields:
            raise ValueError("NYC_PROJECT_ROW_UNTRUSTED")
        if (not isinstance(row.get("bin"), str)
                or not re.fullmatch(r"[0-9]{7}", row["bin"])
                or not isinstance(row.get("bbl"), str)
                or not re.fullmatch(r"[0-9]{10}", row["bbl"])
                or type(row.get("solar_work_type")) is not bool
                or type(row.get("general_construction_work_type")) is not bool):
            raise ValueError("NYC_PROJECT_PROPERTY_REFERENCE_NOT_CROSSCHECKED")
        job = row.get("job_filing_number")
        if not isinstance(job, str) or not NYC_DOBNOW_JOB.fullmatch(job):
            raise ValueError("NYC_PROJECT_JOB_INVALID")
        if job in by_job:
            raise ValueError("NYC_PROJECT_DUPLICATE_JOB")
        filed = row.get("filing_date")
        issued = row.get("issued_date")
        if (not isinstance(filed, str) or not isinstance(issued, str)
                or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", filed)
                or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", issued)):
            raise ValueError("NYC_PROJECT_DATE_INVALID")
        try:
            filed_day = datetime.strptime(filed, "%Y-%m-%d").date()
            issued_day = datetime.strptime(issued, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("NYC_PROJECT_SOURCE_DATE_INVALID") from exc
        if (not now.astimezone(timezone.utc).date() -
                timedelta(days=7) <= issued_day <= now.date()
                or filed_day > issued_day
                or row.get("first_permit_date") != issued
                or row.get("permit_status") != "Permit Issued"
                or row.get("filing_reason") != "Initial Permit"
                or row.get("official_event_crosscheck") is not True):
            raise ValueError("NYC_PROJECT_EVENT_UNVERIFIED")
        borough = row.get("borough")
        works = row.get("work_types")
        if (borough not in BOROUGHS or not isinstance(works, list)
                or not 1 <= len(works) <= MAX_NYC_SAMPLE
                or any(not isinstance(work, str) or WORK_TYPE.fullmatch(work) is None
                       for work in works)
                or type(row.get("underlying_permit_row_count")) is not int
                or not 1 <= row["underlying_permit_row_count"] <= MAX_NYC_SAMPLE):
            raise ValueError("NYC_PROJECT_SCOPE_UNTRUSTED")
        by_job[job] = {
            "project_ref": "nyc_dobnow_job:" + job,
            "city": "New York City", "state": "NY",
            "borough": borough, "original_filing_date": filed,
            "original_first_issuance_date": issued,
            "work_type_categories": sorted(set(works)),
            "source_evidence_url": NYC_DOBNOW_PAGE,
            "evidence_class": "TWO_OFFICIAL_NYC_DOB_DATASETS_CROSSCHECKED",
            "original_project_event_verified": True,
            "named_property_or_company_match_verified": False,
            "buyer_purchase_intent_verified": False,
            "commercial_reuse_rights_verified": False,
        }
    return {
        **empty,
        "status": "OFFICIAL_NYC_FIRST_ISSUANCE_PROJECT_SAMPLE_VERIFIED",
        "observed_at": observed.isoformat(),
        "source_issued_rows_sampled": count,
        "distinct_crosschecked_jobs": len(by_job),
        "project_records": sorted(
            by_job.values(),
            key=lambda d: (d["original_first_issuance_date"], d["project_ref"]),
            reverse=True,
        ),
        "source_receipts": [
            {
                "source_id": f"nyc_dobnow_{key}",
                "source_url": f"https://data.cityofnewyork.us/resource/{ident}.json",
                "sha256": hashes[key],
                "source_observed_at": observed.isoformat(),
            }
            for key, ident in (
                ("permits", NYC_DOBNOW_ISSUED_ID),
                ("filings", NYC_DOBNOW_FILINGS_ID),
            )
        ],
    }



REFERENCE_MATCH = frozenset({
    "TRI_AGENCY_BIN_AND_LOT_MATCH",
    "TRI_AGENCY_BIN_AND_BILLING_LOT_MATCH",
})
REFERENCE_STATES = REFERENCE_MATCH | frozenset({
    "DCP_LOT_ONLY_BIN_UNCONFIRMED",
    "OTI_BIN_ONLY_TAX_LOT_UNCONFIRMED",
    "PROPERTY_SOURCE_REFERENCE_UNMATCHED",
    "BUILDING_TAX_LOT_CONFLICT",
    "DCP_BOROUGH_CONFLICT",
    "AMBIGUOUS_SOURCE_IDENTITY",
})


def build_nyc_property_reference_context(
    source: Mapping[str, Any] | None,
    *, project_layer: Mapping[str, Any], now: datetime,
) -> dict[str, Any]:
    """Sanitise the ORIGINAL DOB/OTI/DCP join into private source evidence.

    Public job IDs and tax-lot land-use *classes* are permitted internally.
    Raw BIN, BBL, property addresses, owner identities and provider responses
    never leave the join's in-memory custody.
    """
    empty = {
        "status": "NOT_OBSERVED_YET",
        "reviewed_project_count": 0,
        "three_agency_reference_matches": 0,
        "unconfirmed_or_conflicting_references": 0,
        "source_receipts": [],
        "project_reference_reviews": [],
        "property_owner_or_operator_verified": False,
        "property_is_customer_buyer_verified": False,
        "source_redistribution_cleared": False,
        "commercial_outreach_authorized": False,
        "site_address_or_parcel_id_exported": False,
        "industrial_business_operation_inferred": False,
    }
    if source is None:
        return empty
    if (not isinstance(source, Mapping) or now.utcoffset() is None
            or source.get("schema") != NYC_PROPERTY_JOIN_SCHEMA
            or source.get("mode") != "OBSERVE"
            or source.get("agency_levels") != ["DOB", "OTI", "DCP"]
            or source.get("source_datasets") != {
                "dob_now_filings": NYC_DOBNOW_FILINGS_ID,
                "dob_now_initial_permits": NYC_DOBNOW_ISSUED_ID,
                "oti_building_footprints": NYC_FOOTPRINT_ID,
                "dcp_pluto": NYC_PLUTO_ID,
            }
            or source.get("rights_review_required_for_customer_distribution") is not True
            or any(source.get(field) is not False for field in (
                "external_outreach_sent",
                "data_warehouse_or_empiredb_mutated",
                "paid_provider_used",
            ))
            or source.get("execution_authority") != "none"):
        raise ValueError("ORIGINAL_THREE_AGENCY_REVIEW_UNTRUSTED")
    observed = _parsed_date(source.get("reviewed_at_utc"))
    if (observed is None or observed > now.astimezone(timezone.utc)
            or now.astimezone(timezone.utc) - observed > timedelta(hours=24)):
        raise ValueError("PROPERTY_SOURCE_REVIEW_TIME_INVALID")
    permits = project_layer.get("project_records") or []
    approved = {
        x["project_ref"]: x for x in permits if isinstance(x, Mapping)
    }
    diagnostics = source.get("diagnostics")
    if (not isinstance(diagnostics, list) or not approved
            or len(diagnostics) != len(approved)
            or source.get("permit_event_count") != len(diagnostics)):
        raise ValueError("THREE_AGENCY_SAMPLE_EVENT_COUNT_MISMATCH")
    receipts = source.get("source_selected_response_receipts")
    if not isinstance(receipts, list) or len(receipts) != 2:
        raise ValueError("THREE_AGENCY_MISSING_SOURCE_RECEIPTS")
    by_id = {}
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            raise ValueError("THREE_AGENCY_SOURCE_RECEIPT_INVALID")
        ident = receipt.get("dataset_id")
        digest = receipt.get("selected_response_sha256")
        if (ident not in (NYC_FOOTPRINT_ID, NYC_PLUTO_ID)
                or ident in by_id
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("THREE_AGENCY_SOURCE_DIGEST_UNVERIFIED")
        by_id[ident] = digest
    if set(by_id) != {NYC_FOOTPRINT_ID, NYC_PLUTO_ID}:
        raise ValueError("THREE_AGENCY_SOURCE_INCOMPLETE")

    rows = []
    seen = set()
    categories = frozenset(NYC_LAND_USE.values()) | {"UNKNOWN"}
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, Mapping):
            raise ValueError("PROPERTY_DIAGNOSTIC_ROW_INVALID")
        job = diagnostic.get("permit_job_filing_ref")
        ref = "nyc_dobnow_job:" + str(job)
        state = diagnostic.get("building_tax_lot_evidence_state")
        category = diagnostic.get("dcp_land_use_category")
        cls = diagnostic.get("dcp_building_class")
        if (ref not in approved or ref in seen
                or state not in REFERENCE_STATES
                or category not in categories
                or (cls is not None and (
                    not isinstance(cls, str)
                    or not re.fullmatch(r"[A-Z0-9]{1,3}", cls)
                ))
                or diagnostic.get("permit_original_issued_date")
                    != approved[ref]["original_first_issuance_date"]
                or any(diagnostic.get(key) is not False for key in (
                    "warehouse_operation_verified", "building_owner_identity_verified",
                    "verified_business_buyer", "property_transaction_verified",
                    "property_damage_verified", "commercial_contact_authorized",
                ))):
            raise ValueError("PROPERTY_DIAGNOSTIC_CLAIMS_UNTRUSTED")
        seen.add(ref)
        rows.append({
            "project_ref": ref,
            "property_reference_evidence_state": state,
            "independent_reference_chain_verified": state in REFERENCE_MATCH,
            "tax_lot_land_use_category": category,
            "tax_lot_building_class": cls,
            "physical_building_use_or_operator_verified": False,
            "named_company_buyer_verified": False,
            "commercial_resale_approved": False,
        })
    if seen != set(approved):
        raise ValueError("PROPERTY_REVIEW_MISSING_PERMIT_REFERENCE")
    matched = sum(x["independent_reference_chain_verified"] for x in rows)
    actual_counts = dict(sorted(
        Counter(x["property_reference_evidence_state"] for x in rows).items()
    ))
    if source.get("event_level_join_status_counts") != actual_counts:
        raise ValueError("PROPERTY_REVIEW_SOURCE_STATE_COUNTS_MISMATCH")
    return {
        **empty,
        "status": "THREE_AGENCY_PROPERTY_REFERENCE_REVIEWED_INTERNAL",
        "reviewed_at": observed.isoformat(),
        "reviewed_project_count": len(rows),
        "three_agency_reference_matches": matched,
        "unconfirmed_or_conflicting_references": len(rows) - matched,
        "property_evidence_status_counts": actual_counts,
        "project_reference_reviews": sorted(rows, key=lambda x: x["project_ref"]),
        "source_receipts": [
            {
                "source_id": f"nyc_{ident}",
                "source_url": f"https://data.cityofnewyork.us/resource/{ident}.json",
                "sha256": by_id[ident],
            }
            for ident in (NYC_FOOTPRINT_ID, NYC_PLUTO_ID)
        ],
    }


def build_private_market_product(
    *, now: datetime, latest: str, census_months: Mapping[str, str],
    awards_response: Mapping[str, Any],
    nyc_project_sample: Mapping[str, Any] | None = None,
    property_reference_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if now.utcoffset() is None:
        raise ValueError("UTC_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    prior, year_ago = reference_months(latest)
    if set(census_months) != {latest, prior, year_ago}:
        raise ValueError("THREE_OFFICIAL_MONTHS_REQUIRED")
    observed = datetime.strptime(latest + "01", "%Y%m%d").replace(tzinfo=timezone.utc)
    if not timedelta(0) <= now - observed <= timedelta(days=115):
        raise ValueError("CURRENT_CENSUS_PUBLICATION_REQUIRED")
    parsed = {month: parse_census(text, month=month) for month, text in census_months.items()}
    if any(p["rows_verified"] != EXPECTED_STATE_COUNT for p in parsed.values()):
        raise ValueError("COMPLETE_STATE_COVERAGE_REQUIRED")
    states = [state for state in STATE_ABBR.values()]
    if len(set(states)) != EXPECTED_STATE_COUNT:
        raise ValueError("CANONICAL_STATES_INVALID")
    current = parsed[latest]["state_totals_for_geographic_context_only"]
    previous = parsed[prior]["state_totals_for_geographic_context_only"]
    earlier = parsed[year_ago]["state_totals_for_geographic_context_only"]
    if set(current) != set(previous) or set(current) != set(earlier):
        raise ValueError("CENSUS_STATE_POPULATION_CHANGED")

    territories = []
    for state in sorted(current):
        units = current[state]
        last_month = previous[state]
        last_year = earlier[state]
        yoy = _pct(units, last_year)
        mom = _pct(units, last_month)
        territories.append({
            "state": state, "residential_units_authorised": units,
            "prior_month_units": last_month, "same_month_prior_year_units": last_year,
            "year_over_year_pct": yoy, "month_over_month_pct": mom,
            "year_over_year_delta_units": units - last_year,
            "observation_class": "STATE_RESIDENTIAL_HOUSING_AUTHORISATIONS",
            "individual_projects_verified": 0,
            "buyer_intent_verified": False,
        })
    territories.sort(key=lambda x: (-x["residential_units_authorised"], x["state"]))
    total = sum(x["residential_units_authorised"] for x in territories)
    yearly = sum(x["same_month_prior_year_units"] for x in territories)
    monthly = sum(x["prior_month_units"] for x in territories)
    if total <= 0:
        raise ValueError("EMPTY_CENSUS_MARKET")
    for index, territory in enumerate(territories, 1):
        territory["rank_by_authorised_units"] = index
        territory["share_of_covered_state_units_pct"] = round(
            territory["residential_units_authorised"] * 100 / total, 2
        )

    award = parse_awards(awards_response, now=now)
    naics = Counter()
    agency = Counter()
    state_awards = Counter()
    dates: list[str] = []
    for row in award["official_award_recipient_research"]:
        naics[row["naics"]] += 1
        agency[row["awarding_agency"]] += 1
        state_awards[row["performance_state"]] += 1
        dates.append(row["award_record_date"])
    if award["source_rows_sampled"] != len(awards_response.get("results", [])):
        raise ValueError("AWARD_SAMPLE_MISMATCH")
    project_layer = build_nyc_project_evidence(
        nyc_project_sample, now=now,
    )
    property_layer = build_nyc_property_reference_context(
        property_reference_review, project_layer=project_layer, now=now,
    )
    contract = get_data_product("market_signal_feed")
    if not contract:
        raise ValueError("CANONICAL_PRODUCT_MISSING")
    return {
        "schema_version": SCHEMA,
        "product_contract": contract.key,
        "product_name": "US Construction Market Intelligence",
        "product_scope": "Original market analysis using public Census state statistics and historical federal award samples",
        "mode": "FOUNDER_PRIVATE_REVIEW",
        "status": "SOURCE_VERIFIED_INTERNAL_PREVIEW",
        "generated_at": now.isoformat(),
        "source_reference_month": latest,
        "comparison_month": prior,
        "comparison_previous_year_month": year_ago,
        "market_segments": [
            "RESIDENTIAL_AUTHORISATIONS",
            "HISTORICAL_FEDERAL_AWARDS",
            "NYC_TWO_DOB_DATASET_FIRST_ISSUANCE_EVIDENCE",
        ],
        "project_event_layer_contract": "permit_intelligence_feed",
        "verified_local_project_evidence": project_layer,
        "independent_property_reference_review": property_layer,
        "geography": "United States: 50 states and District of Columbia",
        "geographic_unit": "state",
        "territory_count": len(territories),
        "territories": territories,
        "summary": {
            "total_state_residential_units_authorised": total,
            "change_from_same_month_prior_year_pct": _pct(total, yearly),
            "change_from_previous_month_pct": _pct(total, monthly),
            "states_with_yoy_increase": sum(
                x["year_over_year_delta_units"] > 0 for x in territories
            ),
            "states_with_yoy_decrease": sum(
                x["year_over_year_delta_units"] < 0 for x in territories
            ),
            "stats_are_unadjusted_subject_to_revision": True,
            "covered_state_totals_not_seasonally_adjusted_national_estimate": True,
        },
        "historical_federal_award_sample": {
            "status": "FIRST_PAGE_HISTORICAL_AWARD_RESEARCH_ONLY",
            "records_in_bounded_sample": award["source_rows_sampled"],
            "records_with_valid_obligation_date": award["recipient_award_records_accepted"],
            "held_records": award["records_rejected"],
            "by_naics": dict(sorted(naics.items())),
            "by_agency": dict(sorted(agency.items())),
            "by_state": dict(sorted(state_awards.items())),
            "latest_obligation_date_in_sample": max(dates) if dates else None,
            "buyer_contracts_or_open_bids_discovered": 0,
            "award_recipient_names_in_product": False,
            "national_market_coverage_claimed": False,
        },
        "source_receipts": [
            {
                "source_id": CENSUS_SOURCE, "source_url": census_url(month),
                "source_period": month, "sha256": parsed[month]["raw_file_sha256"],
                "record_type": "MONTHLY_STATE_RESIDENTIAL_AUTHORISATIONS",
            }
            for month in (latest, prior, year_ago)
        ] + [{
            "source_id": AWARDS_SOURCE, "source_url": AWARDS_URL,
            "source_period": "UP_TO_180_DAY_AWARD_HISTORY_FIRST_PAGE",
            "sha256": award["source_response_sha256"],
            "record_type": "HISTORICAL_FEDERAL_AWARD_RECORDS",
        }],
        "buyer_personas_to_validate": [
            "construction_product_manufacturers",
            "commercial_construction_sales_research_teams",
            "territory_planning_consultancies",
        ],
        "verified_customer_problem_statements": 0,
        "verified_paying_customers": 0,
        "verified_personal_contacts": 0,
        "project_address_matches": 0,
        "predictive_forecasts_or_estimated_buying_intent": False,
        "pricing_approved": False,
        "customer_delivery_enabled": False,
        "source_rights_review_passed_for_external_distribution": False,
        "licenced_redistribution_of_source_data": False,
        "new_scheduler_created": False,
        "outreach_sent": False,
        "crm_writes": False,
        "api_entitlements_issued": False,
        "recognized_revenue": False,
        "execution_authority": "none",
    }



def build_product_from_existing_official_sample(
    *, now: datetime, latest: str, latest_census_text: str,
    awards_response: Mapping[str, Any],
    include_nyc_projects: bool = False,
    include_property_crosscheck: bool = False,
) -> dict[str, Any]:
    """Reuse the same federal data and the existing DOB/OTI/DCP readers."""
    previous, last_year = reference_months(latest)
    references = {latest: latest_census_text}
    for month in (previous, last_year):
        references[month] = _read_official(
            census_url(month), body=None, cap=MAX_CENSUS,
            content_type="text/plain",
        ).decode("utf-8-sig")
    if include_property_crosscheck and not include_nyc_projects:
        raise ValueError("PROPERTY_REFERENCE_REQUIRES_DOB_EVENT_SOURCE")
    project_sample = None
    property_sample = None
    if include_nyc_projects:
        try:
            project_sample = current_nyc_project_events(now=now)
        except (OSError, TimeoutError, ValueError):
            # Fail the project layer closed without discarding independently
            # verified Census and federal market intelligence.
            project_sample = None
        if (include_property_crosscheck and project_sample is not None
                and project_sample.get("status")
                == "OFFICIAL_BOUNDED_EVENT_CROSSCHECK"
                and project_sample.get("events")):
            try:
                property_sample = review_official_building_landuse(
                    project_sample["events"], now=now,
                )
            except (OSError, TimeoutError, ValueError):
                property_sample = None
    return build_private_market_product(
        now=now, latest=latest, census_months=references,
        awards_response=awards_response,
        nyc_project_sample=project_sample,
        property_reference_review=property_sample,
    )



def _validate_nyc_project_layer(layer: Any, *, now: datetime) -> bool:
    if not isinstance(layer, Mapping):
        return False
    if (layer.get("scope") != "NYC_FIRST_ISSUANCE_TWO_DOB_DATASETS"
            or layer.get("citywide_coverage_claimed") is not False
            or layer.get("sample_may_be_incomplete") is not True
            or any(layer.get(key) is not False for key in (
                "buyer_or_owner_identified", "site_address_exported",
                "property_identity_cross_source_verified",
                "source_resale_rights_cleared", "outreach_authorized",
            ))):
        return False
    records = layer.get("project_records")
    receipts = layer.get("source_receipts")
    count = layer.get("source_issued_rows_sampled")
    matched = layer.get("distinct_crosschecked_jobs")
    if (not isinstance(records, list) or not isinstance(receipts, list)
            or type(count) is not int or type(matched) is not int
            or not 0 <= matched == len(records) <= count <= MAX_NYC_SAMPLE):
        return False
    if layer.get("status") in ("NOT_OBSERVED_YET", "OFFICIAL_NYC_SAMPLE_EMPTY"):
        return count == matched == 0 and records == [] and receipts == []
    if layer.get("status") != "OFFICIAL_NYC_FIRST_ISSUANCE_PROJECT_SAMPLE_VERIFIED":
        return False
    observed = _parsed_date(layer.get("observed_at"))
    if (observed is None or observed > now.astimezone(timezone.utc)
            or now.astimezone(timezone.utc) - observed > MAX_AGE):
        return False
    if (len(receipts) != 2 or
            [(x.get("source_id"), x.get("source_url")) for x in receipts
             if isinstance(x, Mapping)] != [
                ("nyc_dobnow_permits",
                 f"https://data.cityofnewyork.us/resource/{NYC_DOBNOW_ISSUED_ID}.json"),
                ("nyc_dobnow_filings",
                 f"https://data.cityofnewyork.us/resource/{NYC_DOBNOW_FILINGS_ID}.json"),
            ]
            or any(not re.fullmatch(
                r"[0-9a-f]{64}", str(x.get("sha256"))
            ) or x.get("source_observed_at") != layer["observed_at"]
                for x in receipts)):
        return False
    accepted_fields = frozenset((
        "project_ref", "city", "state", "borough",
        "original_filing_date", "original_first_issuance_date",
        "work_type_categories", "source_evidence_url", "evidence_class",
        "original_project_event_verified",
        "named_property_or_company_match_verified",
        "buyer_purchase_intent_verified", "commercial_reuse_rights_verified",
    ))
    seen = set()
    for row in records:
        if not isinstance(row, Mapping) or set(row) != accepted_fields:
            return False
        ref = row.get("project_ref")
        if (not isinstance(ref, str) or not ref.startswith("nyc_dobnow_job:")
                or not NYC_DOBNOW_JOB.fullmatch(ref[len("nyc_dobnow_job:"):])
                or ref in seen
                or row.get("city") != "New York City" or row.get("state") != "NY"
                or row.get("borough") not in BOROUGHS
                or row.get("source_evidence_url") != NYC_DOBNOW_PAGE
                or row.get("evidence_class") != "TWO_OFFICIAL_NYC_DOB_DATASETS_CROSSCHECKED"
                or row.get("original_project_event_verified") is not True
                or any(row.get(k) is not False for k in (
                    "named_property_or_company_match_verified",
                    "buyer_purchase_intent_verified", "commercial_reuse_rights_verified",
                ))):
            return False
        try:
            filing = datetime.strptime(row["original_filing_date"], "%Y-%m-%d").date()
            issue = datetime.strptime(row["original_first_issuance_date"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            return False
        if not filing <= issue <= now.date() or issue < observed.date() - timedelta(days=7):
            return False
        work = row.get("work_type_categories")
        if (not isinstance(work, list) or not 1 <= len(work) <= MAX_NYC_SAMPLE
                or any(not isinstance(w, str) or not WORK_TYPE.fullmatch(w)
                       for w in work)):
            return False
        seen.add(ref)
    return True



def _validate_nyc_property_layer(
    layer: Any, *, project_layer: Mapping[str, Any], now: datetime,
) -> bool:
    if not isinstance(layer, Mapping):
        return False
    if any(layer.get(key) is not False for key in (
        "property_owner_or_operator_verified",
        "property_is_customer_buyer_verified",
        "source_redistribution_cleared",
        "commercial_outreach_authorized",
        "site_address_or_parcel_id_exported",
        "industrial_business_operation_inferred",
    )):
        return False
    rows = layer.get("project_reference_reviews")
    receipts = layer.get("source_receipts")
    count = layer.get("reviewed_project_count")
    matches = layer.get("three_agency_reference_matches")
    unresolved = layer.get("unconfirmed_or_conflicting_references")
    if (not isinstance(rows, list) or not isinstance(receipts, list)
            or type(count) is not int or type(matches) is not int
            or type(unresolved) is not int
            or count < 0 or matches < 0 or unresolved < 0
            or matches + unresolved != count or len(rows) != count):
        return False
    if layer.get("status") == "NOT_OBSERVED_YET":
        return count == matches == unresolved == 0 and rows == [] and receipts == []
    if layer.get("status") != "THREE_AGENCY_PROPERTY_REFERENCE_REVIEWED_INTERNAL":
        return False
    stamp = _parsed_date(layer.get("reviewed_at"))
    if (stamp is None or stamp > now.astimezone(timezone.utc)
            or now.astimezone(timezone.utc) - stamp > MAX_AGE):
        return False
    original_refs = {
        x["project_ref"] for x in project_layer.get("project_records", [])
        if isinstance(x, Mapping)
    }
    if (count == 0 or original_refs != {
        row.get("project_ref") for row in rows if isinstance(row, Mapping)
    } or len(original_refs) != len(rows)):
        return False
    expected = frozenset((
        "project_ref", "property_reference_evidence_state",
        "independent_reference_chain_verified",
        "tax_lot_land_use_category", "tax_lot_building_class",
        "physical_building_use_or_operator_verified",
        "named_company_buyer_verified", "commercial_resale_approved",
    ))
    states = Counter()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != expected:
            return False
        state = row.get("property_reference_evidence_state")
        cls = row.get("tax_lot_building_class")
        if (state not in REFERENCE_STATES
                or row.get("independent_reference_chain_verified")
                    is not (state in REFERENCE_MATCH)
                or row.get("tax_lot_land_use_category")
                    not in set(NYC_LAND_USE.values()) | {"UNKNOWN"}
                or (cls is not None and (
                    not isinstance(cls, str)
                    or not re.fullmatch(r"[A-Z0-9]{1,3}", cls)
                ))
                or any(row.get(k) is not False for k in (
                    "physical_building_use_or_operator_verified",
                    "named_company_buyer_verified", "commercial_resale_approved",
                ))):
            return False
        states[state] += 1
    if (dict(sorted(states.items())) != layer.get("property_evidence_status_counts")
            or matches != sum(states[s] for s in REFERENCE_MATCH)):
        return False
    if (len(receipts) != 2
            or any(not isinstance(x, Mapping) for x in receipts)):
        return False
    for receipt, dataset in zip(
        receipts, (NYC_FOOTPRINT_ID, NYC_PLUTO_ID),
    ):
        if (set(receipt) != {"source_id", "source_url", "sha256"}
                or receipt.get("source_id") != "nyc_" + dataset
                or receipt.get("source_url")
                   != f"https://data.cityofnewyork.us/resource/{dataset}.json"
                or not re.fullmatch(
                    r"[0-9a-f]{64}", str(receipt.get("sha256"))
                )):
            return False
    return True


def validate_private_market_product(
    payload: Any, *, now: datetime, enforce_freshness: bool = True,
) -> bool:
    if not isinstance(payload, Mapping) or now.utcoffset() is None:
        return False
    if (payload.get("schema_version") != SCHEMA
            or payload.get("product_contract") != "market_signal_feed"
            or payload.get("mode") != "FOUNDER_PRIVATE_REVIEW"
            or payload.get("status") != "SOURCE_VERIFIED_INTERNAL_PREVIEW"
            or payload.get("territory_count") != EXPECTED_STATE_COUNT
            or payload.get("verified_customer_problem_statements") != 0
            or payload.get("verified_paying_customers") != 0
            or payload.get("project_address_matches") != 0
            or payload.get("execution_authority") != "none"):
        return False
    for gate in (
        "customer_delivery_enabled", "pricing_approved",
        "source_rights_review_passed_for_external_distribution",
        "licenced_redistribution_of_source_data", "outreach_sent",
        "crm_writes", "api_entitlements_issued", "recognized_revenue",
    ):
        if payload.get(gate) is not False:
            return False
    stamp = _parsed_date(payload.get("generated_at"))
    if stamp is None or stamp > now.astimezone(timezone.utc):
        return False
    if enforce_freshness and now.astimezone(timezone.utc) - stamp > MAX_AGE:
        return False
    months = [payload.get("source_reference_month"), payload.get("comparison_month"),
              payload.get("comparison_previous_year_month")]
    if any(not isinstance(m, str) or not re.fullmatch(r"20[0-9]{4}", m)
           for m in months):
        return False
    try:
        if list(reference_months(months[0])) != months[1:]:
            return False
    except ValueError:
        return False
    rows = payload.get("territories")
    if not isinstance(rows, list) or len(rows) != EXPECTED_STATE_COUNT:
        return False
    states = [x.get("state") for x in rows if isinstance(x, Mapping)]
    if len(states) != EXPECTED_STATE_COUNT or set(states) != set(STATE_ABBR.values()):
        return False
    if any(
        type(x.get("residential_units_authorised")) is not int
        or not 0 <= x["residential_units_authorised"] <= 1_000_000
        or x.get("buyer_intent_verified") is not False
        or x.get("individual_projects_verified") != 0
        for x in rows
    ):
        return False
    if (payload.get("project_event_layer_contract") != "permit_intelligence_feed"
            or not _validate_nyc_project_layer(
                payload.get("verified_local_project_evidence"), now=now,
            )):
        return False
    if not _validate_nyc_property_layer(
        payload.get("independent_property_reference_review"),
        project_layer=payload["verified_local_project_evidence"], now=now,
    ):
        return False
    receipts = payload.get("source_receipts")
    if (not isinstance(receipts, list) or len(receipts) != 4
            or any(not isinstance(r, Mapping) or not re.fullmatch(
                r"[0-9a-f]{64}", str(r.get("sha256"))) for r in receipts)):
        return False
    award = payload.get("historical_federal_award_sample")
    if (not isinstance(award, Mapping)
            or type(award.get("records_in_bounded_sample")) is not int
            or not 0 <= award["records_in_bounded_sample"] <= 10
            or award.get("award_recipient_names_in_product") is not False
            or award.get("national_market_coverage_claimed") is not False):
        return False
    summary = payload.get("summary")
    if not isinstance(summary, Mapping) or summary.get(
        "total_state_residential_units_authorised"
    ) != sum(x["residential_units_authorised"] for x in rows):
        return False
    return True


def persist_private_market_product(root: Path, payload: Mapping[str, Any], *,
                                   now: datetime,
                                   allow_noncanonical_test: bool = False) -> Path:
    if not validate_private_market_product(payload, now=now):
        raise ValueError("UNTRUSTED_OR_STALE_MARKET_PRODUCT")
    if root.resolve() != Path("/srv/empire_os") and not allow_noncanonical_test:
        raise ValueError("CANONICAL_BROKERAGE_OWNER_REQUIRED")
    path = root / STATE_PATH
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("SYMLINK_PRODUCT_PATH_REFUSED")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    original = dict(payload)
    original["local_integrity_sha256"] = _sha(payload)
    contents = (json.dumps(original, sort_keys=True, indent=2, allow_nan=False)
                + "\n").encode()
    if len(contents) > MAX_PRIVATE_BYTES:
        raise ValueError("PRIVATE_PRODUCT_TOO_LARGE")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".construction_product.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(contents)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def load_private_market_product(
    root: Path, *, now: datetime,
) -> dict[str, Any] | None:
    path = root / STATE_PATH
    try:
        if (path.is_symlink() or not path.is_file()
                or not 0 < path.stat().st_size <= MAX_PRIVATE_BYTES
                or path.stat().st_mode & 0o077):
            return None
        parsed = json.loads(path.read_text("utf-8"))
        digest = parsed.pop("local_integrity_sha256", None)
        if (not isinstance(digest, str) or digest != _sha(parsed)
                or not validate_private_market_product(parsed, now=now)):
            return None
        return parsed
    except (OSError, TypeError, KeyError, ValueError, UnicodeError):
        return None
