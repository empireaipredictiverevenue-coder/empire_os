"""Evidence-driven buyer pain -> Empire solution bridge.

Observed public intent is grouped into commercial pain themes and mapped to
existing Empire products/workflows. This layer never claims willingness to pay,
never sends outreach, and never turns a social post into a canonical prospect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Iterable

from empire_os.community_intent import IntentObservation


SOLUTION_MAP: dict[str, dict[str, Any]] = {
    "lead_generation": {
        "offer_key": "predictive_revenue_demand_engine",
        "products": (
            "opportunity_feed",
            "search_opportunity_map",
            "revenue_crm",
        ),
        "next_actions": (
            "validate_vertical_offer",
            "build_why_now_evidence",
            "identify_decision_makers",
        ),
    },
    "sales_conversion": {
        "offer_key": "revenue_conversion_system",
        "products": (
            "revenue_crm",
            "conversation_os",
            "revenue_pulse",
        ),
        "next_actions": (
            "diagnose_follow_up_gap",
            "map_conversion_friction",
            "measure_reply_to_conversation",
        ),
    },
    "search_visibility": {
        "offer_key": "search_growth_command",
        "products": (
            "technical_search_audit",
            "authority_intelligence",
            "geo_ai_visibility",
            "competitor_search_gap",
        ),
        "next_actions": (
            "collect_serp_evidence",
            "collect_backlink_evidence",
            "collect_ai_citation_evidence",
        ),
    },
    "automation_ops": {
        "offer_key": "empire_automation_os",
        "products": (
            "workflow_automation",
            "control_fabric",
            "ops_sentinel",
        ),
        "next_actions": (
            "map_manual_workflow",
            "identify_reversible_automation",
            "define_authority_gates",
        ),
    },
    "data_intelligence": {
        "offer_key": "intelligence_fabric",
        "products": (
            "entity_graph_export",
            "market_signal_feed",
            "opportunity_feed",
        ),
        "next_actions": (
            "identify_missing_evidence",
            "map_entity_resolution_need",
            "validate_data_delivery_mode",
        ),
    },
    "revenue_growth": {
        "offer_key": "predictive_revenue",
        "products": (
            "revenue_pulse",
            "forecast_snapshot",
            "opportunity_feed",
        ),
        "next_actions": (
            "identify_revenue_blocker",
            "measure_current_funnel",
            "attach_offer_to_high_intent_problem",
        ),
    },
    "storm_demand": {
        "offer_key": "storm_revenue_strike",
        "products": (
            "storm_revenue_multiplier",
            "search_opportunity_map",
            "revenue_pulse",
        ),
        "next_actions": (
            "validate_affected_territory",
            "identify_local_capacity",
            "build_storm_why_now",
        ),
    },
}


@dataclass(frozen=True)
class PainSolutionBrief:
    pain_point: str
    observed_mentions: int
    average_intent_score: float
    high_intent_mentions: int
    evidence_urls: tuple[str, ...]
    source_mix: tuple[str, ...]
    offer_key: str | None
    products: tuple[str, ...]
    next_actions: tuple[str, ...]
    opportunity_event: str | None
    evidence_strength: str
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_pain_solution_briefs(
    observations: Iterable[IntentObservation],
) -> list[PainSolutionBrief]:
    rows = tuple(observations)
    pains = sorted({
        pain
        for row in rows
        for pain in row.pain_points
    })
    briefs: list[PainSolutionBrief] = []
    for pain in pains:
        matching = tuple(row for row in rows if pain in row.pain_points)
        urls = tuple(dict.fromkeys(
            row.url for row in matching if row.url
        ))
        sources = tuple(sorted({row.source for row in matching}))
        avg_intent = round(mean(row.intent_score for row in matching), 2)
        high = sum(row.intent_band == "high" for row in matching)
        config = SOLUTION_MAP.get(pain, {})
        evidence_count = len(urls)
        strength = (
            "strong" if evidence_count >= 3 and avg_intent >= 60
            else "moderate" if evidence_count >= 2 and avg_intent >= 40
            else "thin"
        )
        opportunity_event = (
            "opportunity_candidate_created"
            if strength in {"strong", "moderate"}
            else None
        )
        briefs.append(PainSolutionBrief(
            pain_point=pain,
            observed_mentions=len(matching),
            average_intent_score=avg_intent,
            high_intent_mentions=high,
            evidence_urls=urls[:10],
            source_mix=sources,
            offer_key=config.get("offer_key"),
            products=tuple(config.get("products") or ()),
            next_actions=tuple(config.get("next_actions") or ()),
            opportunity_event=opportunity_event,
            evidence_strength=strength,
        ))
    return sorted(
        briefs,
        key=lambda row: (
            {"strong": 0, "moderate": 1, "thin": 2}[row.evidence_strength],
            -row.average_intent_score,
            -row.observed_mentions,
            row.pain_point,
        ),
    )
