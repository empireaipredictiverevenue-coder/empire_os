"""Lighthouse/Core Web Vitals evidence parser for Search Intelligence.

This module parses observed Lighthouse JSON. It does not launch a browser,
crawl a URL, or claim field Core Web Vitals. Lab evidence remains explicitly
separate from real-user/field measurements.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PerformanceMetric:
    key: str
    name: str
    value: float | None
    unit: str
    display_value: str | None
    rating: str | None
    source: str = "lighthouse_lab"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_THRESHOLDS: dict[str, tuple[float, float, str]] = {
    "largest-contentful-paint": (2500.0, 4000.0, "ms"),
    "first-contentful-paint": (1800.0, 3000.0, "ms"),
    "cumulative-layout-shift": (0.1, 0.25, "unitless"),
    "total-blocking-time": (200.0, 600.0, "ms"),
    "speed-index": (3400.0, 5800.0, "ms"),
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rating(key: str, value: float | None) -> str | None:
    if value is None or key not in _THRESHOLDS:
        return None
    good, poor, _unit = _THRESHOLDS[key]
    if value <= good:
        return "good"
    if value <= poor:
        return "needs_improvement"
    return "poor"


def _category_score(report: Mapping[str, Any], key: str) -> int | None:
    categories = report.get("categories")
    if not isinstance(categories, Mapping):
        return None
    row = categories.get(key)
    if not isinstance(row, Mapping):
        return None
    score = _number(row.get("score"))
    if score is None:
        return None
    return max(0, min(100, round(score * 100)))


def parse_lighthouse_report(report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        raise ValueError("lighthouse report must be an object")

    audits = report.get("audits")
    if not isinstance(audits, Mapping):
        raise ValueError("lighthouse report audits missing")

    metrics: list[PerformanceMetric] = []
    for key, (good, poor, unit) in _THRESHOLDS.items():
        row = audits.get(key)
        if not isinstance(row, Mapping):
            continue
        value = _number(row.get("numericValue"))
        metrics.append(PerformanceMetric(
            key=key,
            name=str(row.get("title") or key),
            value=value,
            unit=str(row.get("numericUnit") or unit),
            display_value=(
                str(row.get("displayValue"))
                if row.get("displayValue") is not None
                else None
            ),
            rating=_rating(key, value),
        ))

    opportunities: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for key, row in audits.items():
        if not isinstance(row, Mapping):
            continue
        score = _number(row.get("score"))
        details = row.get("details")
        detail_type = (
            str(details.get("type") or "")
            if isinstance(details, Mapping)
            else ""
        )
        item = {
            "key": str(key),
            "title": str(row.get("title") or key),
            "score": score,
            "display_value": (
                str(row.get("displayValue"))
                if row.get("displayValue") is not None
                else None
            ),
        }
        if detail_type == "opportunity":
            savings_ms = None
            if isinstance(details, Mapping):
                savings_ms = _number(
                    details.get("overallSavingsMs")
                )
            item["estimated_savings_ms"] = savings_ms
            opportunities.append(item)
        elif score is not None and score < 1.0:
            diagnostics.append(item)

    opportunities.sort(
        key=lambda row: -float(row.get("estimated_savings_ms") or 0.0)
    )

    return {
        "schema_version": "empire.search.performance.v1",
        "available": True,
        "measurement_kind": "lab",
        "source": "lighthouse",
        "field_core_web_vitals_available": False,
        "field_data_invented": False,
        "fetch_time": report.get("fetchTime"),
        "final_url": report.get("finalDisplayedUrl") or report.get("finalUrl"),
        "lighthouse_version": report.get("lighthouseVersion"),
        "category_scores": {
            "performance": _category_score(report, "performance"),
            "accessibility": _category_score(report, "accessibility"),
            "best_practices": _category_score(report, "best-practices"),
            "seo": _category_score(report, "seo"),
        },
        "lab_metrics": [metric.as_dict() for metric in metrics],
        "opportunities": opportunities[:25],
        "diagnostics": diagnostics[:50],
        "execution_allowed": False,
        "browser_execution": False,
        "limitations": [
            "lab_measurement_not_field_cwv",
            "single_report_not_longitudinal",
            "no_real_user_percentile_claim",
        ],
    }


def lighthouse_parser_status() -> dict[str, Any]:
    return {
        "available": True,
        "mode": "OBSERVE",
        "parser_available": True,
        "runner_available": False,
        "runner_activation_required": True,
        "browser_execution": False,
        "field_data_adapter_available": False,
        "reason": "parser_ready_runner_not_activated",
    }
