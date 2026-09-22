"""Evidence-backed normalized signals for Opportunity Factory.

The normalizer converts specific observed or explicitly modeled canonical facts
into the 0..1 inputs required by Opportunity Factory. Every emitted value keeps
its basis and semantic class. Unsupported dimensions remain UNKNOWN.

It must never derive demand, buyer intent, economics, or market share from raw
search-result counts, competitor coverage gaps, generic acquisition volume, or
LLM prose.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


MARKET_GPS = Path("runtime/market_sweeps/revenue_gps_latest.json")
RADAR = Path("runtime/opportunity_radar/latest.json")
OUTPUT = Path("runtime/opportunity_factory/normalized_signals_latest.json")

SCORE_KEYS = (
    "buyer_intent",
    "demand",
    "urgency",
    "margin_potential",
    "distribution_strength",
    "data_advantage",
    "fulfilment_readiness",
    "build_complexity",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _clamp01(value: float) -> float:
    return round(max(0.0, min(float(value), 1.0)), 6)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _score(
    value: float,
    *,
    semantic_class: str,
    basis: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "value": _clamp01(value),
        "semantic_class": semantic_class,
        "basis": basis,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "observed_truth": semantic_class == "observed_stage",
        "modeled_or_policy": semantic_class in {
            "modeled_proxy",
            "policy_scenario",
        },
    }


def _market_lookup(payload: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    rows = payload.get("markets")
    rows = rows if isinstance(rows, list) else []
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key = (
            _clean(row.get("niche")).casefold(),
            _clean(row.get("metro")).casefold(),
        )
        result[key] = row
    return result


def _commercial_stage_scores(
    market: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    replies = int(market.get("commercial_reply_count") or 0)
    terms = int(market.get("commercial_terms_count") or 0)
    payments = int(market.get("verified_payment_count") or 0)
    refs: list[str] = []
    if replies:
        refs.append("canonical:outbound_replies:commercial")
    if terms:
        refs.append("canonical:commercial_terms_reviews")
    if payments:
        refs.append("canonical:bsc_payment_evidence")

    if payments > 0:
        stage = 1.0
        basis = "verified_payment_observed"
    elif terms > 0:
        stage = 0.9
        basis = "commercial_terms_observed"
    elif replies > 0:
        stage = 0.7
        basis = "commercial_reply_observed"
    else:
        return {}

    # These are evidence-strength normalizations, not probabilities or market
    # share. They represent the strongest observed commercial stage in market.
    return {
        "buyer_intent": _score(
            stage,
            semantic_class="observed_stage",
            basis=basis,
            evidence_refs=refs,
        ),
        "demand": _score(
            stage,
            semantic_class="observed_stage",
            basis=basis,
            evidence_refs=refs,
        ),
    }


def _economics_score(
    market: Mapping[str, Any],
) -> dict[str, Any] | None:
    scenario = market.get("economics_scenario")
    if not isinstance(scenario, Mapping):
        return None
    if scenario.get("available") is not True:
        return None

    price = int(scenario.get("pilot_price_cents") or 0)
    cost = int(scenario.get("policy_cost_ceiling_cents") or 0)
    if price <= 0 or cost < 0:
        return None

    margin_ratio = (price - cost) / price
    return _score(
        margin_ratio,
        semantic_class="policy_scenario",
        basis="verified_product_policy_margin_at_cost_ceiling",
        evidence_refs=["canonical:commercial_product_catalog"],
    )


def _distribution_score(
    market: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    buyers = int(market.get("approved_buyer_count") or 0)
    if buyers <= 0:
        return None, None

    # Bounded ordinal proxy. It means observed approved-buyer coverage, not
    # guaranteed delivery capacity.
    if buyers >= 5:
        value = 0.9
    elif buyers >= 3:
        value = 0.8
    elif buyers == 2:
        value = 0.65
    else:
        value = 0.5

    return (
        _score(
            value,
            semantic_class="modeled_proxy",
            basis="approved_buyer_count",
            evidence_refs=["canonical:buyer_candidate_reviews"],
        ),
        "approved_buyer_network",
    )


def normalize_candidate(
    candidate: Mapping[str, Any],
    *,
    market_gps: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    klass = _clean(candidate.get("opportunity_class"))
    key = _clean(candidate.get("opportunity_key"))
    scores: dict[str, dict[str, Any]] = {}
    distribution_path: str | None = None
    offer_key = _clean(candidate.get("offer_key")) or None

    if klass == "market_research" and isinstance(market_gps, Mapping):
        markets = _market_lookup(market_gps)
        market = markets.get((
            _clean(candidate.get("niche")).casefold(),
            _clean(candidate.get("metro")).casefold(),
        ))
        if isinstance(market, Mapping):
            scores.update(_commercial_stage_scores(market))

            economics = _economics_score(market)
            if economics is not None:
                scores["margin_potential"] = economics

            distribution, path = _distribution_score(market)
            if distribution is not None:
                scores["distribution_strength"] = distribution
                distribution_path = path

            if (
                market.get("product_candidate")
                and market.get("economics_scenario")
            ):
                # Existing verified product means less product-build work than a
                # net-new product. This is an internal planning proxy only.
                scores["build_complexity"] = _score(
                    0.2,
                    semantic_class="modeled_proxy",
                    basis="verified_existing_product_candidate",
                    evidence_refs=["canonical:commercial_product_catalog"],
                )
                offer_key = (
                    _clean(market.get("product_candidate"))
                    or offer_key
                )

    normalized_signals: dict[str, Any] = {
        score_key: (
            scores[score_key]["value"]
            if score_key in scores
            else None
        )
        for score_key in SCORE_KEYS
    }
    if offer_key:
        normalized_signals["offer_key"] = offer_key
    if distribution_path:
        normalized_signals["distribution_path"] = distribution_path

    missing = [
        name for name in SCORE_KEYS
        if normalized_signals.get(name) is None
    ]
    if not normalized_signals.get("distribution_path"):
        missing.append("distribution_path")

    return {
        "schema_version": "empire.opportunity_evidence_normalizer.v1",
        "mode": "OBSERVE",
        "opportunity_key": key,
        "opportunity_class": klass,
        "normalized_signals": normalized_signals,
        "score_evidence": scores,
        "normalized_score_count": len(scores),
        "missing_normalized_fields": missing,
        "search_result_counts_used_as_scores": False,
        "competitor_gaps_used_as_demand": False,
        "buyer_intent_inferred_from_public_pain": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }


def build_normalized_signal_batch(
    radar: Mapping[str, Any],
    *,
    market_gps: Mapping[str, Any] | None,
) -> dict[str, Any]:
    rows = [
        normalize_candidate(
            candidate,
            market_gps=market_gps,
        )
        for candidate in (radar.get("candidates") or [])
        if isinstance(candidate, Mapping)
    ]
    return {
        "schema_version": "empire.opportunity_evidence_normalizer_batch.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(rows),
        "candidates_with_any_normalized_score": sum(
            int(row["normalized_score_count"] > 0)
            for row in rows
        ),
        "total_normalized_scores": sum(
            int(row["normalized_score_count"])
            for row in rows
        ),
        "items": rows,
        "search_result_counts_used_as_scores": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "execution_authority": "none",
    }


def refresh_normalized_signals(repo_root: Path) -> dict[str, Any]:
    payload = build_normalized_signal_batch(
        _read(repo_root / RADAR),
        market_gps=_read(repo_root / MARKET_GPS),
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
