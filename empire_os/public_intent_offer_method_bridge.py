"""Original EmpireOS problem-first keyword research bridge.

Inspired by PUBLIC high-level marketing concepts; not a copy of proprietary
Keyword Sniffer internals, proprietary data, wording or any login-only assets.

This module *only* proposes queries, passes them into the original canonical
Keyword Universe and builds an existing draft-only asset backlog. Unverified
queries are not evidence of searches, CPC, rankings, conversions or revenue.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from empire_os.keyword_universe import build_keyword_universe, build_asset_backlog
from empire_os.search_intelligence.products import get_search_product

SCHEMA = "empire.search.public_intent_offer_bridge.v1"
PUBLIC_METHOD_URL = "https://affiliatemarketingdude.com/marcus-campbells-trigger-word-secrets/"
MAX_CANDIDATES = 60
MAX_GLOSSARY = 12

# Independently written, small, generic trigger vocabulary. No paid dictionary
# or scraped members-only search metrics are used.
TRIGGERS: tuple[tuple[str, str, str, str], ...] = (
    ("price", "{seed} price", "commercial", "conversion"),
    ("cost", "{seed} cost", "commercial", "conversion"),
    ("estimate", "{seed} estimate", "commercial", "conversion"),
    ("calculator", "{seed} calculator", "problem", "consideration"),
    ("checklist", "{seed} checklist", "education", "awareness"),
    ("requirements", "{seed} requirements", "problem", "consideration"),
    ("near me", "{seed} near me", "territory", "evaluation"),
    ("best", "best {seed}", "comparison", "evaluation"),
    ("reviews", "{seed} reviews", "comparison", "evaluation"),
    ("vs", "{seed} vs replacement", "comparison", "evaluation"),
    ("how to", "how to evaluate {seed}", "problem", "awareness"),
    ("mistakes", "{seed} common mistakes", "problem", "awareness"),
    ("alternatives", "{seed} alternatives", "comparison", "evaluation"),
    ("inspection", "{seed} inspection", "problem", "consideration"),
)
GLOSSARY_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    ("{term} cost", "commercial", "conversion"),
    ("{term} repair", "problem", "consideration"),
    ("{term} checklist", "education", "awareness"),
    ("{term} vs {seed}", "comparison", "evaluation"),
)


def _phrase(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(label + "_must_be_text")
    text = " ".join(value.strip().lower().split())
    if not 2 <= len(text) <= 95 or not re.fullmatch(r"[\w\s&/().'+-]+", text):
        raise ValueError(label + "_invalid")
    return text


@dataclass(frozen=True)
class IntentOfferSpec:
    market_key: str
    seed_keyword: str
    icp_key: str
    buyer_problem: str
    product_key: str = "search_opportunity_map"
    glossary_terms: tuple[str, ...] = ()
    cta_key: str = "founder_commercial_enquiry"
    territory_key: str | None = None

    def validated(self) -> "IntentOfferSpec":
        for name in ("market_key", "seed_keyword", "icp_key", "buyer_problem",
                     "product_key", "cta_key"):
            _phrase(getattr(self, name), label=name)
        if get_search_product(self.product_key) is None:
            raise ValueError("not_an_existing_search_product")
        if len(self.glossary_terms) > MAX_GLOSSARY:
            raise ValueError("glossary_terms_limit_exceeded")
        terms = [_phrase(t, label="glossary_term") for t in self.glossary_terms]
        if len(set(terms)) != len(terms):
            raise ValueError("duplicate_glossary_terms")
        if self.territory_key:
            _phrase(self.territory_key, label="territory_key")
        return self


def prepare_public_intent_offer_review(spec: IntentOfferSpec) -> dict[str, Any]:
    spec.validated()
    seed = _phrase(spec.seed_keyword, label="seed_keyword")
    records: list[dict[str, Any]] = []
    provenance: list[dict[str, str]] = []
    seen: set[str] = set()

    def propose(keyword: str, intent: str, stage: str, source: str) -> None:
        text = " ".join(keyword.lower().split())
        if text in seen or len(records) >= MAX_CANDIDATES:
            return
        seen.add(text)
        records.append({
            "keyword": text,
            "cluster_key": spec.market_key,
            "intent_class": intent,
            "product_key": spec.product_key,
            "icp_key": spec.icp_key,
            "funnel_stage": stage,
            "cta_key": spec.cta_key,
            "free_tool_key": "RESEARCH_IDEA_NOT_BUILT" if "calculator" in text else None,
            "territory_key": spec.territory_key,
            # These are idea provenance markers, not verified search demand.
            "evidence_refs": [f"derived_idea:{source}", "not_observed_in_serp_or_gsc"],
            # Intentionally OMIT every required scoring input. A proprietary
            # CPC / search count / difficulty screen is not live evidence.
        })
        provenance.append({
            "keyword": text,
            "origin": source,
            "search_demand_status": "NOT_OBSERVED",
        })

    # Natural-language questions are already long-tail intents. Prefixing
    # "best" or suffixing "cost" to an entire question makes junk content.
    # Keep them verbatim and do not extrapolate a market from one GSC row.
    question_root = seed.split()[0] in {
        "how", "what", "why", "when", "where", "which", "who", "can", "should", "does", "do"
    } or len(seed.split()) > 9
    if not question_root:
        for trigger, pattern, intent, stage in TRIGGERS:
            propose(pattern.format(seed=seed), intent, stage, f"generic_trigger:{trigger}")
    for term in spec.glossary_terms:
        normalized = _phrase(term, label="glossary_term")
        for pattern, intent, stage in GLOSSARY_TEMPLATES:
            propose(pattern.format(term=normalized, seed=seed), intent, stage,
                    f"founder_glossary_term:{normalized}")
    # The raw seed is useful for orientation, not a guaranteed good target.
    propose(seed, "problem" if question_root else "category",
            "consideration" if question_root else "awareness", "founder_seed")

    universe = build_keyword_universe(records)
    assets = build_asset_backlog(records)
    if universe["rejected"] or len(universe["keywords"]) != len(records):
        raise ValueError("existing_keyword_universe_rejected_a_generated_candidate")
    if any(row["opportunity"]["available"] or row["opportunity"]["score"] is not None
           for row in universe["keywords"]):
        raise ValueError("unverified_candidates_must_not_be_scored")
    if any(item["opportunity_available"] or not item["draft_only"] for item in assets["assets"]):
        raise ValueError("asset_backlog_must_be_unscored_and_draft_only")

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "owner": "empire_os.keyword_universe",
        "existing_search_product": spec.product_key,
        "existing_buyer_icp": spec.icp_key,
        "market_key": spec.market_key,
        "buyer_problem": spec.buyer_problem,
        "keyword_candidate_count": len(records),
        "keyword_candidates": provenance,
        "universe": universe,
        "existing_asset_backlog": assets,
        "required_next_evidence": [
            "first_party_gsc_or_authorized_keyword_provider_volume",
            "observed_serp_snapshot_and_competitor_coverage",
            "query_to_buyer_problem_validation",
            "real_offer_capability_price_and_binding_terms_check",
            "consented_conversion_tracking_and_settled_revenue_attribution",
        ],
        "search_volume_reported": False,
        "cpc_reported": False,
        "organic_keyword_difficulty_reported": False,
        "rankings_observed": False,
        "buyer_conversion_verified": False,
        "affiliate_payout_verified": False,
        "actual_revenue_verified": False,
        "outbound_authorized": False,
        "content_publish_authorized": False,
        "indexation_authorized": False,
        "paid_ad_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }
