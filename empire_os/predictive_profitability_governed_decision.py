"""Governed Predictive Revenue decision support, not dispatch or accounting.

Links existing *global* canonical Pulse/Economic Memory aggregates to a
hypothetical opportunity-specific economics book WITHOUT equating scopes.
Realized company GP cannot calibrate an unregistered opportunity forecast.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_profitability_playbooks import SCHEMA as BOOK_SCHEMA

SCHEMA = "empire.predictive_revenue.governed_profitability_decision.v1"
TRUTH_SCHEMA = "empire.predictive_revenue.economic_truth_boundary.v1"
MAX_JSON = 3_000_000
MAX_AGE = timedelta(hours=8)
MAX_SOURCE_SKEW = timedelta(hours=2)


def _truth_hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": TRUTH_SCHEMA, "status": "ECONOMIC_TRUTH_SOURCE_HOLD",
        "mode": "OBSERVE", "hold_code": reason,
        "global_recognized_revenue_minor_from_pulse": None,
        "global_realized_gp_minor_from_pulse": None,
        "economic_memory_outcome_conditioned_count": None,
        "economic_memory_calibration_evidence_count": None,
        "original_pilot_to_global_profit_attribution_verified": False,
        "single_opportunity_realized_gp_minor": None,
        "original_forecast_prediction_error_minor": None,
        "source_owner_payment_authentication_independently_proven": False,
        "economic_memory_learning_applied": False,
        "execution_authority": "none",
        "outbound_sent": False, "database_writes": False,
    }


def review_existing_global_economics_truth(
    pulse: Mapping[str, Any], memory: Mapping[str, Any], *,
    as_of: datetime,
) -> dict[str, Any]:
    """Project only vetted safe scalar aggregates; no raw episodes or tenant IDs."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware current clock required")
    now = as_of.astimezone(timezone.utc)
    if not isinstance(pulse, Mapping) or not isinstance(memory, Mapping):
        return _truth_hold("ORIGINAL_AGGREGATES_REQUIRED")
    if (pulse.get("schema_version") != "empire.revenue-pulse.v3"
            or pulse.get("mode") != "OBSERVE"
            or pulse.get("execution_authority") != "none"
            or pulse.get("execution_allowed") is not False
            or pulse.get("payment_mutation") is not False
            or pulse.get("revenue_mutation") is not False
            or pulse.get("accounting_mutation") is not False):
        return _truth_hold("UNTRUSTED_REVENUE_PULSE_AUTHORITY")
    if (memory.get("schema_version") != "empire.economic_memory.v1"
            or memory.get("mode") != "OBSERVE"
            or memory.get("execution_authority") != "none"
            or memory.get("accounting_authority") != "none"
            or memory.get("commercial_authority") != "none"
            or memory.get("model_weight_mutation_authorized") is not False
            or memory.get("forecast_used_as_outcome") is not False
            or memory.get("synthetic_outcomes_allowed") is not False
            or memory.get("promoted_learning") is not False
            or memory.get("shadow_decisions_receive_causal_credit") is not False):
        return _truth_hold("UNTRUSTED_ECONOMIC_MEMORY_AUTHORITY")
    try:
        pulse_at = _time(pulse.get("generated_at"))
        memory_at = _time(memory.get("generated_at"))
    except ValueError:
        return _truth_hold("INVALID_OR_UNAWARE_SOURCE_TIME")
    if (not timedelta(0) <= now-pulse_at <= MAX_AGE
            or not timedelta(0) <= now-memory_at <= MAX_AGE
            or abs(pulse_at-memory_at) > MAX_SOURCE_SKEW):
        return _truth_hold("SOURCE_EPOCH_STALE_FUTURE_OR_SKEWED")

    truth = pulse.get("recognized_revenue_truth")
    if not isinstance(truth, Mapping) or truth.get("forecast_included_in_truth") is not False:
        return _truth_hold("FORECAST_LEAKED_INTO_REVENUE_TRUTH")
    recognized = truth.get("recognized_revenue_cents")
    gross_profit = truth.get("realized_gp_cents")
    if (type(recognized) is not int or not 0 <= recognized <= 10**14
            or type(gross_profit) is not int or not -10**14 <= gross_profit <= 10**14):
        return _truth_hold("INVALID_CANONICAL_AGGREGATE_ECONOMICS")
    outcomes = memory.get("outcome_conditioned_memory_count")
    calibrations = memory.get("calibration_evidence_count")
    decision_links = memory.get("decision_outcome_attribution_count")
    if any(type(n) is not int or not 0 <= n <= 100_000 for n in
           (outcomes, calibrations, decision_links)):
        return _truth_hold("INVALID_ECONOMIC_MEMORY_COUNTS")
    checks = (
        ("outcome_conditioned_memories", outcomes),
        ("calibration_evidence", calibrations),
        ("decision_outcome_attributions", decision_links),
    )
    if any(not isinstance(memory.get(key), list)
           or len(memory[key]) != total or total > 100_000 for key, total in checks):
        return _truth_hold("ECONOMIC_MEMORY_COUNT_ROWS_DISAGREE")
    return {
        **_truth_hold("NONE"),
        "status": "GLOBAL_ECONOMIC_SNAPSHOT_REVIEWED_NO_OPPORTUNITY_ATTRIBUTION",
        "hold_code": None,
        "source_pulse_epoch": pulse_at.isoformat(),
        "source_economic_memory_epoch": memory_at.isoformat(),
        "source_snapshots_are_same_business_cohort": False,
        "global_recognized_revenue_minor_from_pulse": recognized,
        "global_realized_gp_minor_from_pulse": gross_profit,
        "economic_memory_outcome_conditioned_count": outcomes,
        "economic_memory_calibration_evidence_count": calibrations,
        "economic_memory_decision_attribution_count": decision_links,
        "global_actual_gp_is_opportunity_forecast_error": False,
        "global_actual_gp_is_product_level_profit": False,
    }


def review_existing_global_economics_truth_runtime(
    repo_root: str | Path, *, as_of: datetime,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    found: dict[str, Any] = {}
    for name, rel in (
        ("pulse", "runtime/revenue_pulse/latest.json"),
        ("memory", "runtime/economic_memory/latest.json"),
    ):
        path = root / rel
        try:
            if ((root / "runtime").is_symlink() or path.parent.is_symlink()
                    or path.is_symlink() or not path.is_file()
                    or not 0 < path.stat().st_size <= MAX_JSON):
                return _truth_hold("UNAVAILABLE_"+name.upper()+"_SOURCE")
            found[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            return _truth_hold("UNREADABLE_"+name.upper()+"_SOURCE")
    return review_existing_global_economics_truth(
        found["pulse"], found["memory"], as_of=as_of,
    )


def build_profitability_governed_decision(
    book: Mapping[str, Any], truth: Mapping[str, Any],
) -> dict[str, Any]:
    """Create explanation and owner gates, never internal dispatch instructions."""
    if (not isinstance(book, Mapping) or
            book.get("schema_version") != BOOK_SCHEMA
            or book.get("status") != "HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY"
            or book.get("mode") != "OBSERVE"
            or book.get("execution_authority") != "none"
            or book.get("original_forecast_registered") is not False
            or book.get("actual_gross_profit_verified") is not False
            or book.get("scenario_set_exhaustive_or_calibrated") is not False
            or book.get("spend_authorized") is not False):
        raise ValueError("only governed hypothetical economics books are supported")
    if not isinstance(truth, Mapping) or truth.get("schema_version") != TRUTH_SCHEMA:
        raise ValueError("reviewed original economics truth source required")
    if truth.get("execution_authority") != "none":
        raise ValueError("unexpected source execution authority")
    rows = book.get("scenario_rows")
    if (not isinstance(rows, list) or len(rows) != 3 or
            [row.get("scenario_key") for row in rows if isinstance(row, Mapping)]
            != ["downside", "base", "upside"]):
        raise ValueError("complete downside/base/upside book required")
    base = rows[1]
    relevant = (
        "required_conversion_rate_to_break_even_hypothetical",
        "required_unit_price_minor_to_break_even_hypothetical",
        "expected_operating_profit_minor_hypothetical",
    )
    if any(type(base.get(name)) not in (int, float, type(None)) for name in relevant):
        raise ValueError("invalid original break-even figures")
    raw_playbooks = book.get("playbooks")
    if not isinstance(raw_playbooks, list) or len(raw_playbooks) > 30:
        raise ValueError("bounded owned playbooks required")
    owner_actions = []
    seen = set()
    for entry in raw_playbooks:
        if (not isinstance(entry, Mapping)
                or entry.get("automatic_execution_allowed") is not False):
            raise ValueError("playbook execution gate missing")
        key, owner, trigger, step = (
            entry.get("playbook_key"), entry.get("owner"),
            entry.get("trigger"), entry.get("next_step"),
        )
        if (not all(isinstance(v, str) and 1 <= len(v) <= 170
                    for v in (key, owner, trigger, step)) or key in seen):
            raise ValueError("invalid or duplicate original playbook")
        seen.add(key)
        owner_actions.append({
            "playbook_key": key, "existing_owner": owner,
            "trigger": trigger, "research_action": step,
            "execution_approved": False, "sent_to_execution_bus": False,
        })
    truth_ok = (
        truth.get("status")
        == "GLOBAL_ECONOMIC_SNAPSHOT_REVIEWED_NO_OPPORTUNITY_ATTRIBUTION"
        and truth.get("original_pilot_to_global_profit_attribution_verified") is False
        and truth.get("source_owner_payment_authentication_independently_proven") is False
    )
    if not truth_ok and truth.get("status") != "ECONOMIC_TRUTH_SOURCE_HOLD":
        raise ValueError("untrusted or overstated economic truth")
    if not truth_ok:
        owner_actions.insert(0, {
            "playbook_key": "RESTORE_CANONICAL_ECONOMIC_TRUTH",
            "existing_owner": "finance_and_economic_memory",
            "trigger": truth.get("hold_code") or "UNTRUSTED_SOURCE",
            "research_action": "REVIEW_ORIGINAL_REVENUE_PULSE_AND_ECONOMIC_MEMORY_SOURCE_CUSTODY",
            "execution_approved": False, "sent_to_execution_bus": False,
        })
    cash_hold = book.get("worst_case_cash_exposure_above_assumed_limit")
    worst = book.get("hypothetical_worst_operating_profit_minor")
    if type(cash_hold) is not bool or type(worst) not in (int, float):
        raise ValueError("book has incomplete downside and liquidity constraints")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "HYPOTHETICAL_DECISION_RESEARCH_ONLY",
        "opportunity_key": book["opportunity_key"],
        "original_pilot_design_sha256": book.get("original_pilot_design_sha256"),
        "economic_scenario_horizon_days": book.get("horizon_days"),
        "source_truth_review_status": truth.get("status"),
        "company_wide_recognized_revenue_minor_separate": (
            truth["global_recognized_revenue_minor_from_pulse"] if truth_ok else None
        ),
        "company_wide_realized_gp_minor_separate": (
            truth["global_realized_gp_minor_from_pulse"] if truth_ok else None
        ),
        "opportunity_realized_gp_minor": None,
        "original_pilot_prediction_error_minor": None,
        "original_prediction_registry_matched": False,
        "source_owner_payment_authenticated_for_opportunity": False,
        "calibrated_probabilities_available": False,
        "hypothetical_base_operating_profit_minor": base["expected_operating_profit_minor_hypothetical"],
        "hypothetical_base_break_even_conversion_rate": base["required_conversion_rate_to_break_even_hypothetical"],
        "hypothetical_base_break_even_unit_price_minor": base["required_unit_price_minor_to_break_even_hypothetical"],
        "negative_downside_hypothesis": worst < 0,
        "cash_cap_exceeded_in_hypothesis": cash_hold,
        "decision_release_gate": "HOLD_NO_REGISTERED_PREDICTION_OR_AUTHENTICATED_PAID_OUTCOME",
        "playbook_owner_actions": owner_actions,
        "playbook_count": len(owner_actions),
        "opportunity_level_profitability_rank_authorized": False,
        "scenario_recommendation_is_execution_authority": False,
        "automatic_spend_or_pricing_change": False,
        "economic_memory_feedback_written": False,
        "outbound_sent": False, "database_writes": False,
        "execution_authority": "none",
    }
