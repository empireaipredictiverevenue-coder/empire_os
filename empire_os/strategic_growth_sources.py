"""Strict adapters from existing EmpireOS intelligence into Strategic Growth v2."""
from __future__ import annotations

from typing import Any, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


def candidate_from_market_capture(analysis: Mapping[str, Any]) -> dict[str, Any]:
    identity = analysis.get("identity") if isinstance(analysis.get("identity"), Mapping) else {}
    stage = analysis.get("capture_stage") if isinstance(analysis.get("capture_stage"), Mapping) else {}
    attraction = analysis.get("market_attractiveness") if isinstance(analysis.get("market_attractiveness"), Mapping) else {}
    defensibility = analysis.get("defensibility") if isinstance(analysis.get("defensibility"), Mapping) else {}
    economics = analysis.get("expected_economics") if isinstance(analysis.get("expected_economics"), Mapping) else {}
    risk = economics.get("risk_adjusted") if isinstance(economics.get("risk_adjusted"), Mapping) else {}

    market_key = _text(identity.get("market_key"))
    territory = _text(identity.get("territory_key"))
    corridor = _text(identity.get("corridor_key"))
    product = _text(identity.get("product_key"))
    evidence_refs = [_text(x) for x in analysis.get("evidence_refs") or [] if _text(x)]
    if not market_key or not corridor or not evidence_refs:
        raise ValueError("market capture identity/evidence incomplete")

    stage_name = _text(stage.get("stage")).upper()
    strategy_type = "geo_territory" if stage_name == "EXPAND" else "market_entry"
    confidence = risk.get("confidence")
    expected_gp = economics.get("expected_gross_profit_cents")
    time_days = risk.get("time_to_revenue_days")
    if time_days is None:
        time_days = analysis.get("time_to_revenue_days")

    moat_gaps = {
        _text(row.get("dimension")): row.get("observed_value")
        for row in analysis.get("moat_gaps") or []
        if isinstance(row, Mapping) and _text(row.get("dimension"))
    }
    search_authority = moat_gaps.get("search_authority")
    ai_visibility = moat_gaps.get("ai_visibility")
    partner_density = moat_gaps.get("partner_density")
    data_advantage = moat_gaps.get("data_advantage")
    product_fit = moat_gaps.get("product_fit")

    return {
        "strategy_id": f"market:{corridor}:{stage_name.lower() or 'unknown'}",
        "strategy_type": strategy_type,
        "thesis": (
            f"Advance {corridor} from observed capture stage {stage_name or 'UNKNOWN'} "
            "using the next evidence-backed strategic objective."
        ),
        "target_market": market_key,
        "territory": territory or None,
        "target_icp": "verified_market_buyers",
        "target_roles": [],
        "channel": "market_capture",
        "offer_key": product or None,
        "evidence_refs": evidence_refs,
        "evidence_confidence": confidence,
        "expected_upside_cents": int(expected_gp) if expected_gp is not None else None,
        "estimated_external_cost_cents": None,
        "time_to_signal_days": int(time_days) if time_days is not None else None,
        "speed_to_signal": None,
        "reversibility": 0.8,
        "strategic_fit": attraction.get("score"),
        "product_market_fit": product_fit,
        "buyer_accessibility": None,
        "data_advantage": data_advantage,
        "distribution_advantage": partner_density,
        "competitive_gap": None,
        "learning_value": 0.8,
        "moat_contribution": defensibility.get("score"),
        "operational_simplicity": None,
        "external_cost_efficiency": None,
        "dependencies": ["market_domination", "predictive_cloud"],
        "risks": list(analysis.get("expansion_blockers") or []),
        "experiment": {
            "hypothesis": f"The next objective for {corridor} improves observed commercial outcomes.",
            "baseline": stage_name or None,
            "intervention": (analysis.get("next_strategic_objective") or {}).get("objective"),
            "target_metric": "verified_commercial_outcome_quality",
            "measurement_window": "30 days",
            "minimum_evidence_threshold": "1 new verified commercial outcome",
            "expected_learning": "whether the current market should be deepened, expanded, or deprioritized",
        },
        "kill_criteria": ["no new verified evidence within measurement window"],
        "owner_department": "strategy",
        "authority_required": "observe",
    }
