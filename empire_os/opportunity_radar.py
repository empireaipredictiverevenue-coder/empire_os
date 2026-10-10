"""Predictive Cloud Opportunity Radar.

Aggregates observed opportunity/research surfaces into one read-only radar.
It never invents demand, buyer intent, willingness to pay, economics, market
share, or execution authority. Opportunity Factory promotion remains a
separate evidence-backed assessment step.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


from empire_os.opportunity_revenue_evidence import bridge_factor_evidence
from empire_os.opportunity_factory_readiness import evaluate_factory_readiness
from empire_os.revenue_completion_supervisor import tam_snapshot_truth

from empire_os.commercial_opportunity_decay import (
    assess_opportunity_decay,
)


MARKET_GPS = Path("runtime/market_sweeps/revenue_gps_latest.json")
COMMUNITY_INTENT = Path("runtime/community_intent/latest.json")
COMPETITOR_MARKET = Path(
    "runtime/competitive_intelligence/"
    "competitor_market_opportunity_latest.json"
)
TAM_MARKET = Path("runtime/tam_market_intelligence/latest.json")
STORM_OPPORTUNITY = Path("runtime/storm_opportunity/latest.json")
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


def _tam_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("opportunity_classes")
    rows = rows if isinstance(rows, list) else []
    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        opportunity_key = _clean(row.get("opportunity_key"))
        opportunity_class = _clean(row.get("opportunity_class"))
        industry = _clean(row.get("industry"))
        country_code = _clean(row.get("country_code")).upper()
        refs = _unique([
            _clean(value)
            for value in (row.get("evidence_refs") or [])
        ])
        if not opportunity_key or not opportunity_class or not refs:
            continue
        tam_state = _clean(row.get("tam_state")) or "UNKNOWN"
        output.append({
            "opportunity_key": opportunity_key,
            "opportunity_class": f"tam_{opportunity_class}",
            "source": "tam_market_intelligence",
            "title": (
                f"{opportunity_class.replace('_', ' ').title()} — "
                f"{industry} / {country_code}"
            ),
            "niche": industry or None,
            "metro": None,
            "country_code": country_code or None,
            "trigger": "observed_market_expansion_evidence",
            "observed_priority_score": None,
            "evidence_strength": (
                "verified_tam_context"
                if tam_state == "VERIFIED"
                else "observed_market_scope"
            ),
            "evidence_refs": refs,
            "observed_entity_count": int(
                row.get("observed_entity_count") or 0
            ),
            "tam_entity_count": row.get("tam_entity_count"),
            "tam_state": tam_state,
            "offer_key": None,
            "products": [],
            "recommended_next_actions": [
                "deepen_market_research",
                "validate_buyer_demand",
            ],
            "buyer_intent_inferred": False,
            "demand_inferred": False,
            "pricing_inferred": False,
            "market_share_inferred": False,
            "revenue_inferred": False,
            "opportunity_factory_ready": False,
            "factory_blockers": [
                "canonical_buyer_intent_required",
                "demand_evidence_required",
                "economics_evidence_required",
                "distribution_path_evidence_required",
                "fulfilment_readiness_evidence_required",
            ],
            "execution_authority": "none",
        })
    return output



def _storm_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Consume only fail-closed tenant-scoped Storm opportunity evidence."""
    if payload.get("schema_version") != "empire.storm_opportunity_snapshot.v1":
        return []
    if payload.get("mode") != "OBSERVE":
        return []
    if payload.get("automatic_external_execution_allowed") is not False:
        return []

    raw_rows = payload.get("candidates")
    rows = raw_rows if isinstance(raw_rows, list) else []

    output: list[dict[str, Any]] = []

    for raw in rows:
        if not isinstance(raw, Mapping):
            continue

        row = dict(raw)
        key = _clean(row.get("opportunity_key"))
        tenant_id = _clean(row.get("tenant_id"))

        raw_refs = row.get("evidence_refs")
        raw_refs = raw_refs if isinstance(raw_refs, list) else []

        refs = _unique([
            _clean(value)
            for value in raw_refs
        ])

        if not key or not tenant_id or not refs:
            continue

        row["opportunity_key"] = key
        row["tenant_id"] = tenant_id
        row["evidence_refs"] = refs
        row["source"] = "storm_product_integration"

        if "decision_provenance" in row:
            from empire_os.storm_opportunity_bridge import decision_opportunity_provenance
            try:
                row["decision_provenance"] = decision_opportunity_provenance(
                    row["decision_provenance"]["snapshot"], tenant_id=tenant_id,
                    event_id=row.get("event_id"), subject_id=row.get("subject_id"),
                    as_of=datetime.now(timezone.utc),
                )
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
                continue

        # Radar is intelligence only. Upstream data cannot grant authority.
        row["commercial_ready"] = False
        row["revenue_inferred"] = False
        row["execution_authority"] = "none"
        row["outreach_authority"] = "none"
        row["calls_authority"] = "none"
        row["traffic_authority"] = "none"
        row["commercial_authority"] = "none"
        row["payment_authority"] = "none"
        row["revenue_recognition_authority"] = "none"

        output.append(row)

    return output


def _economic_signal_candidates(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Consume normalized Economic Signal Fabric opportunity candidates.

    Radar does not reinterpret raw economic observations. Revenue leaks, idle
    assets, market gaps and waste must first pass Economic Signal Fabric and
    Opportunity Source Convergence.
    """

    if payload.get("schema_version") != "empire.economic-opportunity-snapshot.v1":
        return []
    if payload.get("mode") != "OBSERVE":
        return []
    if payload.get("execution_authority") != "none":
        return []
    if payload.get("automatic_external_execution_allowed") is not False:
        return []

    rows = payload.get("candidates")
    rows = rows if isinstance(rows, list) else []

    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in rows:
        if not isinstance(raw, Mapping):
            continue

        row = dict(raw)

        if row.get("schema_version") != "empire.opportunity-source.v1":
            continue
        if row.get("source_family") != "economic_signal_fabric":
            continue

        candidate_key = _clean(row.get("candidate_key"))
        tenant_id = _clean(row.get("tenant_id"))
        entity_id = _clean(row.get("entity_id"))
        source_signal_id = _clean(row.get("source_signal_id"))
        opportunity_type = _clean(row.get("opportunity_type"))

        refs = row.get("evidence_refs")
        refs = refs if isinstance(refs, list) else []
        refs = _unique([_clean(value) for value in refs])

        if not (
            candidate_key
            and tenant_id
            and entity_id
            and source_signal_id.startswith("economic_signal_")
            and opportunity_type
            and refs
        ):
            continue

        # Upstream evidence can never grant Radar authority.
        if any(
            row.get(field) != "none"
            for field in (
                "execution_authority",
                "outreach_authority",
                "calls_authority",
                "traffic_authority",
                "commercial_authority",
                "payment_authority",
                "revenue_recognition_authority",
            )
        ):
            continue

        opportunity_key = candidate_key
        if opportunity_key in seen:
            continue
        seen.add(opportunity_key)

        row["opportunity_key"] = opportunity_key
        row["opportunity_class"] = opportunity_type
        row["source"] = "economic_signal_fabric"
        row["trigger"] = "canonical_observed_economic_signal"
        row["evidence_refs"] = refs

        # Economic Signal Fabric confidence is [0,1]. Radar ranking uses
        # [0,100], but this remains an observed evidence priority only.
        confidence = row.get("confidence")
        if type(confidence) in (int, float):
            confidence = float(confidence)
            if 0.0 <= confidence <= 1.0:
                row["observed_priority_score"] = round(
                    confidence * 100.0,
                    2,
                )
            else:
                row["observed_priority_score"] = None
        else:
            row["observed_priority_score"] = None

        row["title"] = (
            opportunity_type.replace("_", " ").title()
        )
        row["niche"] = None
        row["metro"] = None
        row["offer_key"] = None
        row["products"] = []
        row["recommended_next_actions"] = [
            "review_canonical_economic_evidence"
        ]

        row["buyer_intent_inferred"] = False
        row["willingness_to_pay_inferred"] = False
        row["revenue_inferred"] = False
        row["commercial_ready"] = False

        # Preserve the upstream review-only posture. Factory readiness is
        # recalculated below by the existing Radar readiness evaluator.
        row["opportunity_factory_ready"] = False

        row["execution_authority"] = "none"
        row["outreach_authority"] = "none"
        row["calls_authority"] = "none"
        row["traffic_authority"] = "none"
        row["commercial_authority"] = "none"
        row["payment_authority"] = "none"
        row["revenue_recognition_authority"] = "none"

        output.append(row)

    return output


def build_opportunity_radar(
    *,
    market_gps: Mapping[str, Any] | None,
    community_intent: Mapping[str, Any] | None,
    competitor_market: Mapping[str, Any] | None,
    tam_market: Mapping[str, Any] | None = None,
    storm_opportunity: Mapping[str, Any] | None = None,
    economic_signals: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    decay_evidence_by_opportunity: Mapping[
        str, Mapping[str, Any]
    ] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    now = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    decay_evidence_by_opportunity = dict(
        decay_evidence_by_opportunity or {}
    )
    candidates: list[dict[str, Any]] = []
    source_status: dict[str, Any] = {}

    for key, payload, builder in (
        ("market_gps", market_gps, _market_candidates),
        ("community_intent", community_intent, _community_candidates),
        ("competitor_market", competitor_market, _competitor_candidates),
        ("tam_market", tam_market, _tam_candidates),
        ("storm_opportunity", storm_opportunity, _storm_candidates),
        ("economic_signals", economic_signals, _economic_signal_candidates),
    ):
        if key == "tam_market":
            # Reuse the same restricted-source, research-scope and freshness
            # proof as the founder supervisor. A TAM-shaped JSON object is
            # not independently authenticated market evidence.
            tam_check = tam_snapshot_truth(payload, now=now)
            if not tam_check["available"]:
                source_status[key] = {
                    "available": False,
                    "candidate_count": 0,
                    "reason_code": tam_check["reason_code"],
                }
                continue
        if isinstance(payload, Mapping):
            rows = builder(payload)
            source_rows = (
                payload.get("research_queue", [])
                if key == "market_gps"
                else payload.get("pain_solution_briefs", [])
                if key == "community_intent"
                else payload.get("opportunity_classes", [])
                if key == "tam_market"
                else [payload]
            )
            source_rows = source_rows if isinstance(source_rows, list) else []
            if payload.get("available") is False or payload.get("ok") is False:
                source_rows = []
            for row in rows:
                row.update(bridge_factor_evidence(
                    row, source_rows,
                    source_timestamp=payload.get("generated_at") or payload.get("observed_at"),
                    now=now,
                ))
                row.update(evaluate_factory_readiness(row))
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

    identities = Counter(row["opportunity_key"] for row in candidates)
    decay_evidence_count = 0
    for row in candidates:
        decay_evidence = decay_evidence_by_opportunity.get(
            str(row.get("opportunity_key") or "")
        )
        if row["opportunity_key"] in decay_evidence_by_opportunity:
            # The map key binds evidence without an embedded identity.
            # An explicit identity may never override that binding.
            merged = dict(decay_evidence) if isinstance(decay_evidence, Mapping) else {}
            merged.setdefault("opportunity_key", row["opportunity_key"])
            if row.get("offer_key"):
                if "offer_key" in merged and merged["offer_key"] != row["offer_key"]:
                    merged = {}
                else:
                    merged.setdefault("offer_key", row["offer_key"])
            if not isinstance(decay_evidence, Mapping) or identities[row["opportunity_key"]] != 1:
                merged = {}  # No usable component survives ambiguous identity.
            row["opportunity_decay"] = assess_opportunity_decay(
                merged, as_of=now,
                expected_opportunity_key=row["opportunity_key"],
            ).as_dict()
            if identities[row["opportunity_key"]] != 1:
                row["opportunity_decay"]["blockers"] = ("duplicate_opportunity_key",)
            elif not isinstance(decay_evidence, Mapping):
                row["opportunity_decay"]["blockers"] = ("decay_evidence_must_be_mapping",)
            decay_evidence_count += 1

        if identities[row["opportunity_key"]] != 1:
            row["predictive_revenue_inputs"] = {}
            row["predictive_revenue_evidence_refs"] = {}

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
        "decay_evidence_count": decay_evidence_count,
        "decay_changes_ranking": False,
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
        tam_market=_read_json(repo_root / TAM_MARKET),
        storm_opportunity=_read_json(repo_root / STORM_OPPORTUNITY),
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
