"""Explicit official-source discovery contracts for Empire Lead Intelligence.

Research metadata, NOT automatic ingestion/purchase/outbound authority.
Business-only fields, country/industry separation, source-specific rights
and exact access modality. Never turn an agency's lookup into a bulk scraper.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class VerticalSource:
    source_id: str
    sectors: tuple[str, ...]
    country: str
    authority: str
    landing_page: str
    access: str
    activation: str
    rights_note: str
    scope_note: str

SOURCES: tuple[VerticalSource, ...] = (
    VerticalSource(
        "us_cslb_official_contractor_csv",
        ("roofing", "hvac", "solar"), "US",
        "California Contractors State License Board",
        "https://www.cslb.ca.gov/Onlineservices/DataPortal/",
        "official_user_downloaded_csv",
        "OFFLINE_FILE_IMPORT_READY_NOT_ACTIVATED",
        "Free disclosed contractor licence data; review actual download terms, no emails supplied",
        "CA trade class C-39 roofing, C-20 HVAC, C-46 solar; company licences only; not buyer intent",
    ),
    VerticalSource(
        "us_nyc_dcwp_home_improvement_companies",
        ("roofing", "hvac", "solar"), "US",
        "New York City Department of Consumer and Worker Protection",
        "https://data.cityofnewyork.us/Business/Active-Home-Improvement-Contractor-Licenses/acd4-wkax",
        "bounded_official_socrata_query",
        "BOUNDED_MANUAL_PILOT_READY",
        "NYC Open Data public API, current dataset may contain natural persons; company-only data filter required",
        "General home improvement contractor licence only; not verified as specific roofing/HVAC/solar trade",
    ),
    VerticalSource(
        "us_cms_nppes_dental_npi2",
        ("dental",), "US",
        "US Centers for Medicare & Medicaid Services",
        "https://npiregistry.cms.hhs.gov/",
        "bounded_public_api_organization_query",
        "BOUNDED_MANUAL_PILOT_READY",
        "CMS limits registry query rates; bulk collection must use official data dissemination files",
        "NPI-2 organization only; NPI listing is not licensure or verified buyer status; exclude individuals/patients",
    ),
    VerticalSource(
        "us_nyserda_solar_participants",
        ("solar",), "US", "NYSERDA",
        "https://www.nyserda.ny.gov/All-Programs/NY-Sun/On-site-Solar/Homes/Choosing-a-Contractor/Residential-Installers",
        "participating_contractor_directory",
        "CONTRACT_REVIEW_ONLY",
        "Directory is official but no verified bulk API or harvesting permission in this review",
        "NY State solar participant company verification, not purchase intent",
    ),
    VerticalSource(
        "gb_sra_firm_api",
        ("legal", "mass_torts"), "GB",
        "Solicitors Regulation Authority",
        "https://www.sra.org.uk/datasharing",
        "registered_api_key",
        "HOLD_API_KEY_REQUIRED",
        "Law firm API has attribution and API product subscription requirements",
        "Authorised firms only, not individual solicitors, claimants or claim handlers; practice area unproven until data fetched",
    ),
    VerticalSource(
        "gb_fca_insurance_firm_api",
        ("insurance",), "GB",
        "Financial Conduct Authority",
        "https://www.fca.org.uk/firms/financial-services-register",
        "registered_api_key_single_entity_lookup",
        "HOLD_API_KEY_REQUIRED",
        "Free developer API requires registration; single-entity lookup, not bulk; extracts separately paid",
        "Firm regulatory identity check, not insurance policyholders, individual agents or verified buying capacity",
    ),
    VerticalSource(
        "us_naic_insurance_company_search",
        ("insurance",), "US",
        "National Association of Insurance Commissioners",
        "https://content.naic.org/cis_consumer_information.htm",
        "individual_company_lookup",
        "MANUAL_FIRM_VERIFICATION_ONLY",
        "No approved company bulk ingestion endpoint has been established",
        "US carrier legal-entity verification and state licence cross-check; no insured or claims data",
    ),
    VerticalSource(
        "us_state_bar_firm_registry",
        ("legal", "mass_torts"), "US",
        "Individual US State Bar and attorney regulators",
        "https://www.americanbar.org/groups/legal_services/flh-home/flh-bar-directories-and-lawyer-finders/",
        "state_specific_license_lookup",
        "MANUAL_FIRM_VERIFICATION_ONLY",
        "Licensing and bulk rights vary by US jurisdiction; no nationwide firm API assumed",
        "Firm records only; attorney/person registry not a mass-tort claimant discovery source",
    ),
)

BY_ID = {s.source_id: s for s in SOURCES}

def assess_source_access(source_id: str, *, api_key_present: bool = False,
                         approved_local_file: bool = False) -> dict:
    source = BY_ID.get(source_id)
    if source is None:
        raise ValueError("unknown_official_source")
    if source.access == "registered_api_key" or source.access == "registered_api_key_single_entity_lookup":
        state = "CREDENTIAL_PRESENT_FURTHER_RIGHTS_REVIEW" if api_key_present else "HOLD_API_KEY_REQUIRED"
    elif source.access == "official_user_downloaded_csv":
        state = "OFFLINE_FILE_PARSE_READY" if approved_local_file else "HOLD_LOCAL_DATASET_REQUIRED"
    else:
        state = source.activation
    return {
        **asdict(source),
        "state": state,
        "source_records_observed": 0,
        "canonical_leads_verified": 0,
        "buyer_capacity_verified": False,
        "outbound_authorized": False,
        "source_automatic_bulk_fetch_authorized": False,
        "canonical_empiredb_writes": False,
    }
