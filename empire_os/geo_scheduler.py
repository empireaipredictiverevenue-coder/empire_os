"""Adaptive geographic acquisition scheduler."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

from empire_os.geo_registry import GeoMarket


def recent_market_stats(
    log_path: Path,
    *,
    source: str,
    max_lines: int = 5000,
) -> dict[str, dict[str, float]]:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return {}
    lines = lines[-max_lines:]
    current_start: dict[str, Any] | None = None
    rows: dict[str, dict[str, float]] = defaultdict(
        lambda: {"runs": 0.0, "accepted": 0.0, "errors": 0.0}
    )
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if item.get("msg") == "crawler_run_start":
            current_start = item
            continue
        if item.get("msg") != "crawler_run_done" or not current_start:
            continue
        if str(current_start.get("source") or "") != source:
            current_start = None
            continue
        metro = str(current_start.get("metro") or "").strip()
        if metro:
            stat = rows[metro]
            stat["runs"] += 1
            stat["accepted"] += float(item.get("accepted") or 0)
            stat["errors"] += float(item.get("errors") or 0)
        current_start = None
    return dict(rows)


def _score(market: GeoMarket, stat: dict[str, float] | None) -> float:
    if not stat or stat.get("runs", 0) <= 0:
        return market.base_priority
    runs = max(1.0, float(stat.get("runs") or 0))
    accepted = max(0.0, float(stat.get("accepted") or 0))
    errors = max(0.0, float(stat.get("errors") or 0))
    yield_per_run = min(25.0, accepted / runs)
    error_rate = min(1.0, errors / runs)
    experience = min(0.4, runs * 0.02)
    return round(
        market.base_priority
        + (yield_per_run / 25.0) * 2.0
        + experience
        - error_rate * 1.5,
        6,
    )


def choose_market(
    markets: Iterable[GeoMarket],
    *,
    state: dict[str, Any],
    source: str,
    log_path: Path,
) -> dict[str, Any]:
    values = tuple(markets)
    if not values:
        raise ValueError("no enabled acquisition markets")
    cursor = int(
        state.get("next_market_index",
                  state.get("next_metro_index", state.get("next_index", 0)))
        or 0
    ) % len(values)
    cycle = int(state.get("geo_cycle_count") or 0)
    stats = recent_market_stats(log_path, source=source)

    # Deterministic 20% exploration keeps new geographies from starving.
    explore = cycle % 5 == 0 or not stats
    if explore:
        selected_index = cursor
        policy = "explore"
    else:
        ranked = [
            (_score(market, stats.get(market.metro)), -idx, idx, market)
            for idx, market in enumerate(values)
        ]
        ranked.sort(reverse=True, key=lambda row: (row[0], row[1]))
        selected_index = ranked[0][2]
        policy = "exploit"

    market = values[selected_index]
    next_cursor = (cursor + 1) % len(values)
    return {
        "market": market,
        "market_index": selected_index,
        "next_market_index": next_cursor,
        "geo_cycle_count": cycle + 1,
        "policy": policy,
        "score": _score(market, stats.get(market.metro)),
        "recent_stats": stats.get(market.metro) or {
            "runs": 0.0,
            "accepted": 0.0,
            "errors": 0.0,
        },
    }
