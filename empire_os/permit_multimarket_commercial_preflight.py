"""Research-only official rights + data-quality + company-fit audit.

One EmpireOS original Permit Intelligence. Publisher dataset descriptors and
first-party business sites only. No source records queried, buyer emails,
commercial reuse permission, entitlement, issued permit, or buyer intent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping
from empire_os.permit_multimarket_registry import MARKETS, digest, market_plan

SCHEMA = "empire.permit_data.multimarket_commercial_preflight.v1"

# Official publisher pages inspected October 24, 2026. Do not treat metadata
# timestamps as live, independently validated row-level freshness.
AUDITS = {
    "chicago": {
        "license_state": "TERMS_OF_USE_REVIEW_REQUIRED",
        "license_evidence": "https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu/about",
        "last_listed_update": "2026-10-23",
        "field_candidates": ("permit_", "permit_status"),
        "quality_risks": ("Issued-permit coverage does not prove work remains open", "Status field not populated for every permit type", "Contractor identities may be present; do not ingest those fields"),
        "next_review": "Obtain binding Chicago permit-data terms and verify ID/status dictionary",
    },
    "philadelphia": {
        "license_state": "COMMERCIAL_PERMISSION_HOLD",
        "license_evidence": "https://www.phila.gov/terms-of-use/",
        "last_listed_update": None,
        "field_candidates": (),
        "quality_risks": ("Commercial website reuse restrictions require dataset-specific legal review", "CARTO permit and contractor datasets are distinct", "Permit application is not a tender or available contract"),
        "next_review": "Written city/dataset licence clarification before paid data reuse; independent CARTO column audit",
    },
    "san_francisco": {
        "license_state": "OPEN_DATA_TERMS_REVIEW_REQUIRED",
        "license_evidence": "https://data.sf.gov/terms-of-use",
        "last_listed_update": "2026-10-23",
        "field_candidates": ("permit_number", "data_as_of", "data_loaded_at"),
        "quality_risks": ("Multiple address rows per permit; deduplication required", "After 2024-12-10 only new/updated rows are published", "Use maximum data_as_of/data_loaded_at for source freshness rather than page date"),
        "next_review": "Accept terms, verify primary-address deduplicated view and current row-level freshness",
    },
    "seattle": {
        "license_state": "PUBLIC_DOMAIN_LABEL_NOT_DISTRIBUTION_RELEASE",
        "license_evidence": "https://data.seattle.gov/Built-Environment/Building-Permits/76t5-zqzr/about",
        "last_listed_update": "2026-10-22",
        "field_candidates": ("permitnum", "applieddate", "issueddate", "statuscurrent"),
        "quality_risks": ("Description may change before issuance", "Application without issueddate generally still under review", "Publisher page timestamp alone cannot validate freshness or eligibility"),
        "next_review": "Verify exact source fields and quality on a rights-cleared bounded pilot sample",
    },
    "austin": {
        "license_state": "PUBLIC_DOMAIN_LABEL_NOT_DISTRIBUTION_RELEASE",
        "license_evidence": "https://data.austintexas.gov/Building-and-Development/Issued-Construction-Permits/3syk-w9eu/about_data",
        "last_listed_update": "2026-10-11",
        "field_candidates": ("permit_number", "applieddate", "issue_date"),
        "quality_risks": ("Issued-permit dataset cannot support pre-issuance triggers", "Official disclaimer warns contents may differ from department records", "Metadata update older than others; no new rows sampled"),
        "next_review": "Verify field types, source freshness, notices and commercial scope before access",
    },
}

# These are researched companies with first-party site evidence, not leads.
# No recipient emails or personal data. Public site visit != buyer intent.
COMPANIES = (
    ("seattle", "AAA Fire Protection", "fire_protection", "https://www.aaafire.com/"),
    ("seattle", "Columbia Fire", "fire_protection", "https://www.columbiafire.net/about-us/"),
    ("san_francisco", "AR&B Mechanical", "hvac_fire_protection", "https://www.arbmechanical.com/"),
    ("san_francisco", "Cooper & Hawkins", "hvac", "https://www.cooperhawkins.com/"),
    ("austin", "Kidd Roofing", "commercial_roofing", "https://www.kiddroof.com/austin-roofing/commercial/"),
    ("austin", "Texas Fifth Wall Roofing Systems", "commercial_roofing", "https://fifthwallroofing.com/"),
    ("chicago", "Funderburk Roofing", "commercial_roofing", "https://www.funderburkroofing.com/"),
    ("chicago", "Stergo Roofing", "commercial_roofing", "https://stergoroofing.com/"),
    ("philadelphia", "Independence Fire Sprinkler Company", "fire_protection", "https://indpfire.com/about/"),
    ("philadelphia", "TriState HVAC", "commercial_hvac", "https://tristatehvac.com/"),
)
PRIORITY = ("seattle", "san_francisco", "austin", "chicago", "philadelphia")


def build_preflight(*, at: datetime) -> dict:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("multimarket_preflight_requires_aware_clock")
    registry = market_plan(at=at)
    if set(AUDITS) != set(MARKETS) - {"nyc"}:
        raise ValueError("national_source_audit_missing_market")
    markets = []
    for rank, key in enumerate(PRIORITY, start=1):
        audit = AUDITS[key]
        source = MARKETS[key]
        if (source["mode"] != "SOURCE_DISCOVERY_ONLY"
            or not audit["license_evidence"].startswith("https://")
            or len(audit["quality_risks"]) < 3):
            raise ValueError("unsafe_national_market_evidence")
        companies = [company for company in COMPANIES if company[0] == key]
        if len(companies) != 2:
            raise ValueError("national_research_candidate_coverage_not_complete")
        markets.append({
            "market_id": key, "market": source["name"], "priority_for_research": rank,
            "source_dataset_ids": list(source["datasets"]),
            "source_rights_state": audit["license_state"],
            "source_rights_evidence_url": audit["license_evidence"],
            "publisher_last_listed_update_date": audit["last_listed_update"],
            "source_dictionary_field_candidates_not_runtime_approved": list(audit["field_candidates"]),
            "data_quality_risks": list(audit["quality_risks"]),
            "next_approval_step": audit["next_review"],
            "source_terms_allow_customer_redistribution": False,
            "live_source_row_freshness_verified": False,
            "historical_samples_rechecked": 0,
            "official_dataset_api_requests_this_report": 0,
            "commercial_offer_release": "HOLD_SOURCE_RIGHTS_SCHEMA_FRESHNESS_BUYER_AUTHORITY",
            "qualified_buyers": 0,
            "research_companies": [{
                "company": name, "service_fit_for_hypothesis": service,
                "first_party_evidence_url": url,
                "company_research_status": "FIRST_PARTY_SERVICE_FIT_NOT_CONTACTED",
                "first_party_email_verified": False,
                "exact_recipient_suppression_cleared": False,
                "authentic_buying_signal": False,
                "outreach_authorized": False,
                "proposed_value_first_question": (
                    "Which permit-stage checks take your team the most time, "
                    "and how do you distinguish an application from issued work?"
                ),
            } for _, name, service, url in companies],
        })
    result = {
        "schema_version": SCHEMA,
        "original_stack": "ONE_EMPIREOS_PERMIT_INTELLIGENCE",
        "reviewed_at_utc": at.astimezone(timezone.utc).isoformat(),
        "original_national_registry_sha256": registry["private_market_registry_sha256"],
        "original_nyc_five_job_pilot_unchanged": True,
        "new_cities_researched": 5,
        "company_research_candidates": len(COMPANIES),
        "cities_live": 0,
        "company_contacts_sent": 0,
        "source_row_http_requests": 0,
        "customer_source_payloads_exported": 0,
        "buyer_signals_verified": 0,
        "paid_pilots": 0,
        "realised_revenue_usd": "0.00",
        "empiredb_writes": 0,
        "smart_crm_writes": 0,
        "outbound_sent": False,
        "execution_authority": "none",
        "markets": markets,
    }
    result["audit_sha256"] = digest(result)
    return result


def validate_preflight(report: Mapping) -> None:
    if (not isinstance(report, Mapping)
        or report.get("schema_version") != SCHEMA
        or report.get("original_stack") != "ONE_EMPIREOS_PERMIT_INTELLIGENCE"
        or report.get("audit_sha256") != digest({k:v for k,v in report.items() if k != "audit_sha256"})
        or report.get("new_cities_researched") != 5
        or report.get("company_research_candidates") != 10
        or report.get("cities_live") != 0
        or report.get("source_row_http_requests") != 0
        or report.get("outbound_sent") is not False
        or report.get("company_contacts_sent") != 0
        or report.get("buyer_signals_verified") != 0
        or report.get("paid_pilots") != 0
        or report.get("realised_revenue_usd") != "0.00"
        or report.get("empiredb_writes") != 0
        or report.get("smart_crm_writes") != 0
        or report.get("execution_authority") != "none"):
        raise ValueError("untrusted_multimarket_commercial_preflight")
    rows = report.get("markets")
    if not isinstance(rows, list) or len(rows) != 5:
        raise ValueError("invalid_multimarket_commercial_rows")
    if [x.get("market_id") for x in rows] != list(PRIORITY):
        raise ValueError("multimarket_scope_or_priority_changed")
    for row in rows:
        if (row.get("source_rights_state") != AUDITS[row["market_id"]]["license_state"]
            or row.get("source_terms_allow_customer_redistribution") is not False
            or row.get("live_source_row_freshness_verified") is not False
            or row.get("historical_samples_rechecked") != 0
            or row.get("official_dataset_api_requests_this_report") != 0
            or row.get("qualified_buyers") != 0
            or row.get("commercial_offer_release") != "HOLD_SOURCE_RIGHTS_SCHEMA_FRESHNESS_BUYER_AUTHORITY"
            or len(row.get("research_companies", [])) != 2
            or any(company.get("outreach_authorized") is not False
                   or company.get("authentic_buying_signal") is not False
                   or company.get("exact_recipient_suppression_cleared") is not False
                   for company in row["research_companies"])):
            raise ValueError("untrusted_source_rights_or_buyer_research")


def render_preflight(report: Mapping) -> str:
    validate_preflight(report)
    lines = [
        "# EmpireOS national Permit Intelligence — source rights and contractor research",
        "",
        "**FOUNDER PRIVATE. No publisher sample extracted, customer consent, commercial rights approval or sends.**",
        "",
        "| City | Source rights review | Source quality | Research candidates |",
        "|---|---|---|---|",
    ]
    for row in report["markets"]:
        lines.append(
            f'| {row["market"]} | {row["source_rights_state"]} | '
            f'{len(row["data_quality_risks"])} known risks; no live sample | '
            f'{len(row["research_companies"])} uncontacted companies |')
    lines += ["", "## Value-first research companies (not qualified buyers)", ""]
    for row in report["markets"]:
        for c in row["research_companies"]:
            lines.append(f'- {row["market"]}: {c["company"]} ({c["service_fit_for_hypothesis"]}) — {c["first_party_evidence_url"]}')
    lines += ["", "## Release constraints",
              "1. No NYC owner authority or source cadence is inherited by another city.",
              "2. Philadelphia website's commercial restrictions demand separate data licence determination; no commercial publication.",
              "3. Seattle and Austin Public Domain labels alone do not approve automated API access, personal-field processing or subscriber delivery.",
              "4. San Francisco requires permit deduplication and update-watermark testing.",
              "5. First-party business service fit never counts as interest; value-first → authentic reply → buyer signal → permission-based CTA.",
              "6. Suppression, exact recipient, founder approval and data rights precede any free sample or outbound.",
              "", "**0 source-row GETs · 0 contacts · 0 qualified buyers · $0 paid revenue.**", ""]
    return "\n".join(lines)
