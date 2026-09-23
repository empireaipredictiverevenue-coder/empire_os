"""Read-only founder dashboard projection from canonical runtime evidence."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.control_conveyor import build_conveyor
from empire_os.permit_intelligence_runtime import build_permit_intelligence_runtime
from empire_os.vertical_intelligence_runtime import (
    build_private_capital_intelligence_runtime,
    build_property_intelligence_runtime,
)
from empire_os.commercial_recovery_registry import (
    recovery_product_catalog,
    recovery_summary,
)
from empire_os.commercial_recovery_audit import (
    build_recovery_implementation_audit,
)
from empire_os.canonical_phase_plan import (
    build_canonical_phase_plan,
)
from empire_os.phase_3f_closeout import (
    build_phase_3f_closeout,
)
from empire_os.commercial_exchange_contract import (
    build_commercial_exchange_contract,
)
from empire_os.buyer_acquisition_team import (
    refresh_buyer_acquisition_plan,
)
from empire_os.commercial_pricing_policy import (
    build_launch_pricing_proposal,
)
from empire_os.competitor_audience_runtime import (
    build_competitor_audience_runtime,
)
from empire_os.competitor_audience_research_executor import (
    build_account_research_runtime,
)
from empire_os.competitor_account_brief import (
    build_account_brief_runtime,
)
from empire_os.buyer_state_evidence import (
    build_buyer_state_runtime,
)
from empire_os.next_best_action import (
    build_next_best_action_runtime,
)
from empire_os.account_digital_twin import (
    build_account_twin_runtime,
)
from empire_os.cortex_learning_loop import (
    build_cortex_learning_runtime,
)
from empire_os.competitor_market_scale import (
    build_market_scale_runtime,
)
from empire_os.competitor_market_opportunity import (
    build_market_opportunity_runtime,
)
from empire_os.competitor_ecosystem_mining import (
    build_ecosystem_runtime,
)
from empire_os.competitor_public_review_overlap import (
    build_public_review_overlap_runtime,
)
from empire_os.competitor_search_presence import (
    build_search_presence_runtime,
)
from empire_os.competitor_public_activity import (
    build_public_activity_runtime,
)
from empire_os.competitor_intelligence_feed import (
    build_feed_runtime,
)
from empire_os.commercial_marketing_registry import (
    marketing_plan_catalog,
    marketing_summary,
)
from empire_os.commercial_funnel import (
    build_funnel_runtime,
)
from empire_os.revenue_pulse import (
    build_revenue_pulse_runtime,
)
from empire_os.market_sweep_revenue_gps import (
    build_market_sweep_runtime,
)

PHASE_RE = re.compile(
    r"^### Phase\s+(\d+)\s+—\s+(.+?)(?:\s+←\s+CURRENT)?$",
    re.MULTILINE,
)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _mtime_iso(path: Path) -> str | None:
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()


def _phase_projection(blueprint: Path) -> list[dict[str, Any]]:
    try:
        text = blueprint.read_text()
    except OSError:
        return []

    matches = list(PHASE_RE.finditer(text))
    phases: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        number = int(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]

        heading_line = match.group(0)
        if number == 3 or "FROZEN" in title.upper():
            state = "implementation_frozen_proof_pending"
        elif "CURRENT" in heading_line or number == 4:
            state = "current_observe"
        else:
            state = "parallel_build"

        phases.append(
            {
                "phase": number,
                "title": title.replace(
                    " — IMPLEMENTATION FROZEN / PRODUCTION PROOF GATES CARRIED FORWARD",
                    "",
                ),
                "state": state,
                "verified_markers": section.count("✅"),
            }
        )
    return phases


def _commercial_operating_state(
    raw: dict[str, Any],
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    blocker = str(raw.get("highest_priority_blocker") or "").strip() or None
    observed = {
        str(row.get("stage") or ""): row.get("observed")
        for row in stages
        if isinstance(row, dict)
    }

    if raw.get("loop_complete") is True:
        return {
            "class": "COMPLETE",
            "next_event": None,
            "founder_action_required": False,
        }

    if blocker == "buyer_conversation" and observed.get("outbound_sent") is True:
        return {
            "class": "WAITING_EXTERNAL",
            "next_event": "genuine_buyer_reply",
            "founder_action_required": False,
        }

    founder_gates = {
        "commercial_terms": "binding_commercial_terms",
        "bsc_payment_request": "payment_request_authority",
        "recognized_revenue": "revenue_recognition",
    }
    if blocker in founder_gates:
        return {
            "class": "FOUNDER_GATE",
            "next_event": founder_gates[blocker],
            "founder_action_required": True,
        }

    return {
        "class": "SYSTEM_WORK",
        "next_event": blocker,
        "founder_action_required": False,
    }


def _commercial_loop(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "loop_complete": False,
            "highest_priority_blocker": "unavailable",
            "stages": [],
        }
    stages = raw.get("stages")
    clean_stages = stages if isinstance(stages, list) else []
    return {
        "available": True,
        "observed_at": _mtime_iso(path),
        "mode": raw.get("mode"),
        "loop_complete": raw.get("loop_complete") is True,
        "blocker_state": raw.get("blocker_state"),
        "highest_priority_blocker": raw.get("highest_priority_blocker"),
        "operating_state": _commercial_operating_state(raw, clean_stages),
        "stages": clean_stages,
    }


def _astra(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}

    evidence = raw.get("operational_evidence")
    observed = evidence.get("observed") if isinstance(evidence, dict) else {}
    freshness = evidence.get("freshness") if isinstance(evidence, dict) else {}
    board = raw.get("operating_board")
    board_result = board.get("result") if isinstance(board, dict) else {}
    items = board_result.get("items") if isinstance(board_result, dict) else []
    calibration = raw.get("calibration")

    return {
        "available": True,
        "observed_at": _mtime_iso(path),
        "mode": raw.get("mode"),
        "fresh": freshness.get("fresh") if isinstance(freshness, dict) else None,
        "freshness_reason": (
            freshness.get("reason") if isinstance(freshness, dict) else None
        ),
        "observed": observed if isinstance(observed, dict) else {},
        "board": items if isinstance(items, list) else [],
        "calibration": calibration if isinstance(calibration, dict) else {},
    }


def _source_health(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}
    return {
        "available": True,
        "snapshot_updated_at": _mtime_iso(path),
        "observed_at": raw.get("observed_at"),
        "source": raw.get("source"),
        "metro": raw.get("metro"),
        "mode": raw.get("mode"),
        "endpoint_healthy": raw.get("endpoint_healthy"),
        "end_to_end_healthy": raw.get("end_to_end_healthy"),
        "candidates_seen": raw.get("candidates_seen"),
        "quality_accepted": raw.get("quality_accepted"),
        "quality_rejected": raw.get("quality_rejected"),
        "canonical_writes": raw.get("canonical_writes"),
        "blockers": raw.get("blockers") if isinstance(raw.get("blockers"), list) else [],
        "errors": raw.get("errors") if isinstance(raw.get("errors"), list) else [],
    }


def _acquisition(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}
    # This is explicitly the last run record, not the current source-health truth.
    return {
        "available": True,
        "snapshot_updated_at": _mtime_iso(path),
        "started_at": raw.get("started_at"),
        "source": raw.get("source"),
        "metro": raw.get("metro"),
        "real_data_only": raw.get("real_data_only"),
        "recorded_ok": raw.get("ok"),
        "returncode": raw.get("returncode"),
        "max_candidates": raw.get("max_candidates"),
    }




def _conversion(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}
    stages = raw.get("stages")
    unknown = raw.get("unknown_stages")
    return {
        "available": True,
        "observed_at": raw.get("observed_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "source": raw.get("source"),
        "min_sample_size": raw.get("min_sample_size"),
        "primary_bottleneck": raw.get("primary_bottleneck"),
        "primary_bottleneck_rate": raw.get("primary_bottleneck_rate"),
        "experiment_candidate": raw.get("experiment_candidate"),
        "unknown_stages": unknown if isinstance(unknown, list) else [],
        "stages": stages if isinstance(stages, list) else [],
        "counts": raw.get("counts") if isinstance(raw.get("counts"), dict) else {},
        "execution_authority": raw.get("execution_authority", "none"),
    }

def _commercial_catalog(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "product_count": 0,
            "binding_terms_ready_count": 0,
            "blocker_counts": {},
        }
    return {
        "available": True,
        "observed_at": _mtime_iso(path),
        "schema_version": raw.get("schema_version"),
        "product_count": int(raw.get("product_count") or 0),
        "active_count": int(raw.get("active_count") or 0),
        "binding_terms_ready_count": int(
            raw.get("binding_terms_ready_count") or 0
        ),
        "blocker_counts": (
            raw.get("blocker_counts")
            if isinstance(raw.get("blocker_counts"), dict)
            else {}
        ),
        "actual_revenue": False,
        "execution_authority": "none",
    }


def _opportunity_value(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "execution_authority": "none",
        }
    items = raw.get("items")
    items = items if isinstance(items, list) else []
    top = next(
        (
            row for row in items
            if isinstance(row, dict)
            and row.get("status") == "AVAILABLE"
        ),
        None,
    )
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "candidate_count": int(raw.get("candidate_count") or 0),
        "value_available_count": int(
            raw.get("value_available_count") or 0
        ),
        "value_unavailable_count": int(
            raw.get("value_unavailable_count") or 0
        ),
        "top_opportunity": (
            {
                "opportunity_key": top.get("opportunity_key"),
                "rank": top.get("rank"),
                "expected_revenue_cents": top.get(
                    "expected_revenue_cents"
                ),
                "expected_gross_profit_cents": top.get(
                    "expected_gross_profit_cents"
                ),
                "risk_adjusted_score": top.get(
                    "risk_adjusted_score"
                ),
            }
            if isinstance(top, dict)
            else None
        ),
        "new_scoring_model_introduced": (
            raw.get("new_scoring_model_introduced") is True
        ),
        "prediction_only": raw.get("prediction_only") is True,
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _predictive_intelligence(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "source_outcome_count": int(raw.get("source_outcome_count") or 0),
        "matched_outcome_count": int(raw.get("matched_outcome_count") or 0),
        "unmatched_outcome_count": int(raw.get("unmatched_outcome_count") or 0),
        "probability_ready_product_count": int(
            raw.get("probability_ready_product_count") or 0
        ),
        "timing_ready_product_count": int(
            raw.get("timing_ready_product_count") or 0
        ),
        "minimum_terminal_samples": raw.get("minimum_terminal_samples"),
        "minimum_timing_samples": raw.get("minimum_timing_samples"),
        "prediction_only": raw.get("prediction_only") is True,
        "search_scores_used": raw.get("search_scores_used") is True,
        "llm_probability_used": raw.get("llm_probability_used") is True,
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _economic_memory(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "plan_id": raw.get("plan_id"),
        "plan_evaluation_state": raw.get("plan_evaluation_state"),
        "department_episode_count": int(
            raw.get("department_episode_count") or 0
        ),
        "retrievable_department_episode_count": int(
            raw.get("retrievable_department_episode_count") or 0
        ),
        "source_learning_ready_count": int(
            raw.get("source_learning_ready_count") or 0
        ),
        "outcome_conditioned_memory_count": int(
            raw.get("outcome_conditioned_memory_count") or 0
        ),
        "rejected_outcome_memory_count": int(
            raw.get("rejected_outcome_memory_count") or 0
        ),
        "verified_outcomes_only": (
            raw.get(
                "verified_outcomes_only_for_outcome_conditioned_memory"
            )
            is True
        ),
        "department_done_is_verified_outcome": (
            raw.get("department_done_is_verified_outcome") is True
        ),
        "model_weight_mutation_authorized": (
            raw.get("model_weight_mutation_authorized") is True
        ),
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _commercial_exchange_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("observed_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "source": raw.get("source"),
        "prospects_scanned": int(raw.get("prospects_scanned") or 0),
        "inventory_count": int(raw.get("inventory_count") or 0),
        "allocation_candidate_count": int(
            raw.get("allocation_candidate_count") or 0
        ),
        "overflow_count": int(raw.get("overflow_count") or 0),
        "allocated_count": int(raw.get("allocated_count") or 0),
        "blocked_missing_evidence_count": int(
            raw.get("blocked_missing_evidence_count") or 0
        ),
        "buyer_seat_count": int(raw.get("buyer_seat_count") or 0),
        "corridor_count": int(raw.get("corridor_count") or 0),
        "inventory_state_counts": (
            raw.get("inventory_state_counts")
            if isinstance(raw.get("inventory_state_counts"), dict)
            else {}
        ),
        "seat_state_counts": (
            raw.get("seat_state_counts")
            if isinstance(raw.get("seat_state_counts"), dict)
            else {}
        ),
        "seat_activation_blocker_counts": (
            raw.get("seat_activation_blocker_counts")
            if isinstance(
                raw.get("seat_activation_blocker_counts"), dict
            )
            else {}
        ),
        "supply_gate_diagnostics": (
            raw.get("supply_gate_diagnostics")
            if isinstance(raw.get("supply_gate_diagnostics"), dict)
            else {}
        ),
        "buyer_capacity_never_gates_acquisition": (
            raw.get("buyer_capacity_never_gates_acquisition") is True
        ),
        "overflow_remains_empire_owned": (
            raw.get("overflow_remains_empire_owned") is True
        ),
        "automatic_external_delivery": (
            raw.get("automatic_external_delivery") is True
        ),
        "production_schema_applied": (
            raw.get("production_schema_applied") is True
        ),
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _buyer_scout_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "query_count": int(raw.get("query_count") or 0),
        "domain_count": int(raw.get("domain_count") or 0),
        "probed_domain_count": int(raw.get("probed_domain_count") or 0),
        "candidate_count": int(raw.get("candidate_count") or 0),
        "explicit_direct_buyer_candidate_count": int(
            raw.get("explicit_direct_buyer_candidate_count") or 0
        ),
        "probe_failure_counts": (
            raw.get("probe_failure_counts")
            if isinstance(raw.get("probe_failure_counts"), dict)
            else {}
        ),
        "database_write_performed": (
            raw.get("database_write_performed") is True
        ),
        "outbound_sent": raw.get("outbound_sent") is True,
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _buyer_reconciliation_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "candidate_count": int(raw.get("candidate_count") or 0),
        "existing_buyer_count": int(
            raw.get("existing_buyer_count") or 0
        ),
        "existing_prospect_count": int(
            raw.get("existing_prospect_count") or 0
        ),
        "new_external_candidate_count": int(
            raw.get("new_external_candidate_count") or 0
        ),
        "reconciliation_state_counts": (
            raw.get("reconciliation_state_counts")
            if isinstance(raw.get("reconciliation_state_counts"), dict)
            else {}
        ),
        "database_write_performed": (
            raw.get("database_write_performed") is True
        ),
        "automatic_ingest_authorized": (
            raw.get("automatic_ingest_authorized") is True
        ),
        "outbound_sent": raw.get("outbound_sent") is True,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _buyer_persistence_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "persisted_candidate_count": int(
            raw.get("persisted_candidate_count") or 0
        ),
        "skipped_candidate_count": int(
            raw.get("skipped_candidate_count") or 0
        ),
        "holding_area_only": raw.get("holding_area_only") is True,
        "canonical_promotion_performed": (
            raw.get("canonical_promotion_performed") is True
        ),
        "automatic_ingest_authorized": (
            raw.get("automatic_ingest_authorized") is True
        ),
        "outbound_sent": raw.get("outbound_sent") is True,
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _pricing_verification_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "pricing_matches_approved_policy": False,
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("observed_at") or _mtime_iso(path),
        "approval_reference": raw.get("approval_reference"),
        "expected_product_count": int(
            raw.get("expected_product_count") or 0
        ),
        "checked_product_count": int(
            raw.get("checked_product_count") or 0
        ),
        "missing_product_count": int(
            raw.get("missing_product_count") or 0
        ),
        "drift_count": int(raw.get("drift_count") or 0),
        "pricing_matches_approved_policy": (
            raw.get("pricing_matches_approved_policy") is True
        ),
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _buyer_review_readiness_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "candidate_count": int(raw.get("candidate_count") or 0),
        "review_ready_count": int(raw.get("review_ready_count") or 0),
        "blocked_count": int(raw.get("blocked_count") or 0),
        "blocked_reason_counts": (
            raw.get("blocked_reason_counts")
            if isinstance(raw.get("blocked_reason_counts"), dict)
            else {}
        ),
        "canonical_promotion_performed": (
            raw.get("canonical_promotion_performed") is True
        ),
        "outbound_sent": raw.get("outbound_sent") is True,
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _buyer_promotion_plan_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "proposal_count": int(raw.get("proposal_count") or 0),
        "blocked_count": int(raw.get("blocked_count") or 0),
        "blocked_reason_counts": (
            raw.get("blocked_reason_counts")
            if isinstance(raw.get("blocked_reason_counts"), dict)
            else {}
        ),
        "database_write_performed": (
            raw.get("database_write_performed") is True
        ),
        "canonical_promotion_performed": (
            raw.get("canonical_promotion_performed") is True
        ),
        "buy_signal_score_policy": raw.get(
            "buy_signal_score_policy"
        ),
        "outbound_sent": raw.get("outbound_sent") is True,
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _buyer_acquisition_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    automation = (
        raw.get("automation")
        if isinstance(raw.get("automation"), dict)
        else {}
    )
    return {
        "available": True,
        "observed_at": raw.get("generated_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "team_role_count": int(raw.get("team_role_count") or 0),
        "buyer_pool_count": len(raw.get("buyer_pools") or []),
        "demand_gap_count": int(raw.get("demand_gap_count") or 0),
        "priority_target_count": len(raw.get("priority_targets") or []),
        "product_demand_count": int(
            raw.get("product_demand_count") or 0
        ),
        "sellable_product_demand_count": int(
            raw.get("sellable_product_demand_count") or 0
        ),
        "market_validate_product_count": int(
            raw.get("market_validate_product_count") or 0
        ),
        "product_priority_target_count": len(
            raw.get("product_priority_targets") or []
        ),
        "target_buyer_types": list(raw.get("target_buyer_types") or []),
        "buyer_pools": list(raw.get("buyer_pools") or []),
        "supply_gate_diagnostics": (
            raw.get("supply_gate_diagnostics")
            if isinstance(raw.get("supply_gate_diagnostics"), dict)
            else {}
        ),
        "seat_activation_blocker_counts": (
            raw.get("seat_activation_blocker_counts")
            if isinstance(
                raw.get("seat_activation_blocker_counts"), dict
            )
            else {}
        ),
        "live_outbound_send": (
            automation.get("live_outbound_send") is True
        ),
        "buyer_capacity_never_gates_acquisition": (
            raw.get("buyer_capacity_never_gates_acquisition") is True
        ),
        "overflow_remains_empire_owned": (
            raw.get("overflow_remains_empire_owned") is True
        ),
        "canonical_settlement_rail": raw.get(
            "canonical_settlement_rail"
        ),
        "actual_revenue": False,
        "execution_authority": raw.get("execution_authority", "none"),
    }


def _buyer_scout_runtime(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "execution_authority": "none",
        }
    return {
        "available": True,
        "observed_at": raw.get("observed_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "query_count": int(raw.get("query_count") or 0),
        "observation_count": int(raw.get("observation_count") or 0),
        "error_count": int(raw.get("error_count") or 0),
        "outbound_sent": raw.get("outbound_sent") is True,
        "automatic_external_execution": (
            raw.get("automatic_external_execution") is True
        ),
        "execution_authority": raw.get("execution_authority", "none"),
    }


def build_founder_dashboard(repo_root: Path) -> dict[str, Any]:
    runtime = repo_root / "runtime"
    loop_path = runtime / "commercial_loop" / "latest.json"
    astra_path = runtime / "astra" / "latest.json"
    acquisition_path = runtime / "acquisition" / "latest.json"
    source_path = runtime / "source_health" / "latest.json"
    conversion_path = runtime / "conversion" / "latest.json"
    catalog_path = runtime / "commercial_catalog" / "latest.json"
    opportunity_value_path = (
        runtime / "opportunity_factory" / "value_latest.json"
    )
    predictive_intelligence_path = (
        runtime / "predictive_intelligence" / "latest.json"
    )
    economic_memory_path = runtime / "economic_memory" / "latest.json"
    commercial_exchange_runtime_path = (
        runtime / "commercial_exchange" / "latest.json"
    )
    buyer_acquisition_runtime_path = (
        runtime / "buyer_acquisition" / "latest.json"
    )
    buyer_scout_runtime_path = (
        runtime / "buyer_acquisition" / "scout_latest.json"
    )
    buyer_reconciliation_runtime_path = (
        runtime / "buyer_acquisition" / "reconciliation_latest.json"
    )
    buyer_persistence_runtime_path = (
        runtime / "buyer_acquisition" / "persistence_latest.json"
    )
    pricing_verification_runtime_path = (
        runtime
        / "commercial_catalog"
        / "pricing_verification_latest.json"
    )
    buyer_review_readiness_runtime_path = (
        runtime / "buyer_acquisition" / "review_readiness_latest.json"
    )
    buyer_promotion_plan_runtime_path = (
        runtime / "buyer_acquisition" / "promotion_plan_latest.json"
    )
    buyer_scout_runtime_path = (
        runtime / "buyer_acquisition" / "scout_latest.json"
    )

    raw_loop = _read_json(loop_path)
    conveyor = build_conveyor(raw_loop or {"stages": []})

    return {
        "mode": "OBSERVE",
        "side_effects": "none",
        "execution_authority": "none",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commercial_loop": _commercial_loop(raw_loop, loop_path),
        "control_conveyor": conveyor,
        "founder_gate": {
            "required": conveyor.get("authority") == "founder_gate",
            "current_blocker": conveyor.get("current_blocker"),
            "owner_component": conveyor.get("owner_component"),
            "next_event": conveyor.get("next_event"),
            "authority": conveyor.get("authority"),
        },
        "astra": _astra(_read_json(astra_path), astra_path),
        "acquisition": _acquisition(
            _read_json(acquisition_path),
            acquisition_path,
        ),
        "source_health": _source_health(_read_json(source_path), source_path),
        "conversion": _conversion(
            _read_json(conversion_path),
            conversion_path,
        ),
        "commercial_catalog": _commercial_catalog(
            _read_json(catalog_path),
            catalog_path,
        ),
        "opportunity_value": _opportunity_value(
            _read_json(opportunity_value_path),
            opportunity_value_path,
        ),
        "predictive_intelligence": _predictive_intelligence(
            _read_json(predictive_intelligence_path),
            predictive_intelligence_path,
        ),
        "economic_memory": _economic_memory(
            _read_json(economic_memory_path),
            economic_memory_path,
        ),
        "commercial_funnel": build_funnel_runtime(repo_root),
        "revenue_pulse": build_revenue_pulse_runtime(repo_root),
        "market_sweeps_revenue_gps": (
            build_market_sweep_runtime(repo_root)
        ),
        "permit_intelligence": build_permit_intelligence_runtime(repo_root),
        "property_intelligence": build_property_intelligence_runtime(repo_root),
        "private_capital_intelligence": (
            build_private_capital_intelligence_runtime(repo_root)
        ),
        "competitor_audience_intelligence": (
            build_competitor_audience_runtime(repo_root)
        ),
        "competitor_account_research": (
            build_account_research_runtime(repo_root)
        ),
        "competitor_account_briefs": (
            build_account_brief_runtime(repo_root)
        ),
        "buyer_state_evidence": (
            build_buyer_state_runtime(repo_root)
        ),
        "next_best_actions": (
            build_next_best_action_runtime(repo_root)
        ),
        "account_buyer_digital_twins": (
            build_account_twin_runtime(repo_root)
        ),
        "cortex_learning_loop": (
            build_cortex_learning_runtime(repo_root)
        ),
        "competitor_market_scale": (
            build_market_scale_runtime(repo_root)
        ),
        "competitor_market_opportunity": (
            build_market_opportunity_runtime(repo_root)
        ),
        "competitor_ecosystem": (
            build_ecosystem_runtime(repo_root)
        ),
        "competitor_public_review_overlap": (
            build_public_review_overlap_runtime(repo_root)
        ),
        "competitor_search_presence": (
            build_search_presence_runtime(repo_root)
        ),
        "competitor_public_activity": (
            build_public_activity_runtime(repo_root)
        ),
        "competitor_intelligence_feed": (
            build_feed_runtime(repo_root)
        ),
        "recovery_portfolio": {
            "summary": recovery_summary(),
            "products": recovery_product_catalog(),
            "implementation_audit": (
                build_recovery_implementation_audit(repo_root)
            ),
            "marketing_summary": marketing_summary(),
            "marketing_plans": marketing_plan_catalog(),
            "pricing_authority": "none",
            "execution_authority": "none",
            "actual_revenue": False,
        },
        "canonical_execution_plan": build_canonical_phase_plan(),
        "phase_3f_closeout": build_phase_3f_closeout(repo_root),
        "commercial_exchange": build_commercial_exchange_contract(),
        "commercial_exchange_runtime": _commercial_exchange_runtime(
            _read_json(commercial_exchange_runtime_path),
            commercial_exchange_runtime_path,
        ),
        "buyer_acquisition_team": _buyer_acquisition_runtime(
            _read_json(buyer_acquisition_runtime_path),
            buyer_acquisition_runtime_path,
        ),
        "buyer_acquisition_scout": _buyer_scout_runtime(
            _read_json(buyer_scout_runtime_path),
            buyer_scout_runtime_path,
        ),
        "buyer_scout_reconciliation": _buyer_reconciliation_runtime(
            _read_json(buyer_reconciliation_runtime_path),
            buyer_reconciliation_runtime_path,
        ),
        "buyer_scout_persistence": _buyer_persistence_runtime(
            _read_json(buyer_persistence_runtime_path),
            buyer_persistence_runtime_path,
        ),
        "commercial_pricing_verification": _pricing_verification_runtime(
            _read_json(pricing_verification_runtime_path),
            pricing_verification_runtime_path,
        ),
        "buyer_scout_review_readiness": _buyer_review_readiness_runtime(
            _read_json(buyer_review_readiness_runtime_path),
            buyer_review_readiness_runtime_path,
        ),
        "buyer_scout_promotion_plan": _buyer_promotion_plan_runtime(
            _read_json(buyer_promotion_plan_runtime_path),
            buyer_promotion_plan_runtime_path,
        ),
        "buyer_scout": _buyer_scout_runtime(
            _read_json(buyer_scout_runtime_path),
            buyer_scout_runtime_path,
        ),
        "commercial_pricing_proposal": build_launch_pricing_proposal(),
        "phases": _phase_projection(repo_root / "docs" / "BLUEPRINT_V6.md"),
    }
