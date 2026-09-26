"""Observed rank-history analysis for Search Intelligence.

Provider-neutral: observations may originate from Search Fabric, Search
Console, OpenSEO-style adapters or other reviewed sources. No missing
rank/date is synthesized.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class RankObservation:
    query: str
    url: str
    observed_at: str
    position: int
    engine: str
    source: str
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("rank observation query required")
        if not self.url.strip():
            raise ValueError("rank observation url required")
        if self.position < 1:
            raise ValueError("rank observation position must be positive")
        if not self.engine.strip():
            raise ValueError("rank observation engine required")
        if not self.source.strip():
            raise ValueError("rank observation source required")
        if not self.provenance:
            raise ValueError("rank observation provenance required")
        _parse_time(self.observed_at)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_time(value: str) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise ValueError("observed_at required")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc


def analyse_rank_history(
    observations: Iterable[RankObservation],
    *,
    query: str,
    url: str | None = None,
    engine: str | None = None,
) -> dict[str, Any]:
    target_query = str(query or "").strip().casefold()
    if not target_query:
        raise ValueError("query required")
    target_url = str(url or "").strip()
    target_engine = str(engine or "").strip().casefold()

    rows = [
        item
        for item in observations
        if item.query.strip().casefold() == target_query
        and (not target_url or item.url.strip() == target_url)
        and (
            not target_engine
            or item.engine.strip().casefold() == target_engine
        )
    ]
    rows.sort(key=lambda item: _parse_time(item.observed_at))

    if not rows:
        return {
            "available": False,
            "query": query,
            "url": target_url or None,
            "engine": engine or None,
            "reason": "no_observed_rank_history",
            "observations": [],
            "latest_position": None,
            "previous_position": None,
            "position_change": None,
            "best_position": None,
            "worst_position": None,
            "trend": "unknown",
            "synthetic_points": 0,
        }

    latest = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    change = (
        previous.position - latest.position
        if previous is not None
        else None
    )
    best = min(item.position for item in rows)
    worst = max(item.position for item in rows)

    if change is None:
        trend = "insufficient_history"
    elif change > 0:
        trend = "improving"
    elif change < 0:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "available": True,
        "query": latest.query,
        "url": target_url or None,
        "engine": engine or None,
        "observation_count": len(rows),
        "first_observed_at": rows[0].observed_at,
        "latest_observed_at": latest.observed_at,
        "latest_position": latest.position,
        "previous_position": (
            previous.position if previous is not None else None
        ),
        "position_change": change,
        "best_position": best,
        "worst_position": worst,
        "trend": trend,
        "sources": sorted({item.source for item in rows}),
        "provenance": sorted({
            ref
            for item in rows
            for ref in item.provenance
        }),
        "observations": [item.as_dict() for item in rows],
        "synthetic_points": 0,
        "forecast_position": None,
        "execution_allowed": False,
    }
