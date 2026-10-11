"""Canonical daily operating-results projection for EmpireOS."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from empire_os.control_conveyor import build_conveyor
from empire_os.spatial_physical_runtime import build_spatial_physical_runtime

LONDON = ZoneInfo("Europe/London")
_INT = re.compile(r"(?<![\d.])(\d[\d,]*)")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _job_counts(repo_root: Path) -> dict[str, int]:
    base = repo_root / "runtime" / "coder" / "jobs"
    return {
        status: len(list((base / status).glob("*.json")))
        if (base / status).exists()
        else 0
        for status in ("pending", "running", "completed", "failed")
    }


def _stage_rows(loop: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (loop.get("stages") or [])
        if isinstance(row, Mapping)
    ]


def _stage_map(loop: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("stage") or ""): row
        for row in _stage_rows(loop)
        if str(row.get("stage") or "").strip()
    }


def _first_int(text: Any) -> int | None:
    match = _INT.search(str(text or ""))
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _stage_count(stages: Mapping[str, Mapping[str, Any]], name: str) -> int | None:
    row = stages.get(name)
    if not row:
        return None
    for key in ("count", "current_count", "observed_count", "value"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return _first_int(row.get("detail"))


def _report_time(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 48:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _report_count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 1_000_000 else None


def opportunity_daily_results(
    loop: Mapping[str, Any],
    routes: Mapping[str, Any],
    cortex: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Daily founder view of the LAST observed cycle, not invented day totals.

    No research-stage status is an independently verified commercial outcome.
    Missing/stale/ill-typed evidence stays unknown instead of becoming zero.
    """
    if now.tzinfo is None:
        raise ValueError("daily results require a timezone-aware clock")
    local_day = now.astimezone(LONDON).date()
    now_utc = now.astimezone(timezone.utc)
    result: dict[str, Any] = {
        "schema_version": "empire.daily_results.opportunity_activity.v1",
        "mode": "OBSERVE",
        "date": local_day.isoformat(),
        "coverage": "LATEST_COMPLETED_CYCLE_ONLY_NOT_DAILY_TOTAL",
        "source_status": "NO_COMPLETE_ON_DATE_OPPORTUNITY_LOOP",
        "source_freshness": {
            "loop_current_day": False,
            "routes_current_day": False,
            "cortex_current_day": False,
        },
        "found": {
            "observed_candidates_latest_cycle": None,
            "new_identity_count_latest_cycle": None,
        },
        "researched": {
            "candidates_latest_cycle": None,
            "new_public_observations_latest_cycle": None,
        },
        "advanced": {
            "derived_stage_transitions_latest_cycle": None,
            "current_derived_stage_counts": None,
            "commercial_promotion_verified": False,
        },
        "blocked": {"factory_blocked_latest_cycle": None},
        "proved": {
            "verified_commercial_outcomes_today": None,
            "status": "CANONICAL_OUTCOME_EVENT_FEED_NOT_BOUND",
        },
        "learned": {
            "verified_customer_learning_packets_latest_snapshot": None,
            # An old or untrusted Cortex snapshot cannot prove that model
            # weights did or did not change during today's window.
            "model_weights_changed": None,
        },
        "forecast_as_realized_revenue": False,
        "execution_authority": "none",
        "external_execution_performed": False,
    }
    end = _report_time(loop.get("finished_at"))
    start = _report_time(loop.get("started_at"))
    valid_loop = (
        loop.get("schema_version") == "empire.predictive_cloud.opportunity_loop.v2"
        and loop.get("mode") == "OBSERVE"
        and loop.get("execution_authority") == "none"
        and loop.get("automatic_external_execution_allowed") is False
        and loop.get("ok") is True
        and start is not None and end is not None
        and start <= end <= now_utc + timedelta(minutes=5)
        and end.astimezone(LONDON).date() == local_day
        and start.astimezone(LONDON).date() == local_day
    )
    if valid_loop:
        result["source_status"] = "OBSERVED_LATEST_ON_DATE_LOOP"
        result["source_freshness"]["loop_current_day"] = True
        result["found"]["observed_candidates_latest_cycle"] = _report_count(
            loop.get("radar_candidate_count")
        )
        result["researched"]["candidates_latest_cycle"] = _report_count(
            loop.get("research_candidate_count")
        )
        result["researched"]["new_public_observations_latest_cycle"] = _report_count(
            loop.get("research_new_observation_count")
        )
        result["blocked"]["factory_blocked_latest_cycle"] = _report_count(
            loop.get("factory_blocked_count")
        )

        routed_at = _report_time(routes.get("generated_at"))
        routes_current = (
            routes.get("schema_version") == "empire.opportunity_evidence_routes.v1"
            and routes.get("mode") == "OBSERVE"
            and routes.get("execution_authority") == "none"
            and routes.get("automatic_external_execution_allowed") is False
            and routed_at is not None
            and start <= routed_at <= end + timedelta(minutes=1)
            and routed_at.astimezone(LONDON).date() == local_day
        )
        if routes_current:
            result["source_freshness"]["routes_current_day"] = True
            stages = routes.get("stage_counts")
            if (isinstance(stages, Mapping)
                    and all(
                        isinstance(stage, str)
                        and _report_count(count) is not None
                        for stage, count in stages.items()
                    )):
                result["advanced"]["current_derived_stage_counts"] = dict(stages)
            history = routes.get("history")
            if (isinstance(history, Mapping)
                    and history.get("schema_version") ==
                        "empire.opportunity_evidence_history.v1"
                    and history.get("mode") == "OBSERVE"
                    and history.get("execution_authority") == "none"
                    and history.get("automatic_external_execution_allowed") is False
                    and history.get("commercial_stage_independently_verified") is False
                    and history.get("previous_stage_never_promoted") is True
                    and _report_time(history.get("generated_at")) == routed_at):
                result["found"]["new_identity_count_latest_cycle"] = _report_count(
                    history.get("new_identity_count")
                )
                result["advanced"]["derived_stage_transitions_latest_cycle"] = _report_count(
                    history.get("stage_transition_count_this_cycle")
                )

    learned_at = _report_time(cortex.get("generated_at"))
    valid_cortex = (
        cortex.get("schema_version") == "empire.cortex_learning_snapshot.v1"
        and cortex.get("mode") == "OBSERVE"
        and cortex.get("execution_authority") == "none"
        and cortex.get("forecast_used_as_outcome") is False
        and cortex.get("model_weight_mutation_authorized") is False
        and _report_count(cortex.get("synthetic_commercial_label_count")) == 0
        and learned_at is not None
        and learned_at <= now_utc + timedelta(minutes=5)
        and learned_at.astimezone(LONDON).date() == local_day
    )
    if valid_cortex:
        result["source_freshness"]["cortex_current_day"] = True
        result["learned"]["model_weights_changed"] = False
        result["learned"][
            "verified_customer_learning_packets_latest_snapshot"
        ] = _report_count(cortex.get("verified_customer_learning_count"))
    return result


def build_daily_results(
    repo_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    local = current.astimezone(LONDON)
    runtime = repo_root / "runtime"

    acquisition = _read(runtime / "acquisition" / "latest.json")
    qualification = _read(runtime / "qualification" / "latest.json")
    buyer_review = _read(runtime / "buyer_review_materializer" / "latest.json")
    intent = _read(runtime / "community_intent" / "latest.json")
    loop = _read(runtime / "commercial_loop" / "latest.json")
    ops = _read(runtime / "ops_control" / "latest.json")
    source_health = _read(runtime / "source_health" / "latest.json")
    aeo = _read(runtime / "search_intelligence" / "aeo_recovery" / "latest.json")
    security = _read(runtime / "security" / "supabase_audit_latest.json")
    rls_classification = _read(runtime / "security" / "rls_classification_latest.json")
    trust = _read(runtime / "trust" / "latest.json")
    legal_mass_tort = _read(runtime / "legal_mass_tort" / "latest.json")
    revenue_pulse = _read(runtime / "revenue_pulse" / "latest.json")
    opportunity_loop = _read(runtime / "opportunity_radar" / "loop_latest.json")
    opportunity_routes = _read(
        runtime / "opportunity_factory" / "evidence_routes_latest.json"
    )
    cortex_learning = _read(
        runtime / "cortex_learning" / "cortex_learning_latest.json"
    )
    spatial_physical_runtime = build_spatial_physical_runtime(repo_root)
    control_fabric = _read(runtime / "control_fabric" / "latest.json")
    conversation_recovery = _read(runtime / "conversation_recovery" / "latest.json")
    buyer_capacity = _read(runtime / "buyer_capacity" / "latest.json")
    founder_directives = _read(runtime / "founder_directives" / "latest.json")
    stages = _stage_map(loop)
    conveyor = (
        dict(ops.get("conveyor"))
        if isinstance(ops.get("conveyor"), Mapping)
        else build_conveyor(loop)
    )

    funnel = {
        "omega_observations": _stage_count(stages, "omega_projection"),
        "approved_buyers": _stage_count(stages, "buyer_candidate_approved"),
        "outbound_authorized": _stage_count(stages, "outbound_authorized"),
        "outbound_sent": _stage_count(stages, "outbound_sent"),
        "commercial_buyer_replies": _stage_count(stages, "buyer_conversation"),
        "verified_terms": _stage_count(stages, "commercial_terms"),
        "payment_requests": _stage_count(stages, "bsc_payment_request"),
        "verified_payments": _stage_count(stages, "bsc_usdt_payment"),
        "fulfilments": _stage_count(stages, "fulfilment"),
        "recognized_revenue_events": _stage_count(stages, "recognized_revenue"),
        "realized_gp_events": _stage_count(stages, "realized_gross_profit"),
    }

    security_findings = (
        dict(security.get("findings"))
        if isinstance(security.get("findings"), Mapping)
        else {}
    )

    return {
        "schema_version": "empire.daily_results.v1",
        "date": local.date().isoformat(),
        "generated_at": current.isoformat(),
        "timezone": "Europe/London",
        "truth_policy": {
            "unknown_stays_unknown": True,
            "forecast_is_not_actual": True,
            "send_is_not_revenue": True,
            "payment_request_is_not_payment": True,
        },
        "headline": {
            "technical_health": ops.get("healthy"),
            "commercial_blocker": conveyor.get("current_blocker"),
            "blocker_owner": conveyor.get("owner_component"),
            "blocker_authority": conveyor.get("authority"),
            "recognized_revenue_events": funnel["recognized_revenue_events"],
            "realized_gp_events": funnel["realized_gp_events"],
        },
        "commercial_funnel": funnel,
        "opportunity_daily": opportunity_daily_results(
            opportunity_loop, opportunity_routes, cortex_learning,
            now=current,
        ),
        "acquisition": {
            "source": acquisition.get("source"),
            "metro": acquisition.get("metro"),
            "accepted": acquisition.get("accepted"),
            "quality_accepted": acquisition.get("quality_accepted"),
            "quality_rejected": acquisition.get("quality_rejected"),
            "errors": acquisition.get("errors"),
            "observed_at": acquisition.get("observed_at"),
            "source_healthy": source_health.get("end_to_end_healthy"),
        },
        "qualification": {
            "qualified": qualification.get("qualified"),
            "processed": qualification.get("processed"),
            "written": qualification.get("written"),
            "errors": qualification.get("errors"),
            "observed_at": qualification.get("observed_at"),
        },
        "buyer_review": {
            "scanned": buyer_review.get("scanned"),
            "eligible": buyer_review.get("eligible"),
            "probed": buyer_review.get("probed"),
            "proposed": buyer_review.get("proposed"),
            "review_ready": buyer_review.get("review_ready"),
            "deferred_enrichment": buyer_review.get("deferred_enrichment"),
            "rejection_reasons": buyer_review.get("rejection_reasons"),
            "errors": buyer_review.get("errors"),
        },
        "intent_and_pain": {
            "observations": intent.get("observations"),
            "new_observations": intent.get("new_observations"),
            "high_intent": intent.get("high_intent"),
            "medium_intent": intent.get("medium_intent"),
            "by_source": intent.get("by_source"),
            "source_status": intent.get("source_status"),
            "pain_points": intent.get("pain_points"),
            "opportunity_routes": len(intent.get("control_fabric_routes") or []),
        },
        "search_and_seo": {
            "aeo_asset_count": aeo.get("asset_count"),
            "aeo_status_counts": aeo.get("status_counts"),
            "aeo_risk_counts": aeo.get("risk_counts"),
            "timesfm_shadow_enabled": False,
            "traffic_forecast_mode": "SHADOW_COMPARE",
        },
        "legal_intelligence": {
            "market": legal_mass_tort.get("market"),
            "source_count_ready": legal_mass_tort.get("source_count_ready"),
            "source_count_total": legal_mass_tort.get("source_count_total"),
            "firm_buyer_intelligence": legal_mass_tort.get("firm_buyer_intelligence"),
            "consumer_targeting": legal_mass_tort.get("consumer_targeting"),
            "live_market_evidence_bound": legal_mass_tort.get("live_market_evidence_bound"),
            "market_opportunities_observed": legal_mass_tort.get("market_opportunities_observed"),
        },
        "deal_room": {
            "provider": "documenso",
            "bridge_ready": (repo_root / "empire_os/deal_room.py").exists(),
            "provider_execution_activated": False,
            "binding_acceptance": False,
            "payment_request_created": False,
            "revenue_recognition": False,
        },
        "revenue_pulse": {
            "available": bool(revenue_pulse),
            "pulse_state": revenue_pulse.get("pulse_state"),
            "highest_priority_blocker": revenue_pulse.get("highest_priority_blocker"),
            "current_window": revenue_pulse.get("current_window"),
            "previous_window": revenue_pulse.get("previous_window"),
            "conversion": revenue_pulse.get("conversion"),
            "velocity": revenue_pulse.get("velocity"),
            "recognized_revenue_truth": revenue_pulse.get("recognized_revenue_truth"),
            "storm_pulse": revenue_pulse.get("storm_pulse"),
            "spatial_physical_pulse": (
                revenue_pulse.get("spatial_physical_pulse")
                if isinstance(revenue_pulse.get("spatial_physical_pulse"), Mapping)
                else {
                    "volumetric_observations": spatial_physical_runtime.get(
                        "volumetric_observations"
                    ),
                    "physical_observations": spatial_physical_runtime.get(
                        "physical_observations"
                    ),
                    "modeled_opportunities": spatial_physical_runtime.get(
                        "modeled_opportunities"
                    ),
                    "max_combined_priority_boost": spatial_physical_runtime.get(
                        "max_combined_priority_boost"
                    ),
                    "evidence_refs": spatial_physical_runtime.get("evidence_refs"),
                }
            ),
            "forecast_separate_from_truth": (
                (revenue_pulse.get("forecast") or {}).get("separate_from_revenue_truth")
                if isinstance(revenue_pulse.get("forecast"), Mapping)
                else None
            ),
        },
        "control_fabric": {
            "available": bool(control_fabric),
            "component_count": control_fabric.get("component_count"),
            "authority_counts": control_fabric.get("authority_counts"),
            "external_execution_enabled": control_fabric.get("external_execution_enabled"),
            "founder_gates_preserved": control_fabric.get("founder_gates_preserved"),
        },
        "buyer_capacity": {
            "available": bool(buyer_capacity),
            "buyers_seen": buyer_capacity.get("buyers_seen"),
            "status_active": buyer_capacity.get("status_active"),
            "is_active_true": buyer_capacity.get("is_active_true"),
            "commercially_activated": buyer_capacity.get("commercially_activated"),
            "reviewed": buyer_capacity.get("reviewed"),
            "terms_verified": buyer_capacity.get("terms_verified"),
            "capacity_verified": buyer_capacity.get("capacity_verified"),
            "delivery_verified": buyer_capacity.get("delivery_verified"),
            "market_defined": buyer_capacity.get("market_defined"),
            "delivery_destination_present": buyer_capacity.get("delivery_destination_present"),
            "positive_capacity_configured": buyer_capacity.get("positive_capacity_configured"),
            "fully_activated": buyer_capacity.get("fully_activated"),
            "highest_priority_blocker": buyer_capacity.get("highest_priority_blocker"),
            "allocation_ready": buyer_capacity.get("allocation_ready"),
            "activation_blockers": buyer_capacity.get("activation_blockers"),
        },
        "conversation_recovery": {
            "available": bool(conversation_recovery),
            "delivered_first_touches": conversation_recovery.get("delivered_first_touches"),
            "followup_eligible_delivered": conversation_recovery.get("followup_eligible_delivered"),
            "suppressed_after_delivery": conversation_recovery.get("suppressed_after_delivery"),
            "due_now": conversation_recovery.get("due_now"),
            "due_within_24h": conversation_recovery.get("due_within_24h"),
            "recoverable": conversation_recovery.get("recoverable"),
            "blocked_missing_context": conversation_recovery.get("blocked_missing_context"),
            "legacy_generic_subjects": conversation_recovery.get("legacy_generic_subjects"),
            "next_due_in_hours": conversation_recovery.get("next_due_in_hours"),
            "send_executed": conversation_recovery.get("send_executed"),
            "proposal_created": conversation_recovery.get("proposal_created"),
            "pulse_delivery_gap": (
                (
                    (revenue_pulse.get("current_window") or {}).get("delivered_outreach")
                    - conversation_recovery.get("delivered_first_touches")
                )
                if (
                    isinstance(revenue_pulse.get("current_window"), Mapping)
                    and isinstance(
                        (revenue_pulse.get("current_window") or {}).get("delivered_outreach"),
                        int,
                    )
                    and isinstance(conversation_recovery.get("delivered_first_touches"), int)
                )
                else None
            ),
        },
        "founder_directives": {
            "available": bool(founder_directives),
            "directive_count": founder_directives.get("directive_count"),
            "status_counts": founder_directives.get("status_counts"),
            "category_counts": founder_directives.get("category_counts"),
            "founder_gate_count": founder_directives.get("founder_gate_count"),
            "automatic_planning": founder_directives.get("automatic_planning"),
            "automatic_production_execution": founder_directives.get("automatic_production_execution"),
            "execution_mode": founder_directives.get("execution_mode"),
            "latest": founder_directives.get("latest"),
        },
        "coder": _job_counts(repo_root),
        "reliability": {
            "healthy": ops.get("healthy"),
            "incident_count": (
                (ops.get("incident_manager") or {}).get("incident_count")
                if isinstance(ops.get("incident_manager"), Mapping)
                else None
            ),
            "safe_repairs_queued": len(
                (ops.get("sentinel") or {}).get("repair_plan") or []
            )
            if isinstance(ops.get("sentinel"), Mapping)
            else None,
            "current_blocker": conveyor.get("current_blocker"),
            "conveyor": conveyor,
        },
        "security": {
            "supabase_audit_available": bool(security),
            "findings": security_findings,
            "rls_classification_available": bool(rls_classification),
            "rls_table_count": rls_classification.get("table_count"),
            "rls_classes": rls_classification.get("counts"),
            "trust_snapshot_available": bool(trust),
            "trust_ready": (
                (trust.get("assessment") or {}).get("public_trust_center_ready")
                if isinstance(trust.get("assessment"), Mapping)
                else None
            ),
        },
        "commercial_stages": _stage_rows(loop),
        "execution_authority": "none",
        "controls_execution": False,
    }
