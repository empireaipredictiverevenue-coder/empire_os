"""Commercially targeted Data Brokerage acquisition sequencer.

This is the decision component of the EXISTING brokerage/source-intelligence
department. The product/market brief is the starting point, NOT raw collection
volume. Existing canonical sources and owner receipts are its only facts.
Every action identifies what data is needed and what evidence is missing;
it does not create paid buyers, subscriptions or unlicensed data products.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from typing import Any, Mapping
import json
import re

from empire_os.source_intelligence import SOURCES, SourceContract
from empire_os.intelligence_data_products import data_product_catalog

SCHEMA = "empire.data_brokerage.acquisition_sequence.v1"
MAX_RECEIPT = 170_000

# Market hypotheses, NOT claims that a buyer wants to buy this data.
# A deliverable is useful only if its essential original evidence exists.
@dataclass(frozen=True)
class Demand:
    key: str
    sector: str
    buyer_problem: str
    proposed_output: str
    roles_any: tuple[str, ...]
    coverage_groups: tuple[tuple[str, ...], ...]
    niches: tuple[str, ...]
    ideal_refresh_hours: int
    source_types: tuple[str, ...]
    target_country_codes: tuple[str, ...] = ()
    verified_customer_orders: int = 0


DEMANDS = (
    Demand("company_change", "companies",
           "Know which real businesses exist and what changed",
           "Entity-verified business changes with date and provenance",
           ("identity", "company_status", "filings", "business_status"),
           (("identity", "company_status", "business_status"), ("filings", "company_status", "business_status")),
           ("all",), 168, ("official_registry",)),
    Demand("public_procurement", "procurement",
           "Identify genuinely open and relevant purchasing requirements",
           "Timed, source-linked opportunities with tender versus award stage",
           ("procurement_notice", "tender", "federal_award", "award"),
           (("procurement_notice", "tender", "federal_award"), ("buyer_identity", "recipient", "awarding_agency")),
           ("procurement", "technology", "construction", "healthcare"),
           48, ("official_procurement_data", "official_federal_award_data")),
    Demand("renewable_energy", "energy",
           "Locate verified energy investment and capacity shifts",
           "Installation and capacity trend intelligence by territory and time",
           ("installation", "installation_density", "capacity", "historic_adoption", "technology"),
           (("installation", "installation_density", "capacity", "historic_adoption"), ("geography", "territory", "location")),
           ("solar", "battery_storage", "energy", "heat_pump"),
           720, ("official_energy_registry", "official_energy_installation_data")),
    Demand("grid_carbon_signals", "electricity_grid",
           "Identify modelled grid carbon and fuel-mix shifts without inventing installations",
           "Half-hourly regional electricity-consumption forecasts by fuel",
           ("regional_carbon_intensity", "generation_mix_forecast"),
           (("regional_carbon_intensity", "generation_mix_forecast"), ("geography", "territory")),
           ("grid", "energy", "solar"), 1, ("official_energy_forecast",)),
    Demand("federal_spending_activity", "public_spending",
           "Identify genuine dated federal financial actions without inventing new awards",
           "Source-linked transaction action counts and adjustments by agency and sector",
           ("financial_action", "agency_spend", "award_modification"),
           (("financial_action", "award_modification"), ("agency_spend",)),
           ("procurement", "technology", "energy", "solar"), 24,
           ("official_federal_transaction_data",)),
    Demand("property_development", "property",
           "Identify real changes to land use and development",
           "Planning, land, issued-permit and development intelligence",
           ("planning", "development", "geospatial", "property", "permit_type"),
           (("planning", "development", "property", "permit_type"), ("geospatial", "territory", "location", "property")),
           ("property", "permits", "construction", "roofing"),
           168, ("official_planning_data", "official_construction_permits")),
    Demand("trade_capacity", "trades",
           "Measure verified contractor supply without reselling directories",
           "Trade capacity, registered speciality and territory gap research",
           ("certification", "trade", "installer", "registration"),
           (("certification", "trade", "installer", "registration"), ("territory", "location", "quality")),
           ("solar", "roofing", "hvac", "heat_pump", "insulation"),
           168, ("certified_trade_directory", "government_endorsed_directory", "government_trade_directory")),
    Demand("healthcare_procurement", "healthcare",
           "Find procurement evidence for healthcare workforce technology",
           "Healthcare technology and staffing procurement signal reports",
           ("procurement_notice", "tender", "award", "federal_award"),
           (("procurement_notice", "tender", "federal_award"), ("buyer_identity", "awarding_agency", "recipient")),
           ("healthcare",),
           48, ("official_procurement_data", "official_federal_award_data")),
    Demand("private_capital", "investment",
           "Research corporate consolidation using dated verified records",
           "Ownership/filings research with explicitly missing funding proof",
           ("company_status", "filings", "identity", "accounts"),
           (("identity", "company_status"), ("filings", "accounts")),
           ("all",), 720, ("official_registry",)),
    Demand("warehouse_logistics", "logistics",
           "Research physical logistics sites rather than infer operators",
           "Property and industrial land-use change research",
           ("property", "planning", "development", "geospatial"),
           (("planning", "property"), ("geospatial", "development", "location")),
           ("property", "logistics", "warehouse"),
           168, ("official_planning_data",)),
    Demand("web_competitors", "digital",
           "Research competitor sources without inventing rankings or traffic",
           "Historically qualified domain discovery and current verification queue",
           ("web_graph", "page_level_referring_link"),
           (("web_graph",), ("page_level_referring_link",)),
           ("seo", "marketing", "web"),
           168, ("historical_web_graph",)),
    Demand("legal_insurance", "legal",
           "Research filed matters without claiming liability or client intent",
           "Dated legal and insurance market activity research",
           ("court_docket", "case_event"),
           (("court_docket",), ("case_event",)),
           ("legal", "insurance", "litigation"),
           168, ("court_records",)),
)

# A lane is a country, sector and buyer output. Lane rotation covers multiple
# markets before revisiting the same industry. Not all public sources are APIs.
DISCOVERY_LANES = (
    ("GB", "public_procurement", "site:gov.uk public contract notice open data API"),
    ("US", "company_change", "site:gov business registry bulk downloads company data"),
    ("DE", "renewable_energy", "site:bund.de solar energy installation open data"),
    ("AU", "trade_capacity", "site:gov.au licensed contractor register downloadable dataset"),
    ("GB", "healthcare_procurement", "site:nhs.uk workforce technology procurement open dataset"),
    ("US", "property_development", "site:gov building permits land use dataset API"),
    ("IE", "company_change", "site:gov.ie business registry company data download"),
    ("FR", "renewable_energy", "site:gouv.fr energie solaire installations open data"),
    ("CA", "company_change", "site:gc.ca business registry corporation public data"),
    ("NZ", "property_development", "site:govt.nz planning land development public datasets"),
    ("GB", "trade_capacity", "site:gov.uk certified solar contractors companies data"),
    ("US", "public_procurement", "site:gov federal contract opportunities public API"),
    ("NL", "renewable_energy", "site:overheid.nl renewable energy capacity data API"),
    ("BE", "company_change", "site:belgium.be enterprise registry open data"),
    ("IT", "private_capital", "site:gov.it companies filings open data dataset"),
    ("ES", "renewable_energy", "site:gob.es instalaciones energia renovable datos abiertos"),
    ("PT", "property_development", "site:gov.pt building planning development public datasets"),
    ("GB", "web_competitors", "common crawl public web graph dataset documentation"),
    ("US", "legal_insurance", "site:gov court docket case filings public data API"),
    ("DE", "company_change", "site:bund.de companies register open data"),
    ("GB", "warehouse_logistics", "site:gov.uk brownfield land industrial building register open data"),
    ("US", "healthcare_procurement", "site:gov healthcare technology government procurement award data"),
    ("AU", "renewable_energy", "site:gov.au solar installations energy data open API"),
    ("IE", "trade_capacity", "site:gov.ie registered solar installers dataset"),
    ("GB", "grid_carbon_signals", "site:neso.energy regional carbon intensity generation mix energy forecast data"),
    ("US", "federal_spending_activity", "site:usaspending.gov dated federal transaction financial action API"),
)

# Existing product contracts, never a second billing or deliverables catalogue.
CONTRACT_ROUTES = {
    "company_change": "entity_graph_export",
    "public_procurement": "opportunity_feed",
    "renewable_energy": "market_signal_feed",
    "grid_carbon_signals": "market_signal_feed",
    "federal_spending_activity": "market_signal_feed",
    "property_development": "property_intelligence_monitor",
    "trade_capacity": "market_signal_feed",
    "healthcare_procurement": "opportunity_feed",
    "private_capital": "private_capital_intelligence",
    "warehouse_logistics": "spatial_physical_intelligence",
    "web_competitors": "market_signal_feed",
    "legal_insurance": "opportunity_feed",
}

STAGES = (
    "TARGET_REQUIREMENT",
    "SOURCE_DISCOVERY",
    "SCHEMA_PROVENANCE",
    "ORIGINAL_RECORD_MINING",
    "IDENTITY_NORMALISATION",
    "INDEPENDENT_CROSS_CHECK",
    "USEFULNESS_REVIEW",
    "RIGHTS_AND_PRIVACY",
    "ORIGINAL_PRODUCT_PACKAGING",
    "BUYER_VALIDATION",
    "LICENSED_FULFILMENT",
)


def countries() -> tuple[str, ...]:
    """Use registered countries, not a fictional global coverage claim."""
    return tuple(sorted(set(s.country_code for s in SOURCES.values())))


def _score(source: SourceContract, demand: Demand) -> dict[str, Any] | None:
    if source.country_code not in countries():
        return None
    roles = set(source.roles)
    observed_roles = sorted(roles.intersection(demand.roles_any))
    niche_relevance = bool(roles and
                          (set(source.niches).intersection(demand.niches) or "all" in source.niches))
    types_match = source.source_type in demand.source_types
    if not observed_roles and not types_match:
        return None
    if not niche_relevance and not types_match:
        return None
    group_matches = [bool(set(group).intersection(roles)) for group in demand.coverage_groups]
    role_points = min(40, len(observed_roles) * 12)
    coverage_points = sum(15 for matched in group_matches if matched)
    type_points = 12 if types_match else 0
    niche_points = 8 if niche_relevance else 0
    published_freshness = str(source.freshness).casefold()
    freshness_points = 5 if any(tag in published_freshness for tag in
                                ("daily", "current", "real_time", "continuous")) else 2
    research_penalty = 8 if source.production_status != "verified" else 0
    access_requires_budget = any(tag in source.licence.casefold() for tag in
                                 ("paid_api", "commercial_api", "registered_web_service"))
    access_penalty = 15 if access_requires_budget else 0
    declared_provenance_points = min(5, max(0, source.provenance_strength // 20))
    # Actual freshness and redistribution licences need independent receipts.
    score = max(0, min(95, role_points + coverage_points + type_points
                      + niche_points + freshness_points + declared_provenance_points
                      - research_penalty - access_penalty))
    missing_groups = [
        "/".join(group)
        for group, matched in zip(demand.coverage_groups, group_matches) if not matched
    ]
    return {
        "source_id": source.source_id, "country": source.country_code,
        "source_type": source.source_type,
        "score": score, "declared_source_freshness": source.freshness,
        "required_field_groups_matched": sum(group_matches),
        "required_field_groups_total": len(group_matches),
        "relevant_roles": observed_roles, "missing_field_groups": missing_groups,
        "registry_state": source.production_status,
        "actual_recent_records_verified": False,
        "source_rights_independently_verified": False,
        "access_budget_approved": False if access_requires_budget else None,
        "privacy_field_scope_needs_review": bool(roles.intersection(
            {"contact", "officer", "director", "phone", "email"})),
        "declared_provenance_strength_not_independent_proof": source.provenance_strength,
        "raw_data_distribution_authorized": False,
        "product_buyer_verified": False,
    }


def _bounded_json(root: Path, name: str, *, max_bytes: int = MAX_RECEIPT) -> Mapping[str, Any] | None:
    path = root / name
    try:
        if (path.is_symlink() or not path.is_file()
                or not 0 < path.stat().st_size <= max_bytes):
            return None
        obj = json.loads(path.read_text("utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError, TypeError, UnicodeError):
        return None


def _fresh(ts: Any, now: datetime, *, days: int = 7) -> bool:
    if not isinstance(ts, str):
        return False
    try:
        stamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (stamp.utcoffset() is not None and
                timedelta(0) <= now - stamp.astimezone(timezone.utc) <= timedelta(days=days))
    except (ValueError, OverflowError):
        return False


def evidence_by_family(root: Path, *, now: datetime,
                       mining: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Read actual canonical owner receipts, never infer missing rows from counts."""
    receipts: dict[str, Any] = {}
    permit = (mining or {}).get("recent_official_permit_mining")
    if isinstance(permit, Mapping):
        n = permit.get("valid_recent_issue_dates_in_sample")
        receipts["property_development"] = {
            "source": "us_nyc_dob_now_approved_permits", "country": "US",
            "usable_dated_samples": n if type(n) is int and 0 <= n <= 40 else None,
            "source_sample_only": True,
            "source_receipt_verified": permit.get("status") == "CURRENT_DATED_ISSUANCE_SAMPLE_MINED",
            "buyer_verified": False, "rights_cleared": False,
        }
    procurement = _bounded_json(root, "runtime/acquisition_research/official_procurement_requirements_latest.json")
    if (procurement and procurement.get("schema_version") == "empire.acquisition_official_procurement_review.v1"
            and procurement.get("mode") == "OBSERVE" and procurement.get("crm_writes") is False
            and procurement.get("outbound_authorized") is False):
        count = procurement.get("open_service_requirements_identified")
        inspected = procurement.get("releases_inspected")
        receipts["public_procurement"] = {
            "source": "canonical_procurement_owner", "country": "GB",
            "source_receipt_verified": _fresh(procurement.get("observed_at"), now),
            "potential_requirements_observed": count if type(count) is int and 0 <= count <= 1000 else None,
            "official_releases_examined": inspected if type(inspected) is int and 0 <= inspected <= 10000 else None,
            "qualified_buyer_count": 0, "rights_cleared": False,
            "buyer_verified": False, "not_a_customer_enquiry": True,
        }
    companies = _bounded_json(root, "runtime/buyer_acquisition/official_company_registry_evidence_latest.json")
    if (companies and companies.get("schema_version") == "empire.tam.official_company_registry_evidence.v1"
            and companies.get("mode") == "OBSERVE" and companies.get("database_write_performed") is False
            and companies.get("outbound_authorized") is False):
        records = companies.get("records")
        receipts["company_change"] = {
            "source": "existing_company_registry_evidence", "country": "GB",
            "source_receipt_verified": _fresh(companies.get("generated_at"), now),
            "historical_research_records": len(records) if isinstance(records, list) and len(records) <= 100 else None,
            "current_changes_verified": None, "buyer_verified": False,
            "rights_cleared": False,
        }
    return receipts


def acquisition_sequence(
    root: Path, *, index: int, now: datetime,
    mining: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build buyer-problem-first decisions for ALL registered markets.

    Sequence is deterministic, source-specific, evidence-limited, and bounded
    to internal work. It does not fetch beyond the existing owned adapters.
    """
    if (type(index) is not int or not 0 <= index < len(DISCOVERY_LANES)
            or now.utcoffset() is None):
        raise ValueError("UNTRUSTED_BROKERAGE_SEQUENCE_INPUT")
    now = now.astimezone(timezone.utc)
    receipts = evidence_by_family(root, now=now, mining=mining)
    all_countries = countries()
    matrix = {}
    coverage_combinations = 0
    for d in DEMANDS:
        for country in all_countries:
            if d.target_country_codes and country not in d.target_country_codes:
                continue
            possibilities = [
                candidate for item in SOURCES.values()
                if item.country_code == country
                if (candidate := _score(item, d)) is not None
            ]
            possibilities.sort(key=lambda item: (-item["score"], item["source_id"]))
            best = possibilities[:3]
            matrix.setdefault(d.key, {})[country] = {
                "sources": len(possibilities),
                "best": best[0]["source_id"] if best else None,
                "score": best[0]["score"] if best else 0,
            }
            coverage_combinations += 1

    country, product, query = DISCOVERY_LANES[index]
    products_available = {item["key"] for item in data_product_catalog()}
    contract = CONTRACT_ROUTES.get(product)
    if contract not in products_available:
        raise ValueError("CANONICAL_DATA_PRODUCT_CONTRACT_MISSING")
    d = next(x for x in DEMANDS if x.key == product)
    ranked = [
        result for source in SOURCES.values()
        if source.country_code == country
        if (result := _score(source, d)) is not None
    ]
    ranked.sort(key=lambda item: (-item["score"], item["source_id"]))
    lead = ranked[0] if ranked else None
    gaps = list(lead["missing_field_groups"]) if lead else [
        "/".join(group) for group in d.coverage_groups
    ]
    r = receipts.get(product)
    if isinstance(r, Mapping) and r.get("country") != country:
        r = None
    sample_verified = bool(r and r.get("source_receipt_verified") is True)
    if product == "property_development" and country == "US":
        sample_verified = sample_verified and type(r.get("usable_dated_samples")) is int and r["usable_dated_samples"] > 0
    if product == "public_procurement":
        sample_verified = sample_verified and type(r.get("potential_requirements_observed")) is int

    status_by_step = {
        "TARGET_REQUIREMENT": "COMPLETE_INTERNAL_HYPOTHESIS",
        "SOURCE_DISCOVERY": "REGISTERED_SOURCE_FOUND" if lead else "SOURCE_SEARCH_REQUIRED",
        "SCHEMA_PROVENANCE": "REVIEW_REQUIRED",
        "ORIGINAL_RECORD_MINING": "RECEIPTED_INTERNAL_SAMPLE" if sample_verified else "RELEVANT_SAMPLE_NOT_VERIFIED",
        "IDENTITY_NORMALISATION": "NOT_VERIFIED",
        "INDEPENDENT_CROSS_CHECK": "NOT_VERIFIED",
        "USEFULNESS_REVIEW": "HEURISTIC_RANKING_ONLY",
        "RIGHTS_AND_PRIVACY": "SOURCE_FIELD_LICENCE_REVIEW_REQUIRED",
        "ORIGINAL_PRODUCT_PACKAGING": "UNRELEASED_INTERNAL_RESEARCH",
        "BUYER_VALIDATION": "NO_CUSTOMER_REQUIREMENT_VERIFIED",
        "LICENSED_FULFILMENT": "NOT_AUTHORIZED",
    }
    first_missing = ("SCHEMA_PROVENANCE" if lead and not sample_verified
                     else "IDENTITY_NORMALISATION" if sample_verified
                     else "SOURCE_DISCOVERY")
    # Materialized internal original analysis: use true source counts, but
    # do not convert public market observations into buyer or sale claims.
    internal_brief = None
    if sample_verified and isinstance(r, Mapping):
        if product == "public_procurement":
            inspected = r.get("official_releases_examined")
            requirements = r.get("potential_requirements_observed")
            if type(inspected) is int and inspected > 0 and type(requirements) is int:
                internal_brief = {
                    "market": country, "product_contract": contract,
                    "original_analyst_observation":
                        f"Official procurement owner inspected {inspected} releases and "
                        f"identified {requirements} potentially relevant service requirements.",
                    "examined_release_count": inspected,
                    "potential_requirement_count": requirements,
                    "scope": "OBSERVED_SOURCE_SAMPLE_NOT_EXHAUSTIVE",
                    "supplier_requirements_independently_validated": False,
                }
        elif product == "property_development":
            valid = r.get("usable_dated_samples")
            if type(valid) is int and valid > 0:
                internal_brief = {
                    "market": country, "product_contract": contract,
                    "original_analyst_observation":
                        f"Observed {valid} date-validated NYC DOB NOW issued permit records "
                        "in a bounded sampled window; citywide totals and construction starts unknown.",
                    "recent_permit_records_in_sample": valid,
                    "scope": "BOUNDED_NOT_A_POPULATION_COUNT",
                    "verified_construction_starts": None,
                }
        if internal_brief is not None:
            internal_brief.update({
                "internal_analyst_draft_only": True,
                "customer_fulfilment_authorized": False,
                "source_specific_commercial_rights_cleared": False,
                "buyer_intent_proven": False,
            })
            status_by_step["ORIGINAL_PRODUCT_PACKAGING"] = "INTERNAL_ORIGINAL_ANALYSIS_PREPARED_NOT_SELLABLE"
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "evaluated_at": now.isoformat(),
        "country_count": len(all_countries),
        "countries": list(all_countries),
        "product_problem_count": len(DEMANDS),
        "source_contract_count": len(SOURCES),
        "country_product_coverage_rows": matrix,
        "country_product_combinations_evaluated": coverage_combinations,
        "evidence_by_family": receipts,
        "rotation_index": index, "rotation_length": len(DISCOVERY_LANES),
        "active_lane": {
            "country": country, "sector": d.sector, "product": d.key,
            "buyer_problem": d.buyer_problem, "proposed_output": d.proposed_output,
            "canonical_existing_product_contract": contract,
            "customer_product_entitlement_verified": False,
            "required_field_groups": [list(g) for g in d.coverage_groups],
            "data_acquisition_query": query,
            "registered_source_candidates": ranked[:5],
            "best_source_heuristic_score": lead["score"] if lead else 0,
            "missing_field_groups": gaps,
            "source_sample_usable_for_internal_analysis": sample_verified,
            "source_sample_evidence": dict(r) if r else None,
            "internal_original_analysis_draft": internal_brief,
            "sequence": [{"step": stage, "state": status_by_step[stage]}
                         for stage in STAGES],
            "next_evidence_action": first_missing,
        },
        "buyer_demands_are_hypotheses": True,
        "heuristics_do_not_prove_commercial_demand": True,
        "buyer_records_verified": None, "revenue_verified": None,
        "licence_cleared": False, "customer_data_delivery_enabled": False,
        "external_actions": 0, "outbound_sent": False,
        "execution_authority": "none",
    }
