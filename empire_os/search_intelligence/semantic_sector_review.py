"""Source-grounded sector sense-check alongside EmpireOS semantic retrieval.

This is a conservative *review* of explicit terminology, not an embedding
model, proof of buyer intent, or automatic reassignment of product verticals.
Returns evidence/source URLs and abstains on multi-vertical terminology.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class SectorTerm:
    product_key: str
    label: str
    phrases: tuple[str, ...]
    evidence_url: str
    evidence_kind: str


# Source-aligned editorial glossary. Heat pumps are heating/cooling technology
# (US DOE). Empire brand labels come from existing first-party sector routes.
# This is a taxonomy hypothesis for routing *review*, not a search observation.
SECTOR_TERMS = (
    SectorTerm(
        "hvac", "heat_pump_hvac",
        ("heat pump", "heat pumps", "air-source heat pump",
         "air source heat pump", "ground-source heat pump",
         "geothermal heat pump", "ductless mini split", "mini-split",
         "mini splits", "air conditioning", "heating ventilation and air conditioning",
         "hvac"),
        "https://www.energy.gov/energysaver/heat-pump-systems",
        "external_official_taxonomy",
    ),
    SectorTerm(
        "solar", "solar_photovoltaic",
        ("solar panel", "solar panels", "photovoltaic", "solar pv",
         "rooftop solar", "solar installer", "solar installation"),
        "https://empire-ai.co.uk/industries/solar",
        "first_party_vertical_label",
    ),
    SectorTerm(
        "roofing", "commercial_roofing",
        ("roofing", "roof repairs", "roof replacement",
         "roof restoration", "flat roof", "commercial roof"),
        "https://empire-ai.co.uk/industries/roofing",
        "first_party_vertical_label",
    ),
    SectorTerm(
        "predictive-revenue-os", "predictive_revenue",
        ("predictive revenue", "revenue forecasting",
         "sales pipeline forecasting", "sales forecasting"),
        "https://empire-ai.co.uk/predictive-revenue",
        "first_party_vertical_label",
    ),
)


def _phrase_hit(query: str, phrase: str) -> bool:
    # No substring accidents, casefold exact-word/phrase boundaries;
    # plural variants are explicitly enumerated in the source glossary.
    pat = r"(?<![a-z0-9])" + re.escape(phrase.casefold()) + r"(?![a-z0-9])"
    return bool(re.search(pat, query.casefold()))


def review_query_sector(
    query: str,
    ranked_results: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Explain exact vertical clues and possible semantic ranking conflicts.

    Does not replace or re-rank the normal hybrid result. Explicit terms can
    propose a human review. Multiple sector indicators always ABSTAIN.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must have 1..500 nonblank characters")
    if not isinstance(ranked_results, (list, tuple)) or len(ranked_results) > 100:
        raise ValueError("ranked results must be a bounded sequence")
    products = []
    if ranked_results:
        for row in ranked_results:
            if not isinstance(row, Mapping) or not isinstance(row.get("product_key"), str):
                raise ValueError("ranked result must have product_key")
            products.append(row["product_key"])

    evidence = []
    sectors = set()
    for term in SECTOR_TERMS:
        hits = sorted({
            phrase for phrase in term.phrases
            if _phrase_hit(query, phrase)
        })
        if hits:
            sectors.add(term.product_key)
            evidence.append({
                "product_key": term.product_key,
                "label": term.label,
                "matched_terms": hits,
                "source_url": term.evidence_url,
                "evidence_kind": term.evidence_kind,
                "source_asserts_search_volume": False,
                "source_asserts_buyer_intent": False,
            })

    top = products[0] if products else None
    hint = next(iter(sectors)) if len(sectors) == 1 else None
    if len(sectors) > 1:
        status = "ABSTAIN_MULTI_SECTOR_QUERY"
    elif not sectors:
        status = "UNKNOWN_NO_EXPLICIT_SECTOR_EVIDENCE"
    elif top is None:
        status = "SECTOR_HYPOTHESIS_NO_RANKING"
    elif hint != top:
        status = "SEMANTIC_SECTOR_CONFLICT_REVIEW"
    else:
        status = "EXPLICIT_TERMINOLOGY_AGREES"
    return {
        "schema_version": "semantic_sector_sensecheck.v1",
        "mode": "OBSERVE",
        "query": query,
        "status": status,
        "suggested_sector_for_review": hint,
        "semantic_top_product": top,
        "candidate_sectors": sorted(sectors),
        "matched_evidence": evidence,
        "automatic_product_assignment": False,
        "purchase_intent_verified": False,
        "search_volume_verified": False,
        "publication_authorized": False,
        "execution_authority": "none",
    }
