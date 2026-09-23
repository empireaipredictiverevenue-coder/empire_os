"""Canonical read-only status contract for Predictive Cloud.

Aggregates runtime artifacts without mutating business state. Missing artifacts
stay unavailable/unknown rather than becoming zero or healthy.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.control_fabric import default_registry
from empire_os.departments import default_departments, validate_departments


OUTPUT = Path("runtime/predictive_cloud/status_latest.json")

COMPONENTS: dict[str, dict[str, Any]] = {
    "source_health": {
        "path": Path("runtime/source_health/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 1800,
    },
    "community_intent": {
        "path": Path("runtime/community_intent/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 3600,
    },
    "market_gps": {
        "path": Path("runtime/market_sweeps/revenue_gps_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 7200,
    },
    "opportunity_loop": {
        "path": Path("runtime/opportunity_radar/loop_latest.json"),
        "time_keys": ("finished_at", "generated_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_radar": {
        "path": Path("runtime/opportunity_radar/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_research": {
        "path": Path("runtime/opportunity_radar/research_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_normalizer": {
        "path": Path(
            "runtime/opportunity_factory/normalized_signals_latest.json"
        ),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_factory_intake": {
        "path": Path("runtime/opportunity_factory/intake_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_quant_review": {
        "path": Path(
            "runtime/opportunity_factory/quant_review_latest.json"
        ),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_value": {
        "path": Path("runtime/opportunity_factory/value_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "predictive_intelligence": {
        "path": Path("runtime/predictive_intelligence/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 1800,
    },
    "conversion_intelligence": {
        "path": Path("runtime/conversion/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 3600,
    },
    "tag_intelligence": {
        "path": Path("runtime/tag_intelligence/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 28800,
    },
    "media_os": {
        "path": Path("runtime/media_os/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "revenue_pulse": {
        "path": Path("runtime/revenue_pulse/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 900,
    },
    "commercial_loop": {
        "path": Path("runtime/commercial_loop/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 900,
    },
    "commercial_exchange": {
        "path": Path("runtime/commercial_exchange/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 600,
    },
    "buyer_acquisition_team": {
        "path": Path("runtime/buyer_acquisition/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 600,
    },
    "buyer_acquisition_scout": {
        "path": Path("runtime/buyer_acquisition/scout_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 2700,
    },
    "astra": {
        "path": Path("runtime/astra/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 900,
    },
    "astra_executive": {
        "path": Path("runtime/astra/executive_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 900,
    },
    "department_cycle": {
        "path": Path("runtime/astra/department_cycle_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 600,
    },
    "economic_memory": {
        "path": Path("runtime/economic_memory/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 900,
    },
    "founder_directives": {
        "path": Path("runtime/founder_directives/latest.json"),
        "time_keys": ("generated_at", "updated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
}


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _observed_at(
    payload: Mapping[str, Any],
    keys: tuple[str, ...],
) -> datetime | None:
    for key in keys:
        parsed = _time(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _summary(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if name == "source_health":
        return {
            "end_to_end_healthy": payload.get("end_to_end_healthy"),
            "blockers": payload.get("blockers"),
        }
    if name == "community_intent":
        return {
            "observations": payload.get("observations"),
            "new_observations": payload.get("new_observations"),
            "high_intent": payload.get("high_intent"),
        }
    if name == "market_gps":
        return {
            "market_count": payload.get("market_count"),
            "commercial_demand_market_count": payload.get(
                "commercial_demand_market_count"
            ),
            "research_queue_count": len(
                payload.get("research_queue") or []
            ),
        }
    if name == "opportunity_loop":
        return {
            "ok": payload.get("ok"),
            "step_count": len(payload.get("steps") or []),
            "radar_candidate_count": payload.get(
                "radar_candidate_count"
            ),
            "research_observation_count": payload.get(
                "research_observation_count"
            ),
            "candidates_with_any_normalized_score": payload.get(
                "candidates_with_any_normalized_score"
            ),
            "total_normalized_scores": payload.get(
                "total_normalized_scores"
            ),
            "factory_ready_count": payload.get(
                "factory_ready_count"
            ),
            "factory_blocked_count": payload.get(
                "factory_blocked_count"
            ),
            "quant_decision_packet_available_count": payload.get(
                "quant_decision_packet_available_count"
            ),
            "quant_decision_packet_unavailable_count": payload.get(
                "quant_decision_packet_unavailable_count"
            ),
            "quant_missing_field_counts": payload.get(
                "quant_missing_field_counts"
            ),
            "ai_plan_queued_count": payload.get(
                "ai_plan_queued_count"
            ),
        }
    if name == "commercial_exchange":
        return {
            "inventory_count": payload.get("inventory_count"),
            "allocation_candidate_count": payload.get(
                "allocation_candidate_count"
            ),
            "overflow_count": payload.get("overflow_count"),
            "buyer_seat_count": payload.get("buyer_seat_count"),
            "corridor_count": payload.get("corridor_count"),
            "buyer_capacity_never_gates_acquisition": payload.get(
                "buyer_capacity_never_gates_acquisition"
            ),
            "overflow_remains_empire_owned": payload.get(
                "overflow_remains_empire_owned"
            ),
            "automatic_external_delivery": payload.get(
                "automatic_external_delivery"
            ),
            "seat_activation_blocker_counts": payload.get(
                "seat_activation_blocker_counts"
            ),
            "supply_gate_diagnostics": payload.get(
                "supply_gate_diagnostics"
            ),
        }
    if name == "buyer_acquisition_team":
        automation = (
            payload.get("automation")
            if isinstance(payload.get("automation"), Mapping)
            else {}
        )
        return {
            "team_role_count": payload.get("team_role_count"),
            "buyer_pool_count": len(payload.get("buyer_pools") or []),
            "demand_gap_count": payload.get("demand_gap_count"),
            "priority_target_count": len(
                payload.get("priority_targets") or []
            ),
            "product_demand_count": payload.get(
                "product_demand_count"
            ),
            "sellable_product_demand_count": payload.get(
                "sellable_product_demand_count"
            ),
            "market_validate_product_count": payload.get(
                "market_validate_product_count"
            ),
            "icp_priority_target_count": payload.get(
                "icp_priority_target_count"
            ),
            "icp_profile_count": (
                (payload.get("icp_buyer_trigger_intelligence") or {}).get(
                    "profile_count"
                )
                if isinstance(
                    payload.get("icp_buyer_trigger_intelligence"),
                    Mapping,
                )
                else None
            ),
            "icp_execution_authority": (
                (payload.get("icp_buyer_trigger_intelligence") or {}).get(
                    "execution_authority"
                )
                if isinstance(
                    payload.get("icp_buyer_trigger_intelligence"),
                    Mapping,
                )
                else "none"
            ),
            "live_outbound_send": automation.get(
                "live_outbound_send"
            ),
            "canonical_settlement_rail": payload.get(
                "canonical_settlement_rail"
            ),
            "buyer_capacity_never_gates_acquisition": payload.get(
                "buyer_capacity_never_gates_acquisition"
            ),
        }
    if name == "buyer_acquisition_scout":
        return {
            "query_count": payload.get("query_count"),
            "domain_count": payload.get("domain_count"),
            "candidate_count": payload.get("candidate_count"),
            "explicit_direct_buyer_candidate_count": payload.get(
                "explicit_direct_buyer_candidate_count"
            ),
            "icp_assessed_candidate_count": payload.get(
                "icp_assessed_candidate_count"
            ),
            "observed_trigger_candidate_count": payload.get(
                "observed_trigger_candidate_count"
            ),
            "decision_maker_role_match_count": payload.get(
                "decision_maker_role_match_count"
            ),
            "economic_capacity_proxy_count": payload.get(
                "economic_capacity_proxy_count"
            ),
            "verified_budget_candidate_count": payload.get(
                "verified_budget_candidate_count"
            ),
            "database_write_performed": payload.get(
                "database_write_performed"
            ),
            "outbound_sent": payload.get("outbound_sent"),
        }
    if name == "opportunity_radar":
        return {
            "candidate_count": payload.get("candidate_count"),
            "factory_ready_count": payload.get("factory_ready_count"),
        }
    if name == "opportunity_research":
        return {
            "researched_candidate_count": payload.get(
                "researched_candidate_count"
            ),
            "observation_count": payload.get("observation_count"),
            "error_count": payload.get("error_count"),
        }
    if name == "opportunity_normalizer":
        return {
            "candidate_count": payload.get("candidate_count"),
            "candidates_with_any_normalized_score": payload.get(
                "candidates_with_any_normalized_score"
            ),
            "total_normalized_scores": payload.get(
                "total_normalized_scores"
            ),
            "search_result_counts_used_as_scores": payload.get(
                "search_result_counts_used_as_scores"
            ),
        }
    if name == "opportunity_factory_intake":
        return {
            "candidate_count": payload.get("candidate_count"),
            "factory_ready_count": payload.get("factory_ready_count"),
            "blocked_count": payload.get("blocked_count"),
        }
    if name == "opportunity_quant_review":
        return {
            "candidate_count": payload.get("candidate_count"),
            "available_decision_packet_count": payload.get(
                "available_decision_packet_count"
            ),
            "unavailable_decision_packet_count": payload.get(
                "unavailable_decision_packet_count"
            ),
            "missing_field_counts": payload.get(
                "missing_field_counts"
            ),
            "capital_execution": payload.get("capital_execution"),
        }
    if name == "opportunity_value":
        items = payload.get("items")
        items = items if isinstance(items, list) else []
        top = next(
            (
                row for row in items
                if isinstance(row, Mapping)
                and row.get("status") == "AVAILABLE"
            ),
            None,
        )
        return {
            "candidate_count": payload.get("candidate_count"),
            "value_available_count": payload.get("value_available_count"),
            "value_unavailable_count": payload.get("value_unavailable_count"),
            "top_opportunity_key": (
                top.get("opportunity_key")
                if isinstance(top, Mapping)
                else None
            ),
            "top_risk_adjusted_score": (
                top.get("risk_adjusted_score")
                if isinstance(top, Mapping)
                else None
            ),
            "new_scoring_model_introduced": payload.get(
                "new_scoring_model_introduced"
            ),
            "prediction_only": payload.get("prediction_only"),
        }
    if name == "predictive_intelligence":
        return {
            "source_outcome_count": payload.get(
                "source_outcome_count"
            ),
            "matched_outcome_count": payload.get(
                "matched_outcome_count"
            ),
            "probability_ready_product_count": payload.get(
                "probability_ready_product_count"
            ),
            "timing_ready_product_count": payload.get(
                "timing_ready_product_count"
            ),
            "minimum_terminal_samples": payload.get(
                "minimum_terminal_samples"
            ),
            "minimum_timing_samples": payload.get(
                "minimum_timing_samples"
            ),
            "search_scores_used": payload.get(
                "search_scores_used"
            ),
            "llm_probability_used": payload.get(
                "llm_probability_used"
            ),
        }
    if name == "tag_intelligence":
        return {
            "target_count": payload.get("target_count"),
            "available_target_count": payload.get(
                "available_target_count"
            ),
            "failed_target_count": payload.get(
                "failed_target_count"
            ),
            "critical_issue_count": payload.get(
                "critical_issue_count"
            ),
            "high_issue_count": payload.get("high_issue_count"),
            "search_issue_count": payload.get("search_issue_count"),
            "measurement_issue_count": payload.get(
                "measurement_issue_count"
            ),
            "change_count": payload.get("change_count"),
            "critical_change_count": payload.get(
                "critical_change_count"
            ),
            "monitored_site_count": payload.get(
                "monitored_site_count"
            ),
            "monitored_page_count": payload.get(
                "monitored_page_count"
            ),
            "pages_with_public_noindex": payload.get(
                "pages_with_public_noindex"
            ),
            "pages_missing_canonical": payload.get(
                "pages_missing_canonical"
            ),
            "pages_missing_schema": payload.get(
                "pages_missing_schema"
            ),
            "missing_conversion_event_count": payload.get(
                "missing_conversion_event_count"
            ),
            "duplicate_conversion_event_count": payload.get(
                "duplicate_conversion_event_count"
            ),
            "measurement_observation": payload.get(
                "measurement_observation"
            ),
            "automatic_tag_mutation": payload.get(
                "automatic_tag_mutation"
            ),
            "measurement_platform_write": payload.get(
                "measurement_platform_write"
            ),
        }
    if name == "media_os":
        youtube = (
            payload.get("youtube_public")
            if isinstance(payload.get("youtube_public"), Mapping)
            else {}
        )
        outliers = (
            youtube.get("outliers")
            if isinstance(youtube.get("outliers"), Mapping)
            else {}
        )
        owned = (
            payload.get("owned_video_metrics")
            if isinstance(payload.get("owned_video_metrics"), Mapping)
            else {}
        )
        owned_totals = (
            owned.get("observed_totals")
            if isinstance(owned.get("observed_totals"), Mapping)
            else {}
        )
        algorithm = (
            payload.get("algorithm_intelligence")
            if isinstance(payload.get("algorithm_intelligence"), Mapping)
            else {}
        )
        trends = (
            payload.get("trend_fusion")
            if isinstance(payload.get("trend_fusion"), Mapping)
            else {}
        )
        ideas = (
            payload.get("idea_backlog")
            if isinstance(payload.get("idea_backlog"), Mapping)
            else {}
        )
        return {
            "runtime_active": payload.get("runtime_active"),
            "real_evidence_present": payload.get(
                "real_evidence_present"
            ),
            "observed_source_count": payload.get(
                "observed_source_count"
            ),
            "youtube_observation_count": youtube.get(
                "observation_count"
            ),
            "outlier_candidate_count": outliers.get(
                "candidate_count"
            ),
            "owned_video_metric_count": owned.get(
                "record_count"
            ),
            "owned_views_observed": owned_totals.get("views"),
            "owned_engaged_views_observed": owned_totals.get(
                "engaged_views"
            ),
            "owned_watch_time_minutes_observed": owned_totals.get(
                "watch_time_minutes"
            ),
            "owned_subscribers_gained_observed": owned_totals.get(
                "subscribers_gained"
            ),
            "owned_subscribers_lost_observed": owned_totals.get(
                "subscribers_lost"
            ),
            "algorithm_observation_count": algorithm.get(
                "observation_count"
            ),
            "algorithm_hypothesis_count": algorithm.get(
                "hypothesis_count"
            ),
            "trend_topic_count": trends.get("topic_count"),
            "idea_candidate_count": ideas.get("candidate_count"),
            "pending_quant_review_count": ideas.get(
                "pending_quant_review_count"
            ),
            "ready_for_research_generation": payload.get(
                "ready_for_research_generation"
            ),
            "public_publish_authorized": payload.get(
                "public_publish_authorized"
            ),
            "external_action_performed": payload.get(
                "external_action_performed"
            ),
        }
    if name == "conversion_intelligence":
        return {
            "available": payload.get("available"),
            "primary_bottleneck": payload.get("primary_bottleneck"),
        }
    if name == "revenue_pulse":
        truth = payload.get("recognized_revenue_truth")
        truth = truth if isinstance(truth, Mapping) else {}
        return {
            "pulse_state": payload.get("pulse_state"),
            "highest_priority_blocker": payload.get(
                "highest_priority_blocker"
            ),
            "recognized_revenue_cents": truth.get(
                "recognized_revenue_cents"
            ),
            "realized_gp_cents": truth.get("realized_gp_cents"),
        }
    if name == "commercial_loop":
        return {
            "loop_complete": payload.get("loop_complete"),
            "highest_priority_blocker": payload.get(
                "highest_priority_blocker"
            ),
        }
    if name == "astra":
        return {
            "available": payload.get("available"),
            "mode": payload.get("mode"),
            "decision": payload.get("decision"),
        }
    if name == "astra_executive":
        primary = payload.get("primary_goal")
        primary = primary if isinstance(primary, Mapping) else {}
        return {
            "plan_id": payload.get("plan_id"),
            "primary_goal": primary.get("key"),
            "primary_goal_priority": primary.get("priority"),
            "plan_step_count": payload.get("plan_step_count"),
            "departments_in_plan": payload.get("departments_in_plan"),
            "department_plan_counts": payload.get(
                "department_plan_counts"
            ),
            "auto_dispatch_eligible_count": payload.get(
                "auto_dispatch_eligible_count"
            ),
            "founder_gate_step_count": payload.get(
                "founder_gate_step_count"
            ),
            "external_execution_performed": payload.get(
                "external_execution_performed"
            ),
        }
    if name == "department_cycle":
        worker = payload.get("worker")
        worker = worker if isinstance(worker, Mapping) else {}
        evaluation = payload.get("evaluation")
        evaluation = (
            evaluation if isinstance(evaluation, Mapping) else {}
        )
        return {
            "processed_count": worker.get("processed_count"),
            "done_count": worker.get("done_count"),
            "blocked_count": worker.get("blocked_count"),
            "failed_count": worker.get("failed_count"),
            "plan_id": evaluation.get("plan_id"),
            "evaluation_state": evaluation.get("evaluation_state"),
            "status_counts": evaluation.get("status_counts"),
            "external_execution_performed": payload.get(
                "external_execution_performed"
            ),
        }
    if name == "economic_memory":
        return {
            "plan_id": payload.get("plan_id"),
            "plan_evaluation_state": payload.get(
                "plan_evaluation_state"
            ),
            "department_episode_count": payload.get(
                "department_episode_count"
            ),
            "outcome_conditioned_memory_count": payload.get(
                "outcome_conditioned_memory_count"
            ),
            "rejected_outcome_memory_count": payload.get(
                "rejected_outcome_memory_count"
            ),
            "verified_outcomes_only": payload.get(
                "verified_outcomes_only_for_outcome_conditioned_memory"
            ),
            "model_weight_mutation_authorized": payload.get(
                "model_weight_mutation_authorized"
            ),
        }
    if name == "founder_directives":
        return {
            "directive_count": payload.get("directive_count"),
            "founder_gate_count": payload.get("founder_gate_count"),
        }
    return {}


def build_predictive_cloud_status(
    repo_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    components: dict[str, Any] = {}

    for name, config in COMPONENTS.items():
        path = repo_root / config["path"]
        payload = _read(path)
        if payload is None:
            components[name] = {
                "available": False,
                "freshness": "unknown",
                "observed_at": None,
                "age_seconds": None,
                "path": str(config["path"]),
                "summary": {},
            }
            continue

        observed = _observed_at(payload, config["time_keys"])
        age_seconds = None
        freshness = "unknown"
        if observed is not None:
            age_seconds = max(
                0,
                int((current - observed).total_seconds()),
            )
            freshness = (
                "fresh"
                if age_seconds <= int(config["fresh_seconds"])
                else "stale"
            )

        components[name] = {
            "available": True,
            "freshness": freshness,
            "observed_at": (
                observed.isoformat() if observed is not None else None
            ),
            "age_seconds": age_seconds,
            "mode": payload.get("mode"),
            "execution_authority": payload.get("execution_authority"),
            "path": str(config["path"]),
            "summary": _summary(name, payload),
        }

    unavailable = [
        name for name, row in components.items()
        if row["available"] is False
    ]
    stale = [
        name for name, row in components.items()
        if row["freshness"] == "stale"
    ]
    unknown_freshness = [
        name for name, row in components.items()
        if row["available"] and row["freshness"] == "unknown"
    ]

    department_validation = validate_departments(
        registered_components={
            row.name for row in default_registry()
        }
    )

    return {
        "schema_version": "empire.predictive_cloud.status.v2",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "component_count": len(components),
        "available_component_count": sum(
            row["available"] for row in components.values()
        ),
        "unavailable_components": unavailable,
        "stale_components": stale,
        "unknown_freshness_components": unknown_freshness,
        "organization": {
            "department_count": len(default_departments()),
            "fully_wired_department_count": department_validation[
                "fully_wired_department_count"
            ],
            "all_department_components_registered": department_validation[
                "all_components_registered"
            ],
            "departments_with_missing_components": department_validation[
                "departments_with_missing_components"
            ],
            "departments": [
                {
                    "key": row.key,
                    "name": row.name,
                    "mission": row.mission,
                    "authority": row.authority,
                    "components": row.components,
                    "agent_roles": row.agent_roles,
                    "kpis": row.kpis,
                }
                for row in default_departments()
            ],
        },
        "components": components,
        "outreach_sent_by_status": False,
        "payment_action_by_status": False,
        "revenue_recognized_by_status": False,
        "execution_authority": "none",
    }


def refresh_predictive_cloud_status(repo_root: Path) -> dict[str, Any]:
    payload = build_predictive_cloud_status(repo_root)
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
