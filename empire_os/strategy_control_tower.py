"""Executive Strategy Control Tower.

Composes review outputs from Strategy subsystems into one read-only packet.
No market entry, publishing, outreach, contracting, provider activation,
capital commitment, or execution.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _text(v: Any) -> str:
    return str(v or "").strip()


def _available_score(section: Mapping[str, Any], *paths: str) -> float | None:
    cur: Any = section
    try:
        for path in paths:
            cur = cur[path]
    except Exception:
        return None
    try:
        return float(cur) if cur is not None else None
    except (TypeError, ValueError):
        return None


def build_strategy_control_tower(
    *,
    market_portfolio: Mapping[str, Any],
    category_portfolio: Mapping[str, Any],
    keyword_portfolio: Mapping[str, Any],
    competitive_landscape: Mapping[str, Any],
    ai_portfolio: Mapping[str, Any],
    partnership_portfolio: Mapping[str, Any],
    scenario_set: Mapping[str, Any],
) -> dict[str, Any]:
    """Compose already-reviewed packets; never fabricates missing data."""

    top_market = None
    markets = market_portfolio.get("markets") or []
    if markets:
        top_market = markets[0]

    top_category = None
    categories = category_portfolio.get("categories") or []
    if categories:
        top_category = categories[0]

    top_keyword = None
    keywords = (
        keyword_portfolio.get("keywords")
        or keyword_portfolio.get("ranked")
        or []
    )
    if keywords:
        top_keyword = keywords[0]

    top_ai = None
    ai_items = (
        ai_portfolio.get("capabilities")
        or ai_portfolio.get("items")
        or []
    )
    if ai_items:
        top_ai = ai_items[0]

    top_partner = None
    partners = partnership_portfolio.get("partners") or []
    if partners:
        top_partner = partners[0]

    strategic_gaps: list[dict[str, Any]] = []

    if top_market is None:
        strategic_gaps.append({"area": "markets", "reason": "no_ranked_market"})
    if top_category is None:
        strategic_gaps.append({"area": "category", "reason": "no_category_review"})
    if top_keyword is None:
        strategic_gaps.append({"area": "keywords", "reason": "no_keyword_portfolio"})
    if top_ai is None:
        strategic_gaps.append({"area": "ai", "reason": "no_ai_portfolio"})
    if top_partner is None:
        strategic_gaps.append({"area": "partnerships", "reason": "no_partner_portfolio"})

    search_presence = competitive_landscape.get("search_presence") or {}
    if search_presence.get("available") is not True:
        strategic_gaps.append({
            "area": "competitive_search",
            "reason": search_presence.get("reason") or "search_presence_unavailable",
        })

    ai_presence = competitive_landscape.get("ai_citation_presence") or {}
    if ai_presence.get("available") is not True:
        strategic_gaps.append({
            "area": "competitive_ai_visibility",
            "reason": ai_presence.get("reason") or "ai_citation_presence_unavailable",
        })

    scenarios = scenario_set.get("scenarios") or []
    if not scenarios:
        strategic_gaps.append({"area": "scenarios", "reason": "no_scenarios"})

    executive_signals = {
        "top_market": top_market,
        "top_category": top_category,
        "top_keyword": top_keyword,
        "top_ai_capability": top_ai,
        "top_partner": top_partner,
        "scenario_count": len(scenarios),
        "strategic_gap_count": len(strategic_gaps),
    }

    return {
        "schema_version": "strategy_control_tower.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "executive_signals": executive_signals,
        "strategic_gaps": strategic_gaps,
        "source_packets": {
            "market_portfolio_present": bool(market_portfolio),
            "category_portfolio_present": bool(category_portfolio),
            "keyword_portfolio_present": bool(keyword_portfolio),
            "competitive_landscape_present": bool(competitive_landscape),
            "ai_portfolio_present": bool(ai_portfolio),
            "partnership_portfolio_present": bool(partnership_portfolio),
            "scenario_set_present": bool(scenario_set),
        },
        "market_entry_execution": False,
        "publishing_enabled": False,
        "outreach_enabled": False,
        "contracting_enabled": False,
        "capital_commitment": False,
        "provider_activation": False,
    }


def build_strategy_brief(
    control_tower: Mapping[str, Any],
    *,
    max_items: int = 7,
) -> dict[str, Any]:
    if max_items < 1 or max_items > 12:
        raise ValueError("max_items must be between 1 and 12")

    signals = control_tower.get("executive_signals") or {}
    gaps = list(control_tower.get("strategic_gaps") or [])

    items = []
    for key in (
        "top_market",
        "top_category",
        "top_keyword",
        "top_ai_capability",
        "top_partner",
    ):
        value = signals.get(key)
        if value:
            items.append({"type": key, "value": value})

    for gap in gaps:
        if len(items) >= max_items:
            break
        items.append({"type": "strategic_gap", "value": gap})

    return {
        "schema_version": "strategy_executive_brief.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "items": items[:max_items],
        "item_count": min(len(items), max_items),
        "decision_support_only": True,
        "execution_performed": False,
    }
