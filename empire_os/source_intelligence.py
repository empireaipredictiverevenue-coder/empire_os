"""Country/niche Source Intelligence OS.

Descriptive and fail-closed. This module selects and scores public/official
acquisition sources; it does not crawl, send outreach, accept terms, move funds,
or recognise revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourceContract:
    source_id: str
    authority: str
    country_code: str
    source_type: str
    access_method: str
    url: str
    niches: tuple[str, ...]
    roles: tuple[str, ...]
    freshness: str
    licence: str
    production_status: str
    provenance_strength: int
    raw_resale_allowed: bool
    pii_class: str = "business_public"
    allowed_uses: tuple[str, ...] = ("internal_acquisition", "entity_resolution")
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CountrySourcePack:
    country_code: str
    identity_sources: tuple[str, ...]
    niche_sources: dict[str, tuple[str, ...]]
    signal_sources: dict[str, tuple[str, ...]]
    jurisdiction_state: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _source(
    source_id: str,
    authority: str,
    country_code: str,
    source_type: str,
    access_method: str,
    url: str,
    niches: tuple[str, ...],
    roles: tuple[str, ...],
    freshness: str,
    licence: str,
    production_status: str = "verified",
    provenance_strength: int = 100,
    raw_resale_allowed: bool = False,
    pii_class: str = "business_public",
    allowed_uses: tuple[str, ...] = ("internal_acquisition", "entity_resolution"),
    notes: str = "",
) -> SourceContract:
    return SourceContract(
        source_id, authority, country_code, source_type, access_method, url,
        niches, roles, freshness, licence, production_status,
        provenance_strength, raw_resale_allowed, pii_class, allowed_uses, notes,
    )


SOURCES: dict[str, SourceContract] = {
    "gb_companies_house": _source(
        "gb_companies_house", "Companies House", "GB", "official_registry", "api",
        "https://api.company-information.service.gov.uk/", ("all",),
        ("identity", "officer", "company_status", "registered_office"),
        "near_real_time", "official_public_api",
    ),
    "gb_recc_solar": _source(
        "gb_recc_solar", "Renewable Energy Consumer Code", "GB",
        "certified_trade_directory", "html_directory",
        "https://www.recc.org.uk/scheme/members",
        ("solar", "battery_storage", "heat_pump"),
        ("identity", "certification", "territory", "contact"),
        "weekly", "public_directory_no_raw_resale",
        provenance_strength=95,
        notes="Internal acquisition/provenance use; do not redistribute raw directory data.",
    ),
    "gb_mcs": _source(
        "gb_mcs", "MCS", "GB", "certified_trade_directory", "public_search",
        "https://mcscertified.com/find-an-installer/",
        ("solar", "battery_storage", "heat_pump"),
        ("certification", "installer", "technology", "territory"),
        "current", "official_public_directory",
    ),
    "gb_trustmark": _source(
        "gb_trustmark", "TrustMark", "GB", "government_endorsed_directory", "public_search",
        "https://www.trustmark.org.uk/homeowner/find-a-tradesperson",
        ("solar", "roofing", "hvac", "electrical", "property"),
        ("identity", "trade", "quality", "territory"),
        "current", "public_directory_terms_apply", provenance_strength=90,
    ),
    "gb_planning_data": _source(
        "gb_planning_data", "UK Government Planning Data", "GB",
        "official_planning_data", "api_bulk",
        "https://www.planning.data.gov.uk/docs",
        ("property", "permits", "solar", "roofing"),
        ("planning", "property", "geospatial", "constraints", "development"),
        "continuous", "Open Government Licence", raw_resale_allowed=True,
        allowed_uses=("internal_acquisition", "analytics", "derived_products"),
    ),
    "gb_ofgem_fit": _source(
        "gb_ofgem_fit", "Ofgem", "GB", "official_energy_installation_data", "xlsx_bulk",
        "https://www.ofgem.gov.uk/feed-tariffs-fit/contacts-guidance-and-resources/public-reports-and-data-fit/installation-reports",
        ("solar",), ("installation_density", "capacity", "historic_adoption", "geography"),
        "quarterly", "official_public_data",
        allowed_uses=("internal_acquisition", "analytics", "derived_products"),
    ),
    "ca_corporations_canada": _source(
        "ca_corporations_canada", "Corporations Canada", "CA",
        "official_registry", "api",
        "https://api.ised-isde.canada.ca/en/docs?api=corporations",
        ("all",), ("identity", "director", "company_status"),
        "real_time", "official_public_api",
        notes="Federal corporations only; provincial registries remain separate.",
    ),
    "au_abn_lookup": _source(
        "au_abn_lookup", "Australian Business Register", "AU",
        "official_registry", "api",
        "https://abr.business.gov.au/Tools/WebServices",
        ("all",), ("identity", "business_status", "postcode"),
        "current", "registered_web_service",
    ),
    "au_saa_solar": _source(
        "au_saa_solar", "Solar Accreditation Australia", "AU",
        "certified_trade_directory", "public_search",
        "https://www.solaraccreditation.com.au/",
        ("solar", "battery_storage"),
        ("installer", "designer", "accreditation"),
        "current", "official_accreditation_directory",
        notes="SAA is the current SRES installer/designer accreditation scheme operator.",
    ),
    "ie_cro": _source(
        "ie_cro", "Companies Registration Office", "IE",
        "official_registry", "api_bulk",
        "https://opendata.cro.ie/dataset/companies",
        ("all",), ("identity", "company_status", "industry"),
        "daily", "CC-BY-4.0", raw_resale_allowed=True,
        allowed_uses=("internal_acquisition", "entity_resolution", "analytics", "derived_products"),
    ),
    "ie_seai_solar": _source(
        "ie_seai_solar", "Sustainable Energy Authority of Ireland", "IE",
        "certified_trade_directory", "csv_directory",
        "https://www.seai.ie/grants/find-a-registered-professional/solar-pv-companies",
        ("solar",), ("identity", "registration", "territory", "contact"),
        "current", "official_public_directory",
    ),
    "nz_companies_office": _source(
        "nz_companies_office", "New Zealand Companies Office", "NZ",
        "official_registry", "api_bulk",
        "https://www.companiesoffice.govt.nz/data-services/ways-to-get-our-data/",
        ("all",), ("identity", "director", "company_status"),
        "current", "official_api_terms",
    ),
    "de_unternehmensregister": _source(
        "de_unternehmensregister", "Unternehmensregister", "DE",
        "official_registry", "public_search",
        "https://www.unternehmensregister.de/",
        ("all",), ("identity", "company_status", "register_documents"),
        "current", "official_register_terms_apply",
    ),
    "de_mastr": _source(
        "de_mastr", "Bundesnetzagentur Marktstammdatenregister", "DE",
        "official_energy_registry", "bulk_xml",
        "https://www.marktstammdatenregister.de/MaStR/Datendownload",
        ("solar", "battery_storage", "energy"),
        ("installation", "capacity", "market_actor", "geography"),
        "daily", "Datenlizenz Deutschland Namensnennung 2.0",
        raw_resale_allowed=True,
        allowed_uses=("internal_acquisition", "analytics", "derived_products"),
    ),
    "fr_inpi_rne": _source(
        "fr_inpi_rne", "INPI Registre national des entreprises", "FR",
        "official_registry", "api_sftp",
        "https://data.inpi.fr/content/editorial/Acces_API_Entreprises",
        ("all",), ("identity", "company_status", "filings"),
        "daily", "official_open_data",
    ),
    "fr_france_renov_rge": _source(
        "fr_france_renov_rge", "France Rénov'", "FR",
        "government_trade_directory", "public_search",
        "https://france-renov.gouv.fr/annuaire-rge/recherche",
        ("solar", "hvac", "insulation", "property"),
        ("certification", "trade", "territory", "quality"),
        "current", "official_public_directory",
    ),
    "es_rmc": _source(
        "es_rmc", "Registro Mercantil Central", "ES",
        "official_registry", "public_search", "https://www.rmc.es/",
        ("all",), ("identity", "company_name", "registry_information"),
        "current", "official_register_terms_apply", provenance_strength=95,
    ),
    "it_registro_imprese": _source(
        "it_registro_imprese", "Registro Imprese / Camere di Commercio", "IT",
        "official_registry", "api",
        "https://accessoallebanchedati.registroimprese.it/abdo/en/api?lang=en",
        ("all",), ("identity", "director", "company_status", "accounts"),
        "real_time", "commercial_api_terms",
    ),
    "nl_kvk": _source(
        "nl_kvk", "Kamer van Koophandel", "NL",
        "official_registry", "api",
        "https://developers.kvk.nl/documentation/zoeken-api",
        ("all",), ("identity", "activity", "location"),
        "current", "paid_api_terms",
    ),
    "be_cbe": _source(
        "be_cbe", "Crossroads Bank for Enterprises", "BE",
        "official_registry", "api_bulk",
        "https://economie.fgov.be/en/themes/enterprises/crossroads-bank-enterprises/services-everyone/public-data-available-reuse",
        ("all",), ("identity", "activity", "location"),
        "daily", "reuse_terms_apply",
    ),
    "pt_registo_comercial": _source(
        "pt_registo_comercial", "Instituto dos Registos e do Notariado", "PT",
        "official_registry", "public_search",
        "https://registo.justica.gov.pt/Empresas/Publicacoes",
        ("all",), ("identity", "company_status", "filings"),
        "current", "official_public_search", provenance_strength=95,
    ),
}


UNLOCKED_COUNTRIES = (
    "GB", "CA", "AU", "IE", "NZ", "DE", "FR", "ES", "IT", "NL", "BE", "PT"
)

PRIORITY_NICHES = (
    "solar", "roofing", "hvac", "restoration", "property",
    "permits", "private_capital", "logistics", "warehouse",
)


PACKS: dict[str, CountrySourcePack] = {
    "GB": CountrySourcePack(
        "GB", ("gb_companies_house",),
        {
            "solar": ("gb_recc_solar", "gb_mcs", "gb_trustmark", "gb_companies_house"),
            "roofing": ("gb_trustmark", "gb_companies_house"),
            "hvac": ("gb_trustmark", "gb_companies_house"),
            "property": ("gb_planning_data", "gb_companies_house"),
            "permits": ("gb_planning_data",),
        },
        {
            "planning": ("gb_planning_data",),
            "energy": ("gb_ofgem_fit",),
            "solar_adoption": ("gb_ofgem_fit",),
        },
        "jurisdiction_pack_required", "active",
    ),
    "CA": CountrySourcePack(
        "CA", ("ca_corporations_canada",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "AU": CountrySourcePack(
        "AU", ("au_abn_lookup",),
        {"solar": ("au_saa_solar", "au_abn_lookup")}, {},
        "jurisdiction_pack_required", "active_solar",
    ),
    "IE": CountrySourcePack(
        "IE", ("ie_cro",),
        {"solar": ("ie_seai_solar", "ie_cro")}, {},
        "jurisdiction_pack_required", "active_solar",
    ),
    "NZ": CountrySourcePack(
        "NZ", ("nz_companies_office",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "DE": CountrySourcePack(
        "DE", ("de_unternehmensregister",),
        {"solar": ("de_mastr", "de_unternehmensregister")},
        {"energy": ("de_mastr",), "solar_adoption": ("de_mastr",)},
        "jurisdiction_pack_required", "active_solar",
    ),
    "FR": CountrySourcePack(
        "FR", ("fr_inpi_rne",),
        {
            "solar": ("fr_france_renov_rge", "fr_inpi_rne"),
            "hvac": ("fr_france_renov_rge", "fr_inpi_rne"),
            "property": ("fr_france_renov_rge", "fr_inpi_rne"),
        }, {},
        "jurisdiction_pack_required", "active_trade",
    ),
    "ES": CountrySourcePack(
        "ES", ("es_rmc",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "IT": CountrySourcePack(
        "IT", ("it_registro_imprese",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "NL": CountrySourcePack(
        "NL", ("nl_kvk",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "BE": CountrySourcePack(
        "BE", ("be_cbe",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "PT": CountrySourcePack(
        "PT", ("pt_registo_comercial",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
}


def source_contract(source_id: str) -> SourceContract:
    return SOURCES[source_id]


def country_pack(country_code: str) -> CountrySourcePack:
    code = str(country_code or "").upper()
    if code not in PACKS:
        raise KeyError(f"country source pack not configured: {code}")
    return PACKS[code]


def source_waterfall(country_code: str, niche: str) -> tuple[SourceContract, ...]:
    pack = country_pack(country_code)
    key = str(niche or "").strip().casefold()
    ids = list(pack.niche_sources.get(key, ()))
    for source_id in pack.identity_sources:
        if source_id not in ids:
            ids.append(source_id)
    return tuple(SOURCES[source_id] for source_id in ids if source_id in SOURCES)


def classify_runtime_health(
    *, runs: int, accepted: int, errors: int, consecutive_empty_runs: int = 0
) -> str:
    runs = max(0, int(runs))
    accepted = max(0, int(accepted))
    errors = max(0, int(errors))
    empty = max(0, int(consecutive_empty_runs))
    if errors >= 3 and accepted == 0:
        return "QUARANTINED"
    if empty >= 3 and accepted == 0:
        return "QUARANTINED"
    if errors > 0 or (runs >= 2 and accepted == 0):
        return "DEGRADED"
    return "HEALTHY"


def commercial_source_score(
    *, prospects: int = 0, qualified: int = 0, conversations: int = 0,
    verified_revenue_cents: int = 0, runs: int = 1, errors: int = 0
) -> float:
    """Outcome-weighted source score; raw volume is deliberately low weight."""
    denom = max(1, int(runs))
    return round(
        (
            max(0, prospects)
            + max(0, qualified) * 5
            + max(0, conversations) * 20
            + min(max(0, verified_revenue_cents) / 100.0, 10000.0) * 2
            - max(0, errors) * 10
        ) / denom,
        4,
    )


def choose_pack_source(
    country_code: str,
    niche: str,
    *,
    runtime_states: dict[str, str] | None = None,
) -> SourceContract | None:
    runtime_states = runtime_states or {}
    usable = [
        item for item in source_waterfall(country_code, niche)
        if item.production_status == "verified"
        and runtime_states.get(item.source_id, "HEALTHY") != "QUARANTINED"
    ]
    return usable[0] if usable else None


def source_plan(
    country_code: str,
    niche: str,
    *,
    runtime_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    pack = country_pack(country_code)
    waterfall = source_waterfall(country_code, niche)
    selected = choose_pack_source(country_code, niche, runtime_states=runtime_states)
    return {
        "country_code": pack.country_code,
        "niche": str(niche or "").strip().casefold(),
        "pack_status": pack.status,
        "jurisdiction_state": pack.jurisdiction_state,
        "selected_source": selected.source_id if selected else None,
        "waterfall": [item.as_dict() for item in waterfall],
        "execution_authority": "none",
        "actual_revenue": False,
    }


def research_backlog() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for country in UNLOCKED_COUNTRIES:
        pack = PACKS[country]
        if not pack.identity_sources:
            rows.append({
                "country_code": country,
                "niche": "all",
                "status": "source_research_required",
                "next_task": "verify official business identity source",
            })
        for niche in PRIORITY_NICHES:
            if niche not in pack.niche_sources:
                rows.append({
                    "country_code": country,
                    "niche": niche,
                    "status": "niche_source_research_required",
                    "next_task": "verify official/certified niche source plus demand/event sources",
                })
    return tuple(rows)
