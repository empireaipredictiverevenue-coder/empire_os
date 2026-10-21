"""Empire AI proprietary, multi-niche brokerage research configuration.

One controlled research engine, separate source custody and review per country
and vertical. Dental is the first *observed* vertical. Other configured
verticals are PLANNED, not evidence that original sources exist or that a
market research report can already be distributed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NicheProfile:
    code: str
    name: str
    buyer_decision: str
    us_question: str
    uk_question: str
    evidence_categories: tuple[str, ...]
    high_risk_inferences: tuple[str, ...]


NICHES = {
    "dental": NicheProfile(
        "dental", "Dental services",
        "Which original competing service propositions matter to a practice's expansion decision?",
        "Chicago dental implant practice websites and original service positioning",
        "Birmingham dental implant practice websites and official market-study context",
        ("original practice websites", "official market context", "dated source observations"),
        ("patient bookings", "clinical outcomes", "search rankings", "treatment capacity"),
    ),
    "roofing": NicheProfile(
        "roofing", "Roofing",
        "What publicly verifiable local roofing competition, service coverage and project evidence informs a buyer?",
        "US roofing company services and local permit original sources",
        "UK roofing contractor services and official planning original sources",
        ("official permits or planning", "original contractor websites", "verified geographic coverage"),
        ("payable homeowner calls", "buyer capacity", "service eligibility", "verified revenue"),
    ),
    "solar": NicheProfile(
        "solar", "Solar and energy",
        "What verified local installation opportunities and competing offers support a market decision?",
        "US solar installation local incentives public utility and official permit sources",
        "UK solar installer public schemes planning and official data sources",
        ("official scheme rules", "utility or planning data", "original installer service pages"),
        ("installation demand", "subsidy eligibility", "installed capacity", "financial return"),
    ),
    "hvac": NicheProfile(
        "hvac", "HVAC",
        "Which public source facts explain local service competition without claiming call demand?",
        "US HVAC company licensed services original public verification",
        "UK heating air conditioning contractor public verification",
        ("official licences or registers", "original service pages", "geographic service claims"),
        ("booked jobs", "emergency coverage", "call quality", "technician capacity"),
    ),
    "legal": NicheProfile(
        "legal", "Legal services",
        "Which firms publicly state relevant services, jurisdictions and scope?",
        "US law firm published practice areas regulator original records",
        "UK solicitors firms original services and official regulator records",
        ("official regulatory registers", "original legal service descriptions", "jurisdiction"),
        ("case outcomes", "lawyer-client suitability", "lead qualification", "legal advice"),
    ),
    "property": NicheProfile(
        "property", "Property and development",
        "Which official site and permit facts support a specific development decision?",
        "US official municipal permits and development project source records",
        "UK official brownfield registers planning applications original records",
        ("official permits or planning", "public site records", "source field reuse rights"),
        ("development viability", "permit approval prediction", "ownership certainty", "sale price"),
    ),
}

COUNTRIES = ("US", "GB")
SOURCE_READY_ONLY = frozenset({("dental", "US"), ("dental", "GB")})


def research_intake_plan(niche: str, country: str) -> dict:
    """Plan only; never interprets a niche profile as verified source evidence."""
    if niche not in NICHES:
        raise ValueError("UNSUPPORTED_BROKERAGE_NICHE")
    if country not in COUNTRIES:
        raise ValueError("UNSUPPORTED_BROKERAGE_COUNTRY")
    spec = NICHES[niche]
    question = spec.us_question if country == "US" else spec.uk_question
    ready = (niche, country) in SOURCE_READY_ONLY
    return {
        "schema_version": "empire.brokerage.niche_research_intake.v1",
        "niche": niche,
        "niche_name": spec.name,
        "country": country,
        "buyer_problem_to_qualify": spec.buyer_decision,
        "research_question": question,
        "evidence_categories_to_verify": list(spec.evidence_categories),
        "unverified_inferences_to_avoid": list(spec.high_risk_inferences),
        "search_queries": [
            question,
            question + " official original primary source",
        ],
        "source_catalogue_state": (
            "EXISTING_CURATED_DENTAL_ORIGINALS"
            if ready else "ORIGINAL_SOURCES_NOT_YET_ADMITTED"
        ),
        "source_pages_verified": 0,
        "research_findings_confirmed": False,
        "editorial_signed_off": False,
        "source_reuse_rights_verified": False,
        "buyer_intent_verified": False,
        "offer_price_authorized": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "database_writes": False,
        "next_owner": "existing_search_and_market_intelligence",
        "next_action": (
            "EXECUTE_EXISTING_COUNTRY_SOURCE_LEDGER_REVIEW"
            if ready else
            "CURATE_SECTOR_COUNTRY_ORIGINAL_SOURCES_AND_RIGHTS"
        ),
    }
