"""Route Opportunity Factory blockers to the correct Empire evidence source."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.opportunity_lifecycle import derive_opportunity_lifecycle


RADAR = Path("runtime/opportunity_radar/latest.json")
INTAKE = Path("runtime/opportunity_factory/intake_latest.json")
OUTPUT = Path("runtime/opportunity_factory/evidence_routes_latest.json")


ROUTES: dict[str, dict[str, Any]] = {
    "buyer_intent_normalized_score_required": {
        "capability": "conversation_os",
        "action": "observe_genuine_commercial_reply_terms_or_payment",
        "mode": "commercial_observation",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "demand_normalized_score_required": {
        "capability": "market_gps_and_commercial_outcomes",
        "action": "collect_direct_demand_or_genuine_commercial_evidence",
        "mode": "commercial_observation",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "urgency_normalized_score_required": {
        "capability": "sensor_mesh",
        "action": "collect_time_bound_event_or_buyer_deadline_evidence",
        "mode": "internal_research",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": True,
    },
    "margin_potential_normalized_score_required": {
        "capability": "commercial_product_catalog",
        "action": "resolve_verified_price_cost_and_margin_basis",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "distribution_strength_normalized_score_required": {
        "capability": "buyer_capacity_readiness",
        "action": "resolve_verified_buyer_partner_capacity",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "distribution_path_required": {
        "capability": "buyer_capacity_readiness",
        "action": "resolve_delivery_or_distribution_route",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "data_advantage_normalized_score_required": {
        "capability": "intelligence_fabric",
        "action": "measure_source_coverage_freshness_and_exclusivity",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "fulfilment_readiness_normalized_score_required": {
        "capability": "commercial_product_catalog_and_fulfilment",
        "action": "resolve_verified_fulfilment_cost_capacity_and_runbook",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "build_complexity_normalized_score_required": {
        "capability": "empire_coder",
        "action": "measure_reuse_scope_dependencies_and_build_delta",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "offer_key_required": {
        "capability": "commercial_product_catalog",
        "action": "match_verified_existing_product_or_define_product_candidate",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": False,
    },
    "independent_evidence_required": {
        "capability": "search_fabric_and_sensor_mesh",
        "action": "collect_independent_public_or_canonical_evidence",
        "mode": "internal_research",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": True,
    },
    "niche_required": {
        "capability": "entity_resolution",
        "action": "classify_market_niche_from_canonical_evidence",
        "mode": "internal_analysis",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": True,
    },
    "trigger_required": {
        "capability": "sensor_mesh",
        "action": "resolve_observed_trigger",
        "mode": "internal_research",
        "automatic_internal_work": True,
        "blocker_can_be_satisfied_by_public_search": True,
    },
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_evidence_routes(
    radar: Mapping[str, Any],
    intake: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = {
        _clean(row.get("opportunity_key")): row
        for row in (radar.get("candidates") or [])
        if isinstance(row, Mapping)
        and _clean(row.get("opportunity_key"))
    }

    routed: list[dict[str, Any]] = []
    capability_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    auto_internal = 0
    commercial_observation = 0

    for row in intake.get("items") or []:
        if not isinstance(row, Mapping):
            continue
        key = _clean(row.get("opportunity_key"))
        candidate = candidates.get(key) or {}
        lifecycle = derive_opportunity_lifecycle(candidate, row)
        stage_counts[lifecycle.current_stage] += 1

        routes = []
        for blocker in row.get("blockers") or []:
            route = dict(ROUTES.get(str(blocker), {
                "capability": "unknown",
                "action": "manual_evidence_route_definition_required",
                "mode": "internal_analysis",
                "automatic_internal_work": False,
                "blocker_can_be_satisfied_by_public_search": False,
            }))
            route["blocker"] = str(blocker)
            routes.append(route)
            capability_counts[route["capability"]] += 1
            if route["automatic_internal_work"]:
                auto_internal += 1
            if route["mode"] == "commercial_observation":
                commercial_observation += 1

        routed.append({
            "opportunity_key": key,
            "opportunity_class": _clean(row.get("opportunity_class")),
            "lifecycle": lifecycle.as_dict(),
            "route_count": len(routes),
            "routes": routes,
            "automatic_external_execution_allowed": False,
            "execution_authority": "none",
        })

    return {
        "schema_version": "empire.opportunity_evidence_routes.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "opportunity_count": len(routed),
        "stage_counts": dict(sorted(stage_counts.items())),
        "capability_counts": dict(
            sorted(capability_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "automatic_internal_route_count": auto_internal,
        "commercial_observation_route_count": commercial_observation,
        "items": routed,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }


def refresh_evidence_routes(repo_root: Path) -> dict[str, Any]:
    payload = build_evidence_routes(
        _read(repo_root / RADAR),
        _read(repo_root / INTAKE),
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
