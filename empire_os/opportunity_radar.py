"""Predictive Cloud Opportunity Radar.

Aggregates observed opportunity/research surfaces into one read-only radar.
It never invents demand, buyer intent, willingness to pay, economics, market
share, or execution authority. Opportunity Factory promotion remains a
separate evidence-backed assessment step.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


MARKET_GPS = Path("runtime/market_sweeps/revenue_gps_latest.json")
COMMUNITY_INTENT = Path("runtime/community_intent/latest.json")
COMPETITOR_MARKET = Path(
    "runtime/competitive_intelligence/"
    "competitor_market_opportunity_latest.json"
)
OUTPUT = Path("runtime/opportunity_radar/latest.json")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _bounded_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(number, 100.0)), 2)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _market_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("research_queue")
    rows = rows if isinstance(rows, list) else []
    markets_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for raw in payload.get("markets") or []:
        if not isinstance(raw, Mapping):
            continue
        key = (
            _clean(raw.get("niche")).casefold(),
            _clean(raw.get("metro")).casefold(),
        )
        markets_by_key[key] = raw

    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        niche = _clean(row.get("niche"))
        metro = _clean(row.get("metro"))
        market = markets_by_key.get(
            (niche.casefold(), metro.casefold()), {}
        )
        refs = _unique([
            _clean(value)
            for value in (row.get("evidence_refs") or [])
        ])
        output.append({
            "opportunity_key": f"market:{niche}:{metro}".casefold(),
            "opportunity_class": "market_research",
            "source": "market_sweeps_revenue_gps",
            "title": f"{niche} / {metro}".strip(" /"),
            "niche": niche or None,
            "metro": metro or None,
            "trigger": "observed_market_evidence",
            "observed_priority_score": _bounded_score(
                row.get("research_priority_score")
            ),
            "evidence_strength": (
                "commercial_demand_observed"
                if market.get("commercial_demand_state") == "observed"
                else "research_evidence"
            ),
            "evidence_refs": refs,
            "offer_key": market.get("product_candidate"),
            "products": (
                [market.get("product_candidate")]
                if market.get("product_candidate")
                else []
            ),
            "recommended_next_actions": [
                action for action in [
                    _clean(row.get("recommended_next_action"))
                ] if action
            ],
            "commercial_demand_observed": (
                market.get("commercial_demand_state") == "observed"
            ),
            "buyer_intent_inferred": False,
            "market_share_inferred": False,
            "revenue_inferred": False,
            "opportunity_factory_ready": False,
            "factory_blockers": [
                "normalized_economics_required",
                "distribution_strength_evidence_required",
                "fulfilment_readiness_evidence_required",
            ],
            "execution_authority": "none",
        })
    return output


def _community_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    briefs = payload.get("pain_solution_briefs")
    briefs = briefs if isinstance(briefs, list) else []
    output: list[dict[str, Any]] = []
    for row in briefs:
        if not isinstance(row, Mapping):
            continue
        if not row.get("opportunity_event"):
            continue
        pain = _clean(row.get("pain_point"))
        refs = _unique([
            _clean(value)
            for value in (row.get("evidence_urls") or [])
        ])
        intent = _bounded_score(row.get("average_intent_score"))
        output.append({
            "opportunity_key": f"community_pain:{pain}".casefold(),
            "opportunity_class": "community_pain",
            "source": "community_intent",
            "title": pain.replace("_", " ").title(),
            "niche": None,
            "metro": None,
            "trigger": "observed_public_pain",
            "observed_priority_score": intent,
            "evidence_strength": _clean(row.get("evidence_strength")),
            "evidence_refs": refs,
            "offer_key": _clean(row.get("offer_key")) or None,
            "products": [
                _clean(value)
                for value in (row.get("products") or [])
                if _clean(value)
            ],
            "recommended_next_actions": [
                _clean(value)
                for value in (row.get("next_actions") or [])
                if _clean(value)
            ],
            "observed_mentions": int(row.get("observed_mentions") or 0),
            "high_intent_mentions": int(
                row.get("high_intent_mentions") or 0
            ),
            "average_intent_score": intent,
            "buyer_intent_inferred": False,
            "willingness_to_pay_inferred": False,
            "revenue_inferred": False,
            "opportunity_factory_ready": False,
            "factory_blockers": [
                "canonical_buyer_intent_required",
                "economics_evidence_required",
                "distribution_path_evidence_required",
                "fulfilment_readiness_evidence_required",
            ],
            "execution_authority": "none",
        })
    return output


def _competitor_candidates(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gaps = payload.get("underserved_audience_candidates")
    gaps = gaps if isinstance(gaps, list) else []
    if not gaps:
        return []

    niche = _clean(payload.get("niche"))
    metro = _clean(payload.get("metro"))
    market_key = _clean(payload.get("market_key"))
    refs = [
        f"competitive_coverage:{_clean(row.get('entity_id'))}"
        for row in gaps[:25]
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    ]
    return [{
        "opportunity_key": (
            f"competitor_coverage:{market_key or niche}:{metro}"
        ).casefold(),
        "opportunity_class": "competitive_research_gap",
        "source": "competitor_market_opportunity",
        "title": (
            f"Competitor evidence coverage gap — {niche} {metro}"
        ).strip(),
        "niche": niche or None,
        "metro": metro or None,
        "trigger": "observed_competitor_evidence_gap",
        "observed_priority_score": None,
        "evidence_strength": "coverage_gap_only",
        "evidence_refs": refs,
        "offer_key": None,
        "products": [],
        "recommended_next_actions": [
            "collect_additional_public_evidence",
            "resolve_competitor_coverage_gap",
        ],
        "research_gap_company_count": int(
            payload.get("research_gap_company_count") or 0
        ),
        "demand_inferred": False,
        "buyer_intent_inferred": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "opportunity_factory_ready": False,
        "factory_blockers": [
            "coverage_gap_is_not_demand",
            "buyer_intent_evidence_required",
            "economics_evidence_required",
        ],
        "execution_authority": "none",
    }]


def build_opportunity_radar(
    *,
    market_gps: Mapping[str, Any] | None,
    community_intent: Mapping[str, Any] | None,
    competitor_market: Mapping[str, Any] | None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    source_status: dict[str, Any] = {}

    for key, payload, builder in (
        ("market_gps", market_gps, _market_candidates),
        ("community_intent", community_intent, _community_candidates),
        ("competitor_market", competitor_market, _competitor_candidates),
    ):
        if isinstance(payload, Mapping):
            rows = builder(payload)
            candidates.extend(rows)
            source_status[key] = {
                "available": True,
                "candidate_count": len(rows),
                "generated_at": (
                    payload.get("generated_at")
                    or payload.get("observed_at")
                ),
            }
        else:
            source_status[key] = {"available": False}

    candidates.sort(
        key=lambda row: (
            row.get("observed_priority_score") is None,
            -float(row.get("observed_priority_score") or 0),
            str(row.get("opportunity_key") or ""),
        )
    )

    return {
        "schema_version": "empire.predictive_cloud.opportunity_radar.v1",
        "mode": "OBSERVE",
        "generated_at": (
            generated_at or datetime.now(timezone.utc).isoformat()
        ),
        "candidate_count": len(candidates),
        "factory_ready_count": sum(
            row.get("opportunity_factory_ready") is True
            for row in candidates
        ),
        "source_status": source_status,
        "candidates": candidates,
        "next_layer": "opportunity_factory_evidence_completion",
        "automatic_research_allowed": True,
        "automatic_analysis_allowed": True,
        "automatic_planning_allowed": True,
        "automatic_external_execution_allowed": False,
        "outreach_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }


def refresh_opportunity_radar(repo_root: Path) -> dict[str, Any]:
    payload = build_opportunity_radar(
        market_gps=_read_json(repo_root / MARKET_GPS),
        community_intent=_read_json(repo_root / COMMUNITY_INTENT),
        competitor_market=_read_json(repo_root / COMPETITOR_MARKET),
    )
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
