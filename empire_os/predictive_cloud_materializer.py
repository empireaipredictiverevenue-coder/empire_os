"""Runtime materialization for Predictive Cloud pure algorithm components.

This layer distinguishes:
- component/runtime availability
from
- prediction/economic readiness.

Missing commercial evidence stays UNKNOWN. The materializer never fabricates
probability, revenue, cost, timing, confidence, market share or outcomes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


TREND_OUTPUT = Path(
    "runtime/predictive_cloud/future_trend_latest.json"
)
FORMULA_OUTPUT = Path(
    "runtime/predictive_cloud/formula_latest.json"
)

VALUE_INPUT = Path(
    "runtime/opportunity_factory/value_latest.json"
)
PREDICTIVE_INPUT = Path(
    "runtime/predictive_intelligence/latest.json"
)
RADAR_INPUT = Path(
    "runtime/opportunity_radar/latest.json"
)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_write(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_name(path.name + ".tmp")

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def _available_economic_items(
    value_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for raw in value_snapshot.get("items") or ():
        if not isinstance(raw, Mapping):
            continue

        if str(raw.get("status") or "").upper() != "AVAILABLE":
            continue

        if raw.get("expected_revenue_cents") is None:
            continue

        if raw.get("expected_gross_profit_cents") is None:
            continue

        evidence = raw.get("quant_input_evidence")

        if not isinstance(evidence, Mapping):
            continue

        if not evidence.get("evidence_refs"):
            continue

        rows.append(dict(raw))

    return rows


def refresh_predictive_cloud_materializers(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()

    current = (
        now or datetime.now(timezone.utc)
    ).astimezone(timezone.utc)

    value = _load(root / VALUE_INPUT)
    predictive = _load(root / PREDICTIVE_INPUT)
    radar = _load(root / RADAR_INPUT)

    economic_rows = _available_economic_items(value)

    candidate_count = int(
        value.get("candidate_count")
        or radar.get("candidate_count")
        or 0
    )

    probability_ready = int(
        predictive.get(
            "probability_ready_product_count"
        )
        or 0
    )

    timing_ready = int(
        predictive.get(
            "timing_ready_product_count"
        )
        or 0
    )

    verified_outcomes = int(
        predictive.get("matched_outcome_count")
        or 0
    )

    trend_ready = (
        bool(economic_rows)
        and probability_ready > 0
        and timing_ready > 0
        and verified_outcomes > 0
    )

    trend_blockers: list[str] = []

    if not economic_rows:
        trend_blockers.append(
            "normalized_economic_observations_required"
        )

    if probability_ready <= 0:
        trend_blockers.append(
            "verified_probability_cohort_required"
        )

    if timing_ready <= 0:
        trend_blockers.append(
            "verified_timing_cohort_required"
        )

    if verified_outcomes <= 0:
        trend_blockers.append(
            "verified_terminal_outcomes_required"
        )

    trend = {
        "schema_version": (
            "empire.future_trend_intelligence.runtime.v1"
        ),
        "status": "AVAILABLE",
        "available": True,
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),

        "algorithm_module": (
            "empire_os.future_trend_intelligence"
        ),
        "algorithm_available": True,

        "analysis_executed": False,
        "prediction_ready": trend_ready,

        "evidence_state": (
            "READY_FOR_ANALYSIS"
            if trend_ready
            else "INSUFFICIENT_VERIFIED_EVIDENCE"
        ),

        "candidate_count": candidate_count,
        "normalized_economic_candidate_count": len(
            economic_rows
        ),

        "probability_ready_product_count": (
            probability_ready
        ),
        "timing_ready_product_count": timing_ready,
        "verified_terminal_outcome_count": (
            verified_outcomes
        ),

        "blockers": trend_blockers,

        "llm_probability_used": False,
        "search_score_used_as_probability": False,
        "unknown_is_zero": False,
        "synthetic_economics_used": False,

        "prediction_only": True,
        "actual_revenue": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }

    formula_ready = (
        bool(economic_rows)
        and probability_ready > 0
    )

    formula_blockers: list[str] = []

    if not economic_rows:
        formula_blockers.append(
            "normalized_opportunity_economics_required"
        )

    if probability_ready <= 0:
        formula_blockers.append(
            "verified_probability_inputs_required"
        )

    formula = {
        "schema_version": (
            "empire.predictive_cloud_formula.runtime.v1"
        ),
        "status": "AVAILABLE",
        "available": True,
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),

        "algorithm_module": (
            "empire_os.predictive_cloud_formula"
        ),
        "algorithm_available": True,

        "formula_evaluated": False,
        "prediction_ready": formula_ready,

        "evidence_state": (
            "READY_FOR_FORMULA"
            if formula_ready
            else "INSUFFICIENT_VERIFIED_ECONOMICS"
        ),

        "candidate_count": candidate_count,
        "normalized_economic_candidate_count": len(
            economic_rows
        ),
        "probability_ready_product_count": (
            probability_ready
        ),

        "blockers": formula_blockers,

        "portfolio_expected_revenue_cents": None,
        "portfolio_expected_gross_profit_cents": None,
        "portfolio_risk_adjusted_value_cents": None,

        "unknown_is_zero": False,
        "synthetic_economics_used": False,
        "unverified_pipeline_state_used_as_outcome": False,

        "prediction_only": True,
        "actual_revenue": False,
        "commercial_authority": "none",
        "capital_execution": False,
        "execution_authority": "none",
    }

    _atomic_write(
        root / TREND_OUTPUT,
        trend,
    )

    _atomic_write(
        root / FORMULA_OUTPUT,
        formula,
    )

    return {
        "schema_version": (
            "empire.predictive_cloud.materializer.v1"
        ),
        "status": "AVAILABLE",
        "generated_at": current.isoformat(),

        "future_trend": trend,
        "predictive_cloud_formula": formula,

        "runtime_component_count": 2,
        "prediction_ready_component_count": (
            int(trend_ready)
            + int(formula_ready)
        ),

        "synthetic_economics_generated": False,
        "third_party_service_called": False,
        "external_action_performed": False,
        "execution_authority": "none",
    }
