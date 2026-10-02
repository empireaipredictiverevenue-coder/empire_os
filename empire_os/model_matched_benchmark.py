"""Deterministic matched-pair benchmark utilities for local planner models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    covered_groups: int
    total_groups: int
    coverage: float
    output_nonempty: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "covered_groups": self.covered_groups,
            "total_groups": self.total_groups,
            "coverage": self.coverage,
            "output_nonempty": self.output_nonempty,
        }


def score_case(
    *,
    case_id: str,
    output: str,
    required_groups: Iterable[Iterable[str]],
) -> CaseScore:
    text = " ".join(str(output or "").lower().split())
    groups = [tuple(str(term).lower() for term in group) for group in required_groups]
    covered = sum(
        1 for group in groups
        if group and any(term in text for term in group)
    )
    total = len(groups)
    return CaseScore(
        case_id=str(case_id),
        covered_groups=covered,
        total_groups=total,
        coverage=round(covered / total, 6) if total else 0.0,
        output_nonempty=bool(text),
    )


def summarize_model(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = [dict(row) for row in rows]
    if not items:
        return {
            "sample_count": 0,
            "mean_coverage": None,
            "mean_latency_ms": None,
            "successful_calls": 0,
        }
    coverages = [float(row.get("coverage") or 0.0) for row in items]
    latencies = [
        float(row["latency_ms"])
        for row in items
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    return {
        "sample_count": len(items),
        "mean_coverage": round(sum(coverages) / len(coverages), 6),
        "mean_latency_ms": (
            round(sum(latencies) / len(latencies), 3)
            if len(latencies) == len(items) else None
        ),
        "successful_calls": sum(bool(row.get("ok")) for row in items),
    }
