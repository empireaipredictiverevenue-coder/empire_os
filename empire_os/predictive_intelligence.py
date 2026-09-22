"""Verified-cohort Predictive Intelligence for Quant inputs.

Only canonical commercial outcomes may update the cohort. The module does not
derive candidate probability from search volume, generic opportunity scores,
LLM prose, or unverified pipeline state.

Product-specific estimates are emitted only when the outcome row's product_id
can be mapped to a verified catalog product_code. Unsupported fields stay
UNKNOWN.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Callable, Mapping, Sequence

from empire_os.quant_brain import update_beta_posterior


Request = Callable[..., Any]
OUTPUT = Path("runtime/predictive_intelligence/latest.json")
CATALOG = Path("runtime/commercial_catalog/latest.json")

TERMINAL_SUCCESS = frozenset({"won"})
TERMINAL_FAILURE = frozenset({"lost", "no_response"})
TERMINAL = TERMINAL_SUCCESS | TERMINAL_FAILURE


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_ts(value: Any) -> datetime | None:
    raw = _clean(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _wilson_interval(
    successes: int,
    trials: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    if trials <= 0:
        return (0.0, 1.0)
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denom
    spread = (
        z
        * math.sqrt(
            (p * (1.0 - p) / trials)
            + (z2 / (4.0 * trials * trials))
        )
        / denom
    )
    return (
        max(0.0, center - spread),
        min(1.0, center + spread),
    )


def _catalog_product_map(
    catalog: Mapping[str, Any],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in catalog.get("products") or []:
        if not isinstance(row, Mapping):
            continue
        product_id = _clean(row.get("product_id"))
        product_code = _clean(row.get("product_code"))
        if not product_id or not product_code:
            continue
        if str(row.get("catalog_state") or "").upper() != "VERIFIED":
            continue
        if str(row.get("version_state") or "").upper() != "VERIFIED":
            continue
        mapping[product_id] = product_code
    return mapping


def _time_to_revenue_days(
    rows: Sequence[Mapping[str, Any]],
) -> list[float]:
    durations: list[float] = []
    for row in rows:
        if row.get("actual_revenue") is not True:
            continue
        start = _parse_ts(
            row.get("fulfilment_created_at")
            or row.get("commercial_started_at")
        )
        end = _parse_ts(row.get("revenue_recognized_at"))
        if start is None or end is None or end < start:
            continue
        durations.append(
            (end - start).total_seconds() / 86400.0
        )
    return durations


def build_product_estimate(
    product_code: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    min_terminal_samples: int = 20,
    min_timing_samples: int = 8,
) -> dict[str, Any]:
    terminal = [
        row
        for row in rows
        if _clean(row.get("conversion_outcome")).lower() in TERMINAL
    ]
    successes = sum(
        _clean(row.get("conversion_outcome")).lower()
        in TERMINAL_SUCCESS
        for row in terminal
    )
    failures = len(terminal) - successes

    probability_available = len(terminal) >= max(
        1, int(min_terminal_samples)
    )
    probability = uncertainty = confidence = None
    interval_low = interval_high = None
    posterior = None

    if probability_available:
        posterior_obj = update_beta_posterior(
            prior_alpha=1.0,
            prior_beta=1.0,
            successes=successes,
            failures=failures,
            verified_real_outcomes=True,
        )
        posterior = posterior_obj.as_dict()
        probability = round(
            float(posterior_obj.mean_probability),
            6,
        )
        low, high = _wilson_interval(successes, len(terminal))
        interval_low = round(low, 6)
        interval_high = round(high, 6)
        interval_width = max(0.0, min(1.0, high - low))
        uncertainty = round(interval_width / 2.0, 6)
        confidence = round(1.0 - interval_width, 6)

    durations = _time_to_revenue_days(rows)
    timing_available = len(durations) >= max(1, int(min_timing_samples))
    time_to_revenue_days = (
        round(float(median(durations)), 4)
        if timing_available
        else None
    )

    refs = [
        "canonical:commercial_outcomes",
        "canonical:fulfilment_orders",
    ]
    if any(row.get("actual_revenue") is True for row in rows):
        refs.append("canonical:commercial_events:revenue_recognized")

    blockers: list[str] = []
    if not probability_available:
        blockers.append("insufficient_verified_terminal_outcomes")
    if not timing_available:
        blockers.append("insufficient_verified_time_to_revenue_samples")

    return {
        "product_code": product_code,
        "terminal_outcome_count": len(terminal),
        "success_count": successes,
        "failure_count": failures,
        "probability_success": probability,
        "probability_available": probability_available,
        "posterior": posterior,
        "wilson_interval_95": {
            "low": interval_low,
            "high": interval_high,
        },
        "uncertainty": uncertainty,
        "uncertainty_semantics": (
            "half_width_of_95pct_wilson_interval"
            if probability_available
            else None
        ),
        "confidence": confidence,
        "confidence_semantics": (
            "precision_proxy_one_minus_95pct_wilson_interval_width"
            if probability_available
            else None
        ),
        "time_to_revenue_days": time_to_revenue_days,
        "time_to_revenue_available": timing_available,
        "time_to_revenue_sample_count": len(durations),
        "time_to_revenue_semantics": (
            "median_verified_fulfilment_created_to_revenue_recognized_days"
            if timing_available
            else None
        ),
        "blockers": blockers,
        "evidence_refs": refs,
        "candidate_probability_is_product_cohort_baseline": True,
        "candidate_specific_causal_probability_claimed": False,
        "prediction_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def build_predictive_intelligence_snapshot(
    outcomes: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, Any],
    *,
    min_terminal_samples: int = 20,
    min_timing_samples: int = 8,
) -> dict[str, Any]:
    product_map = _catalog_product_map(catalog)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    unmatched = 0

    for row in outcomes:
        if not isinstance(row, Mapping):
            continue
        product_id = _clean(row.get("product_id"))
        product_code = product_map.get(product_id)
        if not product_code:
            unmatched += 1
            continue
        grouped[product_code].append(row)

    estimates = {
        code: build_product_estimate(
            code,
            rows,
            min_terminal_samples=min_terminal_samples,
            min_timing_samples=min_timing_samples,
        )
        for code, rows in sorted(grouped.items())
    }

    return {
        "schema_version": "empire.predictive_intelligence.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_outcome_count": len(outcomes),
        "matched_outcome_count": sum(len(v) for v in grouped.values()),
        "unmatched_outcome_count": unmatched,
        "verified_catalog_product_count": len(set(product_map.values())),
        "product_estimates": estimates,
        "probability_ready_product_count": sum(
            row["probability_available"] is True
            for row in estimates.values()
        ),
        "timing_ready_product_count": sum(
            row["time_to_revenue_available"] is True
            for row in estimates.values()
        ),
        "minimum_terminal_samples": max(1, int(min_terminal_samples)),
        "minimum_timing_samples": max(1, int(min_timing_samples)),
        "probability_source": "verified_terminal_commercial_outcomes_only",
        "search_scores_used": False,
        "llm_probability_used": False,
        "unverified_pipeline_state_used_as_outcome": False,
        "prediction_only": True,
        "model_weight_mutation": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def fetch_outcomes(
    request: Request,
    *,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    bounded = max(1, min(int(limit), 1000))
    payload = request(
        "POST",
        "/rest/v1/rpc/get_commercial_outcome_feedback",
        payload={"p_limit": bounded},
    ) or []
    if isinstance(payload, Mapping):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("commercial outcome feedback RPC must return a list")
    return [dict(row) for row in payload if isinstance(row, Mapping)]


def fetch_catalog(
    request: Request,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    bounded = max(1, min(int(limit), 500))
    payload = request(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        payload={"p_product_code": None, "p_limit": bounded},
    ) or []
    if isinstance(payload, Mapping):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("commercial product catalog RPC must return a list")
    return {
        "products": [
            dict(row)
            for row in payload
            if isinstance(row, Mapping)
        ]
    }


def _fresh_snapshot(
    path: Path,
    *,
    max_age_seconds: int,
) -> dict[str, Any] | None:
    payload = _read(path)
    generated = _parse_ts(payload.get("generated_at"))
    if generated is None:
        return None
    age = (
        datetime.now(timezone.utc) - generated
    ).total_seconds()
    if age < 0 or age > max(0, int(max_age_seconds)):
        return None
    return payload


def refresh_predictive_intelligence(
    repo_root: str | Path,
    *,
    request: Request,
    min_terminal_samples: int = 20,
    min_timing_samples: int = 8,
    max_age_seconds: int = 300,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    path = root / OUTPUT
    fresh = _fresh_snapshot(
        path,
        max_age_seconds=max_age_seconds,
    )
    if fresh is not None:
        return {
            **fresh,
            "reused_existing_snapshot": True,
        }

    catalog = _read(root / CATALOG)
    if not catalog.get("products"):
        catalog = fetch_catalog(request)
    outcomes = fetch_outcomes(request)
    payload = build_predictive_intelligence_snapshot(
        outcomes,
        catalog,
        min_terminal_samples=min_terminal_samples,
        min_timing_samples=min_timing_samples,
    )
    payload["reused_existing_snapshot"] = False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
