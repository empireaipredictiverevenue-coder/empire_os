"""Source-specific, evidence-bound original Data Brokerage intelligence.

Uses the existing procurement source owner, existing Companies House evidence
and NESO official public API, then binds only original derived intelligence
to the ORIGINAL Intelligence Fabric product contracts. Internal research only.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.parse import urlsplit
import json
import re

from empire_os.intelligence_data_products import get_data_product
from empire_os.data_brokerage_buyer_fit import (qualify_existing_agency_report, validate_agency_fit_receipt, verify_public_research_demand, validate_public_research_demand)
from empire_os.data_brokerage_targeted_buyer_scope import assess_targeted_buyer_demand, validate_targeted_buyer_demand
from empire_os.data_brokerage_live_buyer_fit import validate_first_party_fit_summary

SCHEMA = "empire.data_brokerage.source_product_mining.v1"
NESO_REGIONAL = "https://api.carbonintensity.org.uk/regional"
NESO_NATIONAL = "https://api.carbonintensity.org.uk/intensity"
OGL_NOTICE = "https://www.find-tender.service.gov.uk/Notice/"
PROCUREMENT_OWNER = Path("runtime/acquisition_research/official_procurement_requirements_latest.json")
REGISTRY_OWNER = Path("runtime/buyer_acquisition/official_company_registry_evidence_latest.json")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_NOTICE = re.compile(r"\d{6}-20\d{2}\Z")
_OCID = re.compile(r"ocds-[a-z0-9]{6}-[a-z0-9]+\Z")
_FUELS = frozenset({"biomass", "coal", "imports", "gas", "nuclear", "other", "hydro", "solar", "wind"})
REGION_ID_MIN = 1
REGION_ID_MAX = 14
REQUIRED_REGION_COUNT = 14
MAX_SOURCE_BYTES = 180_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _strict_json(root: Path, path: Path, *, max_bytes: int = MAX_SOURCE_BYTES) -> tuple[Mapping[str, Any], str] | None:
    target = root / path
    try:
        if (target.is_symlink() or not target.is_file()
                or not 0 < target.stat().st_size <= max_bytes):
            return None
        raw = target.read_bytes()
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj, sha256(raw).hexdigest()
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    return None


def _contract(key: str) -> dict[str, Any]:
    contract = get_data_product(key)
    if contract is None:
        raise ValueError("ORIGINAL_EMPIRE_DATA_PRODUCT_NOT_FOUND")
    return {
        "key": key, "name": contract.name, "contract_required_evidence": list(contract.required_evidence),
        "delivery_modes_are_capabilities_not_entitlements": list(contract.delivery_modes),
        "commercial_model": contract.commercial_model,
        "customer_claim_release_ready": False,
        "customer_access_provisioned": False,
        "customer_distribution_authorized": False,
    }


def _internal_item(
    *, product: str, source: str, source_uri: str,
    original_date: str | None, source_digest: str | None,
    statement: str, analysis: Mapping[str, Any],
    evidence_state: str, missing: list[str],
) -> dict[str, Any]:
    if evidence_state not in {
        "SOURCE_DATED_NOTICE_OWNER_VERIFIED",
        "OFFICIAL_BOUNDED_FORECAST_AND_ESTIMATE",
        "HISTORICAL_SOURCE_OWNER_ONLY",
        "OFFICIAL_US_TRANSACTION_ACTION_DATED_SAMPLE",
    }:
        raise ValueError("INVALID_MARKET_EVIDENCE_STATE")
    if not isinstance(source_uri, str) or not source_uri.startswith("https://"):
        raise ValueError("PROVENANCE_URI_REQUIRED")
    # Source-evidence utility is an INTERNAL routing score, not customer
    # demand, originality pricing, resale approval or sale probability.
    if source == "gb_find_a_tender_ocds":
        utility = {
            "score": 72,
            "tier": "PRIORITISE_BUYER_PROBLEM_VERIFICATION",
            "reason": "Dated public requirement, named public buyer and explicit deadline",
        }
    elif source == "us_usaspending_transactions":
        utility = {
            "score": 43,
            "tier": "HISTORICAL_MARKET_RESEARCH",
            "reason": "Official dated financial-action observations; sample is not all awards or new contracts",
        }
    else:
        utility = {
            "score": 38,
            "tier": "COMMODITY_DATA_NEEDS_ORIGINAL_VALUE_ADD",
            "reason": "Official regional forecast; client application and differentiation not proven",
        }
    utility["verified_customer_demand"] = False
    utility["score_is_sales_probability_or_revenue"] = False
    return {
        "product_contract": _contract(product),
        "usefulness_qualification": utility,
        "original_evidence_source": source, "original_evidence_uri": source_uri,
        "original_source_event_at": original_date,
        "source_evidence_sha256": source_digest,
        "evidence_state": evidence_state,
        "original_derived_intelligence": statement,
        "analysis": dict(analysis),
        "missing_product_evidence": missing,
        "original_analysis_is_a_market_signal_not_a_customer": True,
        "license_or_customer_terms_cleared": False,
        "raw_source_records_redistributed": False,
        "product_release_status": "INTERNAL_CLAIM_EVIDENCE_REVIEW_ONLY",
        "claimed_sales_revenue": None,
    }


def mine_uk_procurement_owner(root: Path, *, now: datetime) -> dict[str, Any]:
    source = _strict_json(root, PROCUREMENT_OWNER, max_bytes=150_000)
    if source is None:
        return {"status": "ORIGINAL_PROCUREMENT_OWNER_RECEIPT_MISSING", "products": []}
    record, receipt_digest = source
    rows = record.get("records")
    if (record.get("schema_version") != "empire.acquisition_official_procurement_review.v1"
            or record.get("mode") != "OBSERVE" or record.get("crm_writes") is not False
            or record.get("outbound_authorized") is not False
            or not isinstance(rows, list) or len(rows) > 50):
        return {"status": "ORIGINAL_PROCUREMENT_OWNER_RECEIPT_UNTRUSTED", "products": []}
    receipt_time = _utc(record.get("observed_at"))
    if receipt_time is None or not timedelta(0) <= now - receipt_time <= timedelta(days=7):
        return {"status": "ORIGINAL_PROCUREMENT_OWNER_RECEIPT_STALE", "products": []}
    seen = set()
    products = []
    held = Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            held["invalid_record"] += 1
            continue
        ref, ocid = row.get("notice_ref"), row.get("ocid")
        uri = row.get("notice_url")
        posted, closes = _utc(row.get("notice_release_at")), _utc(row.get("tender_closes_at"))
        org, title = row.get("buyer_organisation"), row.get("title")
        source_hash = row.get("source_sha256")
        if (row.get("source") != "find_a_tender"
                or not isinstance(ref, str) or not _NOTICE.fullmatch(ref)
                or not isinstance(ocid, str) or not _OCID.fullmatch(ocid)
                or uri != OGL_NOTICE + ref
                or not isinstance(source_hash, str) or not _SHA.fullmatch(source_hash)
                or posted is None or closes is None or not posted <= receipt_time <= now < closes
                or not isinstance(org, str) or not 2 <= len(org) <= 130
                or not isinstance(title, str) or not 3 <= len(title) <= 230
                or row.get("buyer_interest_in_empire_ai_verified") is not False
                or row.get("bid_eligibility_verified") is not False
                or row.get("outbound_authorized") is not False):
            held["insufficient_or_conflicting_provenance"] += 1
            continue
        if ocid in seen:
            held["duplicate_ocid"] += 1
            continue
        seen.add(ocid)
        days = (closes - now).total_seconds() / 86400
        # Opportunity usefulness: first-party dated need, named public buyer,
        # open submission window. Do not conflate public budget with Empire's revenue.
        urgency = "TIME_SENSITIVE" if days <= 14 else "OPEN_DEADLINE_AHEAD"
        statement = (
            f"An official {org} tender notice for {title} was published "
            f"{posted.date().isoformat()} and has a stated deadline of "
            f"{closes.isoformat()}. This is an externally published "
            "requirement, not an Empire AI sales enquiry or proof of supplier eligibility."
        )
        products.append(_internal_item(
            product="opportunity_feed", source="gb_find_a_tender_ocds",
            source_uri=uri, original_date=posted.isoformat(),
            source_digest=source_hash, statement=statement,
            analysis={
                "official_notice_ref": ref, "ocid": ocid, "public_buyer": org,
                "public_notice_title": title, "submission_deadline": closes.isoformat(),
                "days_until_deadline": round(days, 2),
                "deadline_state": urgency,
                "published_tender_estimate_gbp": (
                    row.get("published_estimated_value_gbp")
                    if row.get("published_value_source") == "OFFICIAL_OCDS_TENDER_VALUE_NOT_BINDING"
                    else None),
                "estimate_not_empire_revenue": True,
                "observed_open_as_of": receipt_time.isoformat(),
                "independent_supplier_document_review_completed": False,
                "first_party_source_owner_receipt_sha256": receipt_digest,
            }, evidence_state="SOURCE_DATED_NOTICE_OWNER_VERIFIED",
            missing=["independent_notice_recheck", "supplier_eligibility",
                     "buyer_specific_product_fit", "source_field_rights_for_customer_delivery"],
        ))
    return {
        "status": "OWNER_OBSERVED_PUBLIC_REQUIREMENTS_MINED" if products else "NO_VALID_CURRENT_PROCUREMENT_OWNER_RECORDS",
        "owner_receipt_sha256": receipt_digest, "owner_observed_at": receipt_time.isoformat(),
        "original_record_count": len(rows), "qualified_internal_notices": len(products),
        "source_duplicate_or_invalid": dict(held),
        "products": products, "verified_customer_count": 0,
        "external_bids_submitted": 0, "customer_claim_rights_cleared": False,
    }


def _official_neso_json(url: str) -> Mapping[str, Any]:
    if url not in {NESO_REGIONAL, NESO_NATIONAL}:
        raise ValueError("UNAPPROVED_ENERGY_PROVIDER_ENDPOINT")
    req = Request(url, method="GET", headers={
        "Accept": "application/json",
        "User-Agent": "EmpireAI-Brokerage-Official-Energy-Research/1.0 (empire-ai.co.uk)",
    })
    with build_opener(_NoRedirect).open(req, timeout=8) as response:
        if (response.status != 200 or response.geturl() != url
                or not response.headers.get("Content-Type", "").startswith("application/json")):
            raise ValueError("NESO_SOURCE_IDENTITY_UNVERIFIED")
        raw = response.read(70_001)
        if len(raw) > 70_000:
            raise ValueError("NESO_SOURCE_OVERSIZED")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("NESO_SOURCE_SHAPE_INVALID")
        return result


def _pct(value: Any) -> float | None:
    if type(value) not in (int, float) or not 0 <= value <= 100:
        return None
    return round(float(value), 2)


def mine_neso_energy(
    regional: Mapping[str, Any], national: Mapping[str, Any],
    *, now: datetime,
) -> dict[str, Any]:
    """Region-level forecast intelligence; avoid fabricated company-level demand."""
    try:
        region_window = regional["data"]
        national_window = national["data"]
        if not isinstance(region_window, list) or len(region_window) != 1:
            raise ValueError("REGIONAL_WINDOW_INVALID")
        if not isinstance(national_window, list) or len(national_window) != 1:
            raise ValueError("NATIONAL_WINDOW_INVALID")
        block = region_window[0]
        reference = national_window[0]
        start, finish = _utc(block.get("from")), _utc(block.get("to"))
        n_start, n_end = _utc(reference.get("from")), _utc(reference.get("to"))
        if (start is None or finish is None or start != n_start or finish != n_end
                or not timedelta(minutes=20) <= finish - start <= timedelta(minutes=60)
                or not timedelta(minutes=0) <= now - start <= timedelta(hours=3)):
            raise ValueError("ENERGY_SAMPLE_NOT_SAME_RECENT_HALF_HOUR")
        rows = block.get("regions")
        if not isinstance(rows, list) or not 14 <= len(rows) <= 30:
            raise ValueError("REGION_COVERAGE_UNTRUSTED")
        observations = []
        region_ids = set()
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("REGION_NOT_MAPPING")
            region_id = row.get("regionid")
            if type(region_id) is not int or not REGION_ID_MIN <= region_id <= REGION_ID_MAX:
                continue  # Exclude aggregate England, Scotland, Wales etc.
            if region_id in region_ids:
                raise ValueError("DUPLICATE_ENERGY_REGION")
            region_ids.add(region_id)
            shortname = row.get("shortname")
            if not isinstance(shortname, str) or not re.fullmatch(r"[A-Za-z0-9 '&,-]{3,50}", shortname):
                raise ValueError("INVALID_REGION_NAME")
            intensity = row.get("intensity")
            forecast = intensity.get("forecast") if isinstance(intensity, Mapping) else None
            if type(forecast) not in (int, float) or not 0 <= forecast <= 2000:
                raise ValueError("ENERGY_FORECAST_INVALID")
            mix = row.get("generationmix")
            if not isinstance(mix, list) or len(mix) > 18:
                raise ValueError("REGION_MIX_INVALID")
            fuels: dict[str, float] = {}
            for entry in mix:
                if not isinstance(entry, Mapping):
                    raise ValueError("REGION_FUEL_SHAPE")
                fuel, pct = entry.get("fuel"), _pct(entry.get("perc"))
                if fuel not in _FUELS or pct is None or fuel in fuels:
                    raise ValueError("INVALID_FUEL_OR_DUPLICATE")
                fuels[fuel] = pct
            if not 98 <= sum(fuels.values()) <= 102:
                raise ValueError("REGION_MIX_DOES_NOT_TOTAL_100")
            observations.append({
                "region_id": region_id, "region": shortname,
                "renewable_wind_solar_percent_estimated": round(fuels.get("wind", 0) + fuels.get("solar", 0), 2),
                "modeled_consumption_carbon_intensity_forecast_gco2_kwh": round(float(forecast), 1),
            })
        if len(observations) != REQUIRED_REGION_COUNT:
            raise ValueError("PARTIAL_DNO_REGIONAL_COVERAGE")
        n_intensity = reference.get("intensity")
        if not isinstance(n_intensity, Mapping):
            raise ValueError("NATIONAL_INTENSITY_ABSENT")
        n_forecast, n_actual = n_intensity.get("forecast"), n_intensity.get("actual")
        if type(n_forecast) not in (int, float) or not 0 <= n_forecast <= 2000:
            raise ValueError("NATIONAL_FORECAST_INVALID")
        if n_actual is not None and (type(n_actual) not in (int, float) or not 0 <= n_actual <= 2000):
            raise ValueError("NATIONAL_ESTIMATE_INVALID")
        ranking = sorted(observations, key=lambda item: (
            -item["renewable_wind_solar_percent_estimated"], item["region_id"]))
        spread = round(max(x["renewable_wind_solar_percent_estimated"] for x in observations)
                       - min(x["renewable_wind_solar_percent_estimated"] for x in observations), 2)
    except (KeyError, IndexError, TypeError, ValueError):
        return {"status": "NESO_SOURCE_VALUES_NOT_VERIFIED", "products": [],
                "source_rights_auto_approved": False}
    record = _internal_item(
        product="market_signal_feed", source="gb_neso_carbon_intensity",
        source_uri=NESO_REGIONAL,
        original_date=start.isoformat(),
        source_digest=_digest([regional, national]),
        statement=(
            f"NESO regional modelling indicates a {spread:.1f}-percentage-point "
            f"spread in wind-and-solar shares across 14 GB distribution regions "
            f"for the {start.isoformat()} settlement window. "
            "These are modelled electricity-consumption forecasts, not "
            "measured installation growth, construction demand or company leads."
        ),
        analysis={
            "window_from": start.isoformat(), "window_to": finish.isoformat(),
            "region_count": len(observations),
            "regional_wind_solar_forecast_spread_percentage_points": spread,
            "ranked_regions": ranking,
            "national_carbon_intensity_forecast_gco2_kwh": float(n_forecast),
            "national_carbon_intensity_estimated_actual_gco2_kwh": (
                float(n_actual) if n_actual is not None else None),
            "source_attribution": "National Energy System Operator; CC BY 4.0",
            "modelled_regional_mix_not_installed_capacity": True,
            "region_aggregation_not_population_weighted": True,
        },
        evidence_state="OFFICIAL_BOUNDED_FORECAST_AND_ESTIMATE",
        missing=["customer_specific_market_use", "source_data_quality_sampling",
                 "review_attribution_and_commercial_rights"],
    )
    return {
        "status": "OFFICIAL_NESO_REGIONAL_SOURCE_MINED",
        "observed_source_period_start": start.isoformat(),
        "region_count": len(observations),
        "official_api_calls": 2,
        "products": [record],
        "verified_installers_or_buyers": None, "resale_rights_auto_approved": False,
    }


def mine_company_owner(root: Path, *, now: datetime) -> dict[str, Any]:
    source = _strict_json(root, REGISTRY_OWNER, max_bytes=90_000)
    if not source:
        return {"status": "COMPANY_REGISTRY_OWNER_RECEIPT_MISSING", "products": []}
    obj, digest = source
    if (obj.get("schema_version") != "empire.tam.official_company_registry_evidence.v1"
            or obj.get("mode") != "OBSERVE" or obj.get("database_write_performed") is not False
            or obj.get("outbound_authorized") is not False):
        return {"status": "COMPANY_REGISTRY_OWNER_RECEIPT_UNTRUSTED", "products": []}
    stamp = _utc(obj.get("generated_at"))
    rows = obj.get("records")
    if stamp is None or not isinstance(rows, list) or len(rows) > 100:
        return {"status": "COMPANY_REGISTRY_OWNER_SCHEMA_UNVERIFIED", "products": []}
    valid = sum(1 for row in rows if isinstance(row, Mapping)
                and isinstance(row.get("first_party_registration_number"), str)
                and re.fullmatch(r"[A-Z0-9]{7,9}", row["first_party_registration_number"]))
    days = (now - stamp).total_seconds() / 86400
    if days < 0:
        return {"status": "COMPANY_REGISTRY_OWNER_CLOCK_CONFLICT", "products": []}
    return {
        "status": ("HISTORICAL_COMPANY_EVIDENCE_ONLY"
                   if days > 7 else "SOURCE_OWNER_COMPANY_EVIDENCE_NEEDS_LIVE_RECHECK"),
        "owner_receipt_sha256": digest,
        "historical_registry_records": valid, "source_observed_at": stamp.isoformat(),
        "days_since_owner_observation": round(days, 2),
        "new_company_changes_proven": False,
        "products": [],  # Do NOT market dated historic registry data as current.
        "live_company_api_authenticated": False,
    }


def build_source_specific_products(
    root: Path, *, now: datetime,
    neso_fetch: Callable[[str], Mapping[str, Any]] = _official_neso_json,
    us_fetch: Callable[[str, datetime], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if now.utcoffset() is None:
        raise ValueError("UTC_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    procurement = mine_uk_procurement_owner(root, now=now)
    company = mine_company_owner(root, now=now)
    agency_original = qualify_existing_agency_report(root, now=now)
    targeted_buyer_scope = assess_targeted_buyer_demand(root, now=now)
    # This read-only buyer-need observer reuses the ORIGINAL official UK
    # procurement source adapter; it never submits bids or creates CRM leads.
    public_research = (
        verify_public_research_demand(now=now)
        if root.resolve() == Path("/srv/empire_os")
        else None
    )
    try:
        neso = mine_neso_energy(neso_fetch(NESO_REGIONAL), neso_fetch(NESO_NATIONAL), now=now)
    except (OSError, ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError):
        neso = {
            "status": "OFFICIAL_NESO_ENDPOINT_FAILED", "products": [],
            "source_rights_auto_approved": False,
        }
    us_source_fetch = us_fetch or _fetch_us_spending_transactions
    us_responses = {}
    for term in US_KEYWORDS:
        try:
            us_responses[term] = us_source_fetch(term, now)
        except (OSError, ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError):
            continue
    us = mine_us_spending_transactions(us_responses, now=now)
    items = procurement["products"] + neso["products"] + company["products"] + us["products"]
    items.sort(key=lambda row: -row["usefulness_qualification"]["score"])
    if len(items) != len({(x["product_contract"]["key"], x["original_evidence_source"],
                          x["original_evidence_uri"],
                          x["analysis"].get("search_keyword")) for x in items}):
        raise ValueError("DUPLICATE_DATA_PRODUCT_EVIDENCE_KEY")
    return {
        "schema_version": SCHEMA, "status": "MULTISECTOR_SOURCE_SPECIFIC_MINING_EXECUTED",
        "observed_at": now.isoformat(), "countries": ["GB", "US"],
        "sectors": ["procurement", "energy", "companies", "us_federal_financial_actions"],
        "source_status": {
            "gb_procurement": procurement["status"],
            "gb_energy": neso["status"],
            "gb_companies": company["status"],
            "us_federal_financial_actions": us["status"],
        },
        "original_product_count": len(items),
        "products_ranked_by_internal_usefulness": True,
        "source_bound_products": items,
        "original_agency_report_buyer_fit": agency_original,
        "targeted_agency_publisher_buyer_scope": targeted_buyer_scope,
        "public_research_buyer_needs": public_research,
        "existing_product_contracts_used": sorted({x["product_contract"]["key"] for x in items}),
        "verified_external_customers": None, "claimed_revenue": None,
        "no_customer_delivery": True, "no_paid_provider_or_email": True,
        "raw_third_party_source_records_persisted": False,
        "canonical_crm_writes": False, "execution_authority": "none",
    }

# Fourth source family: U.S. federal awarded-spend research, distinct from
# UK OPEN tender notices. USAspending POST is read-only SEARCH, not a write.
US_SPENDING = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"
US_KEYWORDS = ("software", "solar")
US_FIELDS = ("Award ID", "Recipient Name", "Transaction Amount",
             "Awarding Agency", "Action Date")
US_TYPES = ("A", "B", "C", "D")
US_LIMIT = 10


def _transaction_request(*, term: str, now: datetime) -> dict[str, Any]:
    if term not in US_KEYWORDS:
        raise ValueError("UNKNOWN_US_AWARD_SECTOR")
    return {
        "filters": {
            "keywords": [term],
            "time_period": [{
                "start_date": (now.date() - timedelta(days=45)).isoformat(),
                "end_date": now.date().isoformat(),
            }],
            "award_type_codes": list(US_TYPES),
        },
        "fields": list(US_FIELDS),
        "sort": "Action Date", "order": "desc",
        "page": 1, "limit": US_LIMIT,
    }


def _fetch_us_spending_transactions(term: str, now: datetime) -> Mapping[str, Any]:
    """Official USAspending financial-action search POST, read-only."""
    if term not in US_KEYWORDS:
        raise ValueError("UNAPPROVED_FEDERAL_AWARD_QUERY")
    payload = json.dumps(_transaction_request(term=term, now=now)).encode("utf-8")
    req = Request(US_SPENDING, data=payload, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "EmpireAI-Brokerage-US-Transaction-Research/1.0 (empire-ai.co.uk)",
    })
    with build_opener(_NoRedirect).open(req, timeout=9) as response:
        if (response.status != 200 or response.geturl() != US_SPENDING
                or not response.headers.get("Content-Type", "").startswith("application/json")):
            raise ValueError("US_TREASURY_SOURCE_UNVERIFIED")
        raw = response.read(75_001)
        if len(raw) > 75_000:
            raise ValueError("US_AWARD_RESPONSE_TOO_LARGE")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("US_AWARD_SOURCE_SHAPE_UNVERIFIED")
    return obj


def mine_us_spending_transactions(
    responses: Mapping[str, Mapping[str, Any]], *, now: datetime,
) -> dict[str, Any]:
    """Mine genuinely dated financial ACTIONS, not new contract start claims.

    An action can be a modification, deobligation or zero-dollar change.
    The first 10 most recent matching actions are a biased search sample;
    no sampled amount is advertised as a public-sector market total.
    """
    if now.utcoffset() is None:
        raise ValueError("TRANSACTION_CLOCK_NEEDS_UTC")
    items: list[dict[str, Any]] = []
    sectors: list[dict[str, Any]] = []
    earliest = now.date() - timedelta(days=45)
    for term in US_KEYWORDS:
        response = responses.get(term)
        if not isinstance(response, Mapping):
            sectors.append({"sector": term, "status": "US_SOURCE_NOT_RETURNED"})
            continue
        rows = response.get("results")
        if not isinstance(rows, list) or len(rows) > US_LIMIT or response.get("limit") != US_LIMIT:
            sectors.append({"sector": term, "status": "UNTRUSTED_US_TRANSACTION_RESPONSE"})
            continue
        positive = negative = zero = recent = old = future = invalid = 0
        agency_counts: Counter[str] = Counter()
        dates = []
        unique = set()
        for row in rows:
            if not isinstance(row, Mapping):
                invalid += 1
                continue
            amount = row.get("Transaction Amount")
            agency, award, date = (
                row.get("Awarding Agency"), row.get("Award ID"),
                row.get("Action Date"),
            )
            if (not isinstance(award, str) or not 3 <= len(award) <= 180
                    or not isinstance(agency, str) or not 3 <= len(agency) <= 140
                    or not re.fullmatch(r"[A-Za-z0-9 ./&(),'-]{3,140}", agency)
                    or type(amount) not in (int, float)
                    or not -1e12 <= amount <= 1e12
                    or not isinstance(date, str)):
                invalid += 1
                continue
            try:
                when = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                invalid += 1
                continue
            identity = row.get("internal_id")
            # The official transaction identity is preferred. Where omitted,
            # exact source field dedup protects the derived sample.
            key = identity if type(identity) in (int, str) and identity else (
                award, date, str(amount), agency
            )
            if key in unique:
                continue
            unique.add(key)
            if when > now.date():
                future += 1
                continue
            if when < earliest:
                old += 1
                continue
            recent += 1
            agency_counts[agency] += 1
            dates.append(when)
            if amount > 0:
                positive += 1
            elif amount < 0:
                negative += 1
            else:
                zero += 1
        if recent == 0:
            sectors.append({
                "sector": term,
                "status": "NO_ACTION_DATED_CURRENT_SOURCE_SAMPLE",
                "older_action_date_records_held": old,
                "future_action_date_records_held": future,
                "invalid_records_held": invalid,
            })
            continue
        latest = max(dates)
        original = latest.isoformat() + "T00:00:00+00:00"
        evidence = _internal_item(
            product="market_signal_feed", source="us_usaspending_transactions",
            source_uri=US_SPENDING, original_date=original,
            source_digest=_digest(response),
            statement=(
                f"An official USAspending search for {term} returned {recent} "
                f"distinct financial transactions dated within the preceding "
                f"45 days (latest {latest.isoformat()}): {positive} positive "
                f"obligations, {negative} deobligations and {zero} zero-dollar "
                "actions in a 10-result capped sample. These are recorded "
                "financial actions, NOT ten newly awarded contracts, new "
                "buyer enquiries, future spending or market-wide totals."
            ),
            analysis={
                "search_keyword": term,
                "source_record_type": "DATED_FEDERAL_FINANCIAL_TRANSACTION",
                "search_window": [earliest.isoformat(), now.date().isoformat()],
                "last_original_financial_action_date": latest.isoformat(),
                "source_rows_in_sample": len(rows),
                "distinct_recent_financial_actions_in_sample": recent,
                "positive_obligation_event_count": positive,
                "negative_deobligation_event_count": negative,
                "zero_amount_action_event_count": zero,
                "older_action_records_excluded": old,
                "future_action_records_excluded": future,
                "invalid_records_excluded": invalid,
                "agency_mentions_in_capped_sample": dict(sorted(agency_counts.items())),
                "not_a_new_contract_or_open_procurement": True,
                "total_population_or_total_spend_not_computed": True,
                "original_event_basis": "OFFICIAL_ACTION_DATE_NOT_CONTRACT_START_DATE",
                "record_provenance": "United States Treasury USAspending",
            },
            evidence_state="OFFICIAL_US_TRANSACTION_ACTION_DATED_SAMPLE",
            missing=["full_transaction_population",
                     "independent_agency_procurement_need",
                     "source_specific_field_reuse_review", "buyer_validation"],
        )
        items.append(evidence)
        sectors.append({
            "sector": term, "status": "CURRENT_FINANCIAL_ACTION_SAMPLE_MINED",
            "genuine_original_dated_actions": recent,
            "positive_obligation_event_count": positive,
            "negative_deobligation_event_count": negative,
        })
    return {
        "status": ("US_TREASURY_FINANCIAL_ACTIONS_MINED"
                   if items else "NO_CURRENT_US_TREASURY_ACTIONS_VERIFIED"),
        "keyword_sectors": sectors, "products": items,
        "transactions_are_not_new_contracts": True,
        "source_specific_resale_authorized": False,
    }


def validate_source_specific_product_report(report: Any) -> bool:
    """Reject forged product activation, revenue, entitlement or source proofs."""
    if not isinstance(report, Mapping):
        return False
    if report.get("status") == "NONCANONICAL_RUNTIME_NOT_RUN":
        return (report.get("original_product_count") == 0
                and report.get("no_customer_delivery") is True
                and report.get("source_bound_products") == [])
    if (report.get("schema_version") != SCHEMA
            or report.get("status") != "MULTISECTOR_SOURCE_SPECIFIC_MINING_EXECUTED"
            or report.get("no_customer_delivery") is not True
            or report.get("no_paid_provider_or_email") is not True
            or report.get("raw_third_party_source_records_persisted") is not False
            or report.get("canonical_crm_writes") is not False
            or report.get("execution_authority") != "none"
            or report.get("claimed_revenue") is not None
            or report.get("verified_external_customers") is not None
            or ("original_agency_report_buyer_fit" in report
                and not validate_agency_fit_receipt(report["original_agency_report_buyer_fit"]))
            or (report.get("public_research_buyer_needs") is not None
                and not validate_public_research_demand(report["public_research_buyer_needs"]))
            or ("targeted_agency_publisher_buyer_scope" in report
                and not validate_targeted_buyer_demand(report["targeted_agency_publisher_buyer_scope"]))
            or ("first_party_buyer_fit_summary" in report
                and not validate_first_party_fit_summary(report["first_party_buyer_fit_summary"]))):
        return False
    products = report.get("source_bound_products")
    if (not isinstance(products, list) or not 0 <= len(products) <= 55
            or report.get("original_product_count") != len(products)):
        return False
    accepted = set()
    for product in products:
        if not isinstance(product, Mapping):
            return False
        contract = product.get("product_contract")
        uri = product.get("original_evidence_uri")
        source = product.get("original_evidence_source")
        digest = product.get("source_evidence_sha256")
        if (not isinstance(contract, Mapping)
                or contract.get("key") not in ("opportunity_feed", "market_signal_feed")
                or contract.get("customer_claim_release_ready") is not False
                or contract.get("customer_access_provisioned") is not False
                or contract.get("customer_distribution_authorized") is not False
                or product.get("product_release_status") != "INTERNAL_CLAIM_EVIDENCE_REVIEW_ONLY"
                or product.get("license_or_customer_terms_cleared") is not False
                or product.get("raw_source_records_redistributed") is not False
                or not isinstance(digest, str) or not _SHA.fullmatch(digest)
                or not isinstance(source, str)
                or not isinstance(uri, str)
                or not (
                    uri in (NESO_REGIONAL, US_SPENDING)
                    or (source == "gb_find_a_tender_ocds"
                        and uri.startswith(OGL_NOTICE)
                        and _NOTICE.fullmatch(uri.removeprefix(OGL_NOTICE)))
                )):
            return False
        if source == "gb_neso_carbon_intensity" and uri != NESO_REGIONAL:
            return False
        if source == "us_usaspending_transactions" and uri != US_SPENDING:
            return False
        if source not in ("gb_neso_carbon_intensity", "gb_find_a_tender_ocds", "us_usaspending_transactions"):
            return False
        key = (contract["key"], source, uri,
               product.get("analysis", {}).get("search_keyword")
               if isinstance(product.get("analysis"), Mapping) else None)
        if key in accepted:
            return False
        accepted.add(key)
    return True
