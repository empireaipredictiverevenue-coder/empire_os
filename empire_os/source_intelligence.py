"""Country/niche Source Intelligence OS.

This module is descriptive and fail-closed. It does not crawl, send outreach,
accept terms, move funds, or recognize revenue. It defines source contracts,
country packs, ranking, and quarantine decisions for acquisition planning.
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


SOURCES: dict[str, SourceContract] = {
    "gb_companies_house": SourceContract(
        "gb_companies_house", "Companies House", "GB", "official_registry",
        "api", "https://api.company-information.service.gov.uk/",
        ("all",), ("identity", "officer", "company_status"),
        "near_real_time", "official_public_api", "verified", 100, False,
    ),
    "gb_recc_solar": SourceContract(
        "gb_recc_solar", "Renewable Energy Consumer Code", "GB",
        "certified_trade_directory", "html_directory",
        "https://www.recc.org.uk/scheme/members",
        ("solar", "battery_storage", "heat_pump"),
        ("identity", "certification", "territory"),
        "weekly", "public_directory_no_raw_resale", "verified", 95, False,
        "Internal acquisition/provenance use only; do not redistribute the raw directory.",
    ),
    "ca_corporations_canada": SourceContract(
        "ca_corporations_canada", "Corporations Canada", "CA",
        "official_registry", "api",
        "https://api.ised-isde.canada.ca/en/docs?api=corporations",
        ("all",), ("identity", "director", "company_status"),
        "real_time", "official_public_api", "verified", 100, False,
        "Federal corporations only; provincial registries remain separate sources.",
    ),
    "au_abn_lookup": SourceContract(
        "au_abn_lookup", "Australian Business Register", "AU",
        "official_registry", "api",
        "https://abr.business.gov.au/Tools/WebServices",
        ("all",), ("identity", "business_status", "postcode"),
        "current", "registered_web_service", "verified", 100, False,
    ),
    "ie_cro": SourceContract(
        "ie_cro", "Companies Registration Office", "IE",
        "official_registry", "api_bulk",
        "https://opendata.cro.ie/dataset/companies",
        ("all",), ("identity", "company_status", "industry"),
        "daily", "CC-BY-4.0", "verified", 100, True,
    ),
    "ie_seai_solar": SourceContract(
        "ie_seai_solar", "Sustainable Energy Authority of Ireland", "IE",
        "certified_trade_directory", "csv_directory",
        "https://www.seai.ie/grants/find-a-registered-professional/solar-pv-companies",
        ("solar",), ("identity", "certification", "territory", "contact"),
        "current", "official_public_directory", "verified", 100, False,
    ),
    "nz_companies_office": SourceContract(
        "nz_companies_office", "New Zealand Companies Office", "NZ",
        "official_registry", "api_bulk",
        "https://www.companiesoffice.govt.nz/data-services/ways-to-get-our-data/",
        ("all",), ("identity", "director", "company_status"),
        "current", "official_api_terms", "verified", 100, False,
    ),
    "fr_inpi_rne": SourceContract(
        "fr_inpi_rne", "INPI Registre national des entreprises", "FR",
        "official_registry", "api_sftp",
        "https://data.inpi.fr/content/editorial/Acces_API_Entreprises",
        ("all",), ("identity", "company_status", "filings"),
        "daily", "official_open_data", "verified", 100, False,
    ),
    "nl_kvk": SourceContract(
        "nl_kvk", "Kamer van Koophandel", "NL",
        "official_registry", "api",
        "https://developers.kvk.nl/documentation/zoeken-api",
        ("all",), ("identity", "activity", "location"),
        "current", "paid_api_terms", "verified", 100, False,
    ),
    "be_cbe": SourceContract(
        "be_cbe", "Crossroads Bank for Enterprises", "BE",
        "official_registry", "api_bulk",
        "https://economie.fgov.be/en/themes/enterprises/crossroads-bank-enterprises/services-everyone/public-data-available-reuse",
        ("all",), ("identity", "activity", "location"),
        "daily", "reuse_terms_apply", "verified", 100, False,
    ),
    "it_registro_imprese": SourceContract(
        "it_registro_imprese", "Registro Imprese / Camere di Commercio", "IT",
        "official_registry", "api",
        "https://accessoallebanchedati.registroimprese.it/abdo/en/api?lang=en",
        ("all",), ("identity", "director", "company_status", "accounts"),
        "real_time", "commercial_api_terms", "verified", 100, False,
    ),
    "pt_registo_comercial": SourceContract(
        "pt_registo_comercial", "Instituto dos Registos e do Notariado", "PT",
        "official_registry", "public_search",
        "https://registo.justica.gov.pt/Empresas/Publicacoes",
        ("all",), ("identity", "company_status", "filings"),
        "current", "official_public_search", "verified", 95, False,
    ),
}


UNLOCKED_COUNTRIES = ("GB", "CA", "AU", "IE", "NZ", "DE", "FR", "ES", "IT", "NL", "BE", "PT")\n\nPRIORITY_NICHES = ("solar", "roofing", "hvac", "restoration", "property", "permits", "private_capital", "logistics", "warehouse")


PACKS: dict[str, CountrySourcePack] = {
    "GB": CountrySourcePack(
        "GB", ("gb_companies_house",),
        {"solar": ("gb_recc_solar", "gb_companies_house")},
        {
            "property": (),
            "planning": (),
            "grid": (),
            "energy": (),
        },
        "jurisdiction_pack_required", "active",
    ),
    "CA": CountrySourcePack(
        "CA", ("ca_corporations_canada",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "AU": CountrySourcePack(
        "AU", ("au_abn_lookup",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "IE": CountrySourcePack(
        "IE", ("ie_cro",), {"solar": ("ie_seai_solar", "ie_cro")}, {},
        "jurisdiction_pack_required", "active",
    ),
    "NZ": CountrySourcePack(
        "NZ", ("nz_companies_office",), {}, {},
        "jurisdiction_pack_required", "identity_ready_niche_research",
    ),
    "FR": CountrySourcePack(
        "FR", ("fr_inpi_rne",), {}, {},
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
    "DE": CountrySourcePack("DE", (), {}, {}, "jurisdiction_pack_required", "source_research_required"),
    "ES": CountrySourcePack("ES", (), {}, {}, "jurisdiction_pack_required", "source_research_required"),
    "IT": CountrySourcePack("IT", ("it_registro_imprese",), {}, {}, "jurisdiction_pack_required", "identity_ready_niche_research"),
    "PT": CountrySourcePack("PT", ("pt_registo_comercial",), {}, {}, "jurisdiction_pack_required", "identity_ready_niche_research"),
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
    *,
    runs: int,
    accepted: int,
    errors: int,
    consecutive_empty_runs: int = 0,
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


def choose_pack_source(
    country_code: str,
    niche: str,
    *,
    runtime_states: dict[str, str] | None = None,
) -> SourceContract | None:
    runtime_states = runtime_states or {}
    candidates = source_waterfall(country_code, niche)
    usable = [
        item for item in candidates
        if item.production_status == "verified"
        and runtime_states.get(item.source_id, "HEALTHY") != "QUARANTINED"
    ]
    if not usable:
        return None
    # Waterfall order is deliberate: niche-specific certified/official sources
    # come before general company registries. Identity registries remain the
    # corroboration/enrichment layer.
    return usable[0]


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
                    "next_task": (
                        "verify official/certified niche source plus demand/event sources"
                    ),
                })
    return tuple(rows)
