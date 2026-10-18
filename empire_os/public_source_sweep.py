"""Verified-research source opportunity catalogue; metadata, NOT source data.

Reuses existing Source Intelligence, Sensor Mesh, Quant and Marketing teams.
Registry is immutable in code: no feeds are enabled merely by listing them,
and no licensing rights or buyer interest is inferred.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json

SCHEMA = "empire.public_source_sweep.v1"

# Public official documentation reviewed on 18 Oct 2026; endpoint behavior,
# availability, permissions and freshness must be rechecked before each live
# adapter launch. Existing EmpireOS source routes are always preferred.
# readiness: REUSE_EXISTING | PILOT_READ_ONLY | NEW_ADAPTER_REVIEW |
#   API_KEY_REQUIRED | LIMITED_SOURCE_RIGHTS | NO_ACTIVE_RECORDS |
#   BLOCKED_COMMERCIAL_FREE_TIER.
SOURCES = (
    ("ea_flood_warnings", "UK", "environment.data.gov.uk",
     "https://environment.data.gov.uk/flood-monitoring/doc/reference",
     "PILOT_READ_ONLY", "no_key", "OGL3_ATTRIBUTION", "near_realtime",
     "sensor_mesh", "flood_event", 94, "observed_warning_not_damage_or_buyer"),
    ("uk_contracts_finder", "UK", "contractsfinder.service.gov.uk",
     "https://www.contractsfinder.service.gov.uk/apidocumentation",
     "NEW_ADAPTER_REVIEW", "public_ocds_read", "OGL_VERIFY_RECORD",
     "publication", "business_development", "procurement_notice", 96,
     "public_procurement_not_awarded_order"),
    ("uk_find_a_tender", "UK", "find-tender.service.gov.uk",
     "https://www.find-tender.service.gov.uk/Developer/Documentation",
     "PILOT_READ_ONLY", "public_ocds_read", "OGL3_ATTRIBUTION",
     "publication", "business_development", "procurement_notice", 96,
     "public_ocds_not_authenticated_submission_api"),
    ("us_nws_alerts", "US", "api.weather.gov",
     "https://www.weather.gov/documentation/services-web-api",
     "REUSE_EXISTING", "user_agent", "US_FEDERAL_OPEN_DATA",
     "near_realtime", "sensor_mesh", "public_weather_alert", 93,
     "weather_alert_not_verified_property_damage"),
    ("us_nyc_dobnow", "US", "data.cityofnewyork.us",
     "https://www.nyc.gov/opendata/get-started/user-guides/open-data-apis",
     "REUSE_EXISTING", "socrata_public", "DATASET_TERMS_VERIFY",
     "daily_source", "market_intelligence", "public_permit", 91,
     "source_filing_not_confirmed_buyer"),
    ("us_openfema_disasters", "US", "www.fema.gov",
     "https://www.fema.gov/about/openfema/data-sets",
     "NEW_ADAPTER_REVIEW", "public_api", "FEDERAL_PUBLIC_VERIFY",
     "updates", "sensor_mesh", "disaster_declaration", 90,
     "official_declaration_not_damage_at_individual_address"),
    ("us_usaspending", "US", "api.usaspending.gov",
     "https://api.usaspending.gov/docs/endpoints",
     "NEW_ADAPTER_REVIEW", "no_key", "FEDERAL_PUBLIC_VERIFY",
     "frequent_batches", "market_intelligence", "procurement_award", 88,
     "historical_awards_not_new_contract_demand"),
    ("uk_ea_rainfall", "UK", "environment.data.gov.uk",
     "https://environment.data.gov.uk/flood-monitoring/doc/rainfall",
     "NEW_ADAPTER_REVIEW", "no_key", "OGL3_ATTRIBUTION",
     "frequent_batches", "sensor_mesh", "rainfall_measurement", 87,
     "sensor_reading_not_damage_or_job"),
    ("uk_ofgem_fit", "UK", "www.ofgem.gov.uk",
     "https://www.ofgem.gov.uk/feed-tariffs-fit/contacts-guidance-and-resources/public-reports-and-data-fit/installation-reports",
     "NEW_ADAPTER_REVIEW", "public_files", "PER_FILE_REVIEW",
     "quarterly", "market_intelligence", "solar_installation_baseline", 83,
     "historic_accreditations_not_current_solar_buyer"),
    ("us_census_building_permits", "US", "www.census.gov",
     "https://www.census.gov/construction/bps/index.html",
     "NEW_ADAPTER_REVIEW", "public_download", "US_FEDERAL_OPEN_DATA",
     "monthly", "market_intelligence", "regional_building_trend", 82,
     "aggregate_permits_not_purchaser_identity"),
    ("us_epa_echo", "US", "echo.epa.gov",
     "https://echo.epa.gov/tools/web-services",
     "NEW_ADAPTER_REVIEW", "public_api", "FEDERAL_PUBLIC_VERIFY",
     "varying_updates", "market_intelligence", "facility_environment_context", 76,
     "facility_compliance_not_purchase_intent"),
    ("uk_ons", "UK", "api.beta.ons.gov.uk",
     "https://developer.ons.gov.uk/",
     "NEW_ADAPTER_REVIEW", "no_key", "DATASET_TERMS_VERIFY",
     "periodic", "market_intelligence", "regional_macro_indicators", 75,
     "aggregate_statistics_not_real_buyer"),
    ("us_eia_energy", "US", "api.eia.gov",
     "https://www.eia.gov/opendata/documentation.php",
     "API_KEY_REQUIRED", "free_key_required", "US_FEDERAL_OPEN_DATA",
     "periodic", "market_intelligence", "regional_energy_market", 78,
     "state_market_stats_not_customer_sales"),
    ("uk_companies_house", "UK", "api.company-information.service.gov.uk",
     "https://developer.company-information.service.gov.uk/get-started",
     "API_KEY_REQUIRED", "free_key_required", "REUSE_AND_PERSONAL_DATA_REVIEW",
     "filings", "market_intelligence", "company_changes", 80,
     "company_filings_not_verifiable_buying_intent"),
    ("uk_epc", "UK", "epc.opendatacommunities.org",
     "https://epc-preview.opendatacommunities.org/docs/api",
     "LIMITED_SOURCE_RIGHTS", "account_and_permissions",
     "PERSONAL_DATA_ADDRESS_LICENCE_REVIEW", "monthly_or_batched",
     "market_intelligence", "energy_certificate", 62,
     "no_household_contact_or_address_extraction"),
    ("uk_planning_application_api", "UK", "www.planning.data.gov.uk",
     "https://www.planning.data.gov.uk/dataset/planning-application",
     "NO_ACTIVE_RECORDS", "public_beta", "OGL3_ATTRIBUTION",
     "no_current_providers", "market_intelligence", "planning_application", 35,
     "official_catalogue_zero_records_at_sweep"),
    ("open_meteo_free_tier", "GLOBAL", "open-meteo.com",
     "https://open-meteo.com/en/terms",
     "BLOCKED_COMMERCIAL_FREE_TIER", "free_hosted_noncommercial",
     "COMMERCIAL_HOSTED_SUBSCRIPTION_REQUIRED", "forecasts",
     "sensor_mesh", "third_party_weather", 30,
     "do_not_use_free_hosted_tier_for_commercial_empireos"),
    ("empire_gsc", "UK_US", "google.com",
     "https://developers.google.com/webmaster-tools/v1/searchanalytics/query",
     "REUSE_EXISTING", "connected_scoped_property",
     "FIRST_PARTY_PROPERTY_ACCESS", "daily",
     "marketing_growth", "owned_search_performance", 89,
     "query_samples_not_complete_market_demand"),
    ("empire_commoncrawl", "GLOBAL", "data.commoncrawl.org",
     "https://commoncrawl.org/get-started",
     "REUSE_EXISTING", "existing_free_graph_review",
     "CC_SOURCE_REUSE_VERIFY", "historical",
     "marketing_growth", "historical_domain_graph", 64,
     "historical_links_not_live_links_or_sales"),
)

NAMES = (
    "source_key", "region", "host", "official_documentation", "readiness",
    "auth", "rights", "cadence", "department", "signal_class",
    "strategic_priority", "truth_limit",
)
VALID_STATES = {
    "REUSE_EXISTING", "PILOT_READ_ONLY", "NEW_ADAPTER_REVIEW",
    "API_KEY_REQUIRED", "LIMITED_SOURCE_RIGHTS", "NO_ACTIVE_RECORDS",
    "BLOCKED_COMMERCIAL_FREE_TIER",
}


def review_public_source_sweep(*, as_of: datetime | None = None) -> dict[str, Any]:
    at = as_of or datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("timezone-aware review timestamp required")
    rows = [dict(zip(NAMES, original)) for original in SOURCES]
    if len({row["source_key"] for row in rows}) != len(rows):
        raise ValueError("duplicate source")
    for row in rows:
        if (row["readiness"] not in VALID_STATES
                or not row["official_documentation"].startswith("https://")
                or not 0 <= row["strategic_priority"] <= 100):
            raise ValueError("source metadata not trusted")
        row["paid_api_invoked"] = False
        row["active_ingestion_enabled_by_catalogue"] = False
        row["buyer_intent_verified"] = False
        row["contact_extraction_authorized"] = False
        row["revenue_verified"] = False
        row["source_provenance_requires_runtime_verification"] = True
    rows.sort(key=lambda row: (-row["strategic_priority"], row["source_key"]))
    states = Counter(row["readiness"] for row in rows)
    ref_digest = sha256(json.dumps(SOURCES, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": at.astimezone(timezone.utc).isoformat(),
        "catalogue_research_as_of": "2026-10-18",
        "source_count": len(rows),
        "by_readiness": dict(sorted(states.items())),
        "sources": rows,
        "metadata_fingerprint": ref_digest,
        "top_new_public_source_choices": [
            item["source_key"] for item in rows
            if item["readiness"] in ("PILOT_READ_ONLY", "NEW_ADAPTER_REVIEW")
        ][:7],
        "all_original_sources_preserved": True,
        "new_service_or_database_created": False,
        "source_polling_started": False,
        "paid_api_invoked": False,
        "outbound_authorized": False,
        "revenue_verified": False,
        "execution_authority": "none",
    }


def enqueue_deep_source_reviews(
    repo_root: str,
    catalogue: dict[str, Any],
    *,
    allow_noncanonical_test: bool = False,
) -> dict[str, Any]:
    """Route exactly TWO bounded source-readiness checks to ASTRA's queue.

    Merely queues internal analysis of published official source metadata;
    never asks the workers to crawl sites, ingest personal details or send
    procurement enquiries. No new scheduler, independent workforce or DB.
    """
    from pathlib import Path
    from empire_os.department_work_queue import DepartmentWorkQueue

    root = Path(repo_root).resolve()
    if root != Path("/srv/empire_os") and not allow_noncanonical_test:
        raise PermissionError("canonical department queue required")
    reference = review_public_source_sweep()
    if (not isinstance(catalogue, dict)
            or catalogue.get("schema_version") != SCHEMA
            or catalogue.get("metadata_fingerprint") != reference["metadata_fingerprint"]
            or catalogue.get("sources") != reference["sources"]
            or catalogue.get("source_count") != reference["source_count"]
            or catalogue.get("source_polling_started") is not False
            or catalogue.get("execution_authority") != "none"):
        raise ValueError("untrusted or changed public-source catalogue")
    keys = {item["source_key"]: item for item in reference["sources"]}
    work = (
        ("uk_procurement",
         "business_development",
         "review_official_uk_procurement_public_ocds_for_eligible_sector_demand",
         ("uk_find_a_tender", "uk_contracts_finder"), 94),
        ("uk_environmental_events",
         "market_intelligence",
         "review_ea_flood_source_event_quality_for_sensor_mesh",
         ("ea_flood_warnings", "uk_ea_rainfall"), 87),
    )
    # Validate every requested source before creating queue directories.
    for _, _, _, sources, _ in work:
        if any(source not in keys or keys[source]["readiness"] not in (
            "PILOT_READ_ONLY", "NEW_ADAPTER_REVIEW"
        ) for source in sources):
            raise ValueError("source readiness no longer eligible")
    queue = DepartmentWorkQueue(root)
    output = []
    for lane, owner, action, source_keys, priority in work:
        material = reference["metadata_fingerprint"] + "|" + "|".join(source_keys)
        digest = sha256(material.encode()).hexdigest()
        step = {
            "step_id": "source_" + lane + "_" + digest[:16],
            "goal_key": "assess_official_source_mining_reuse",
            "department_keys": [owner],
            "target_component": "existing_source_intelligence_and_sensor_mesh",
            "action": action,
            "authority": "observe",
            "evidence_refs": [keys[key]["official_documentation"]
                              for key in source_keys],
            "rationale": "Verify source semantics, coverage and rights before considering canonical ingestion",
            "success_condition": "Internal source readiness/evidence review; no buyer contact, send, revenue, model inference or integration activation",
            "intelligence_request": {
                "official_source_deep_sweep": {
                    "source_keys": list(source_keys),
                    "source_inventory_fingerprint": digest,
                    "public_metadata_only": True,
                    "commercial_source_rights_must_be_verified": True,
                    "public_event_or_tender_not_sales_outcome": True,
                    "explicit_ingest_authorization_required": True,
                },
                "budget": {
                    "requested_model_tokens": 0,
                    "requested_external_cost_cents": 0,
                },
            },
        }
        item, created = queue.enqueue_step(
            plan_id="source_deep_sweep_wave2_v1",
            step=step,
            priority=priority,
        )
        output.append({
            "source_lane": lane, "department": owner, "work_id": item.id,
            "delivery": "QUEUED" if created else "ALREADY_QUEUED",
        })
    return {
        "schema_version": "empire.public_source_sweep.department_review.v1",
        "mode": "OBSERVE",
        "new_review_tasks": sum(x["delivery"] == "QUEUED" for x in output),
        "duplicate_review_tasks": sum(x["delivery"] == "ALREADY_QUEUED" for x in output),
        "reviews": output,
        "external_source_polling_started": False,
        "paid_provider_invoked": False,
        "customer_contact_retrieved": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
