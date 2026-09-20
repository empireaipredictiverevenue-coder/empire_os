"""Observed local-search / Maps-grid visibility analysis.

No grid cells, ranks, reviews, ratings or GBP attributes are synthesized.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Iterable


@dataclass(frozen=True)
class LocalGridObservation:
    query: str
    latitude: float
    longitude: float
    observed_at: str
    engine: str
    provenance: tuple[str, ...]
    position: int | None = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("local grid query required")
        if not -90 <= float(self.latitude) <= 90:
            raise ValueError("latitude out of range")
        if not -180 <= float(self.longitude) <= 180:
            raise ValueError("longitude out of range")
        if self.position is not None and self.position < 1:
            raise ValueError("local grid position must be positive")
        if not self.engine.strip():
            raise ValueError("local grid engine required")
        if not str(self.observed_at or "").strip():
            raise ValueError("local grid observed_at required")
        if not self.provenance:
            raise ValueError("local grid provenance required")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyse_local_grid(
    observations: Iterable[LocalGridObservation],
    *,
    query: str,
    engine: str | None = None,
) -> dict[str, Any]:
    target_query = str(query or "").strip().casefold()
    if not target_query:
        raise ValueError("query required")
    target_engine = str(engine or "").strip().casefold()

    rows = [
        row
        for row in observations
        if row.query.strip().casefold() == target_query
        and (
            not target_engine
            or row.engine.strip().casefold() == target_engine
        )
    ]

    if not rows:
        return {
            "available": False,
            "query": query,
            "engine": engine or None,
            "reason": "no_observed_local_grid_evidence",
            "observed_points": 0,
            "ranked_points": 0,
            "unknown_points": 0,
            "top3_share": None,
            "top10_share": None,
            "median_observed_position": None,
            "synthetic_points": 0,
            "points": [],
        }

    ranked = [row for row in rows if row.position is not None]
    unknown = [row for row in rows if row.position is None]
    ranked_count = len(ranked)

    top3 = (
        sum(1 for row in ranked if row.position <= 3) / ranked_count
        if ranked_count
        else None
    )
    top10 = (
        sum(1 for row in ranked if row.position <= 10) / ranked_count
        if ranked_count
        else None
    )
    median_position = (
        float(median([row.position for row in ranked if row.position]))
        if ranked_count
        else None
    )

    weak_points = [
        row.as_dict()
        for row in ranked
        if row.position is not None and row.position > 10
    ]

    return {
        "available": True,
        "query": rows[0].query,
        "engine": engine or None,
        "observed_points": len(rows),
        "ranked_points": ranked_count,
        "unknown_points": len(unknown),
        "top3_share": round(top3, 4) if top3 is not None else None,
        "top10_share": round(top10, 4) if top10 is not None else None,
        "median_observed_position": median_position,
        "weak_point_count": len(weak_points),
        "weak_points": weak_points,
        "sources": sorted({row.engine for row in rows}),
        "provenance": sorted({
            ref
            for row in rows
            for ref in row.provenance
        }),
        "synthetic_points": 0,
        "points": [row.as_dict() for row in rows],
        "execution_allowed": False,
    }
