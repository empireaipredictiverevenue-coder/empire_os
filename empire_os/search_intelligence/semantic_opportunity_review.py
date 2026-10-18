"""Explainable, abstention-first search-intent and commercial-fit review.

Extends the existing semantic sector review; no second taxonomy/search engine.
The signals here are *heuristics on text* and do not prove a buyer, location,
volume, revenue, search-indexing state or authority to send a message.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .semantic_sector_review import review_query_sector


# Conservative, intentionally short phrase sets. Explicit negatives are
# prioritised ahead of commercial research; ambiguity returns review.
_JOB = (
    r"\b(?:jobs?|vacanc(?:y|ies)|careers?|apprenticeships?|salary|salaries)\b",
    r"\b(?:job openings?|job adverts?|hiring now|hiring (?:technicians?|employees?|engineers?|apprentices?|sales(?:people|persons| reps)?)|apply for (?:a |the )?job)\b",
    r"\b(?:cv|r[eé]sum[eé])\b",
)
_EDUCATION = (
    r"\b(?:what is|what are|how does|how do|why do|definition of)\b",
    r"\b(?:course|training|certification|exam|tutorial|diy|do it yourself)\b",
    r"\b(?:how to (?:repair|install|fix|build|replace|clean|paint|maintain))\b",
)
_SERVICE_REQUEST = (
    r"\b(?:need|looking for|find|hire|book|request|seeking|want)\b.{0,75}\b(?:contractor|installer|installation|roofer|roofing company|hvac company|agency|provider|service|quote|quotation|estimate|consultant)\b",
    r"\b(?:request|book|get)\s+(?:a |an |the )?(?:quote|quotation|estimate|consultation|survey|assessment)\b",
)
_COMPARISON = (
    r"\b(?:versus|vs\.?|compare|comparison|alternatives?|reviews?|which (?:company|provider|software|agency|service))\b",
    r"\b(?:best|top|recommended|ratings?)\s+(?:\S+\s+){0,5}(?:contractors?|installers?|providers?|companies|agencies|software)\b",
)
_PRICE = (
    r"\b(?:costs?|prices?|pricing|quotations?|quotes?|estimates?|rates?|roi|return on investment)\b",
    r"\b(?:how much|per lead|pay per appointment|pay per click|cpc|cpl)\b",
)
_LOCAL_HINTS = {
    "UK": (
        "united kingdom", "great britain", "england", "scotland", "wales",
        "london", "manchester", "bolton", "glasgow", "edinburgh",
        "liverpool", "leeds", "bristol", "birmingham uk", "uk",
    ),
    "USA": (
        "united states", "usa", "u.s.a.", "chicago", "dallas",
        "houston", "denver", "new york", "los angeles", "phoenix",
        "seattle", "miami", "florida", "texas",
    ),
}


def _hits(query: str, patterns: Sequence[str]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, query, re.I)]


def _territory_evidence(query: str) -> dict[str, Any]:
    matches = {
        country: sorted({
            phrase for phrase in phrases
            if re.search(
                r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])",
                query.casefold(),
            )
        })
        for country, phrases in _LOCAL_HINTS.items()
    }
    hits = {k: v for k, v in matches.items() if v}
    return {
        "geography_claim": (
            next(iter(hits)) if len(hits) == 1 else None
        ),
        "geography_state": (
            "EXPLICIT_TEXT_HINT_UNVERIFIED" if len(hits) == 1
            else "MULTIPLE_MARKETS_ABSTAIN" if len(hits) > 1
            else "UNKNOWN_NO_EXPLICIT_LOCATION"
        ),
        "matched_location_terms": hits,
        "actual_customer_location_verified": False,
    }


def review_semantic_opportunity(
    query: str,
    *,
    ranked_results: Sequence[Mapping[str, Any]] = (),
    source_kind: str = "caller_supplied_unverified",
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Explain intent, geography, vertical and whether human review is useful.

    Works for query text from validated GSC records or draft research seeds,
    but never promotes a text heuristic into verified buyer intent.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must have 1..500 nonblank characters")
    if source_kind not in {
        "caller_supplied_unverified", "GSC_QUERY_PAGE",
        "PAGE_TITLE_UNMEASURED", "EXTERNAL_PUBLIC_TITLE",
    }:
        raise ValueError("unsupported source_kind")
    if (not isinstance(evidence_refs, (list, tuple))
            or len(evidence_refs) > 50
            or any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs)):
        raise ValueError("evidence_refs must be bounded nonempty strings")
    if source_kind == "GSC_QUERY_PAGE" and not evidence_refs:
        raise ValueError("GSC intent review needs original GSC row receipts")

    sector = review_query_sector(query, ranked_results)
    location = _territory_evidence(query)

    job = bool(_hits(query, _JOB))
    learning = bool(_hits(query, _EDUCATION))
    request = bool(_hits(query, _SERVICE_REQUEST))
    compare = bool(_hits(query, _COMPARISON))
    price = bool(_hits(query, _PRICE))

    # A query is not a verified purchase: signals represent text only.
    if job:
        intent = "EMPLOYMENT_OR_TRAINING_REVIEW"
        action = "EXCLUDE_AUTOMATIC_BUYER_ROUTING"
    elif learning and request:
        intent = "MIXED_EDUCATIONAL_AND_SERVICE_QUERY"
        action = "REVIEW_QUERY_INTENT"
    elif learning and not request and not compare:
        intent = "INFORMATIONAL_HYPOTHESIS"
        action = "EDUCATIONAL_CONTENT_REVIEW_ONLY"
    elif request:
        intent = "SERVICE_REQUEST_TEXT_HYPOTHESIS"
        action = "REVIEW_COMMERCIAL_FIT"
    elif compare or price:
        intent = "COMMERCIAL_RESEARCH_HYPOTHESIS"
        action = "REVIEW_COMPARISON_OR_PRICING_CONTENT"
    else:
        intent = "UNKNOWN_INTENT"
        action = "ABSTAIN_UNKNOWN_INTENT"

    sector_state = sector["status"]
    if sector_state in {"ABSTAIN_MULTI_SECTOR_QUERY", "SEMANTIC_SECTOR_CONFLICT_REVIEW"}:
        action = "HUMAN_REVIEW_SECTOR_CONFLICT"
    elif (sector_state == "UNKNOWN_NO_EXPLICIT_SECTOR_EVIDENCE"
          and action == "REVIEW_COMMERCIAL_FIT"):
        action = "HUMAN_REVIEW_UNKNOWN_SECTOR"
    if location["geography_state"] == "MULTIPLE_MARKETS_ABSTAIN":
        action = "HUMAN_REVIEW_MULTIPLE_TERRITORIES"
    if job:
        action = "EXCLUDE_AUTOMATIC_BUYER_ROUTING"

    return {
        "schema_version": "semantic_commercial_opportunity_review.v1",
        "mode": "OBSERVE",
        "query": query,
        "source_kind": source_kind,
        "original_evidence_refs": list(evidence_refs),
        "intent_label": intent,
        "intent_label_is_heuristic": True,
        "textual_signals": {
            "employment": job, "educational": learning,
            "service_request": request, "comparison": compare, "pricing": price,
        },
        "sector_review": sector,
        "territory_review": location,
        "recommended_review_action": action,
        "commercial_value_estimate": None,
        "buyer_willingness_to_pay_verified": False,
        "search_volume_verified": False,
        "buyer_identity_verified": False,
        "conversion_verified": False,
        "revenue_verified": False,
        "outbound_authorized": False,
        "publication_authorized": False,
        "execution_authority": "none",
    }
