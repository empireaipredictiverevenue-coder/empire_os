"""US-primary adaptive geographic acquisition scheduler."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

from empire_os.geo_registry import GeoMarket


SOURCE_COUNTRIES: dict[str, frozenset[str] | None] = {
    "overpass": None,
    "biz_search": None,
    "reddit": None,
    "nws_alerts": frozenset({"US"}),
    "courtlistener": frozenset({"US"}),
    "permits": frozenset({"US"}),
    "chicago_311": frozenset({"US"}),
    "nyc_hpd": frozenset({"US"}),
    "recc_solar": frozenset({"GB"}),
}

SOURCE_FIXED_MARKET_IDS = {
    "permits": "US-NY",
    "nyc_hpd": "US-NY",
    "chicago_311": "US-IL",
}

# Deterministic 80/20 policy for globally compatible sources.
US_PRIMARY_PATTERN = ("US", "US", "US", "US", "INTL")


def recent_market_stats(
    log_path: Path,
    *,
    source: str,
    max_lines: int = 5000,
) -> dict[str, dict[str, float]]:
    try:
        lines = log_path.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
    except OSError:
        return {}

    current_start = None
    rows = defaultdict(
        lambda: {
            "runs": 0.0,
            "accepted": 0.0,
            "errors": 0.0,
        }
    )

    for raw in lines[-max_lines:]:
        try:
            item = json.loads(raw)
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


def _score(
    market: GeoMarket,
    stat: dict[str, float] | None,
) -> float:
    if not stat or stat.get("runs", 0) <= 0:
        return market.base_priority

    runs = max(1.0, float(stat.get("runs") or 0))
    accepted = max(0.0, float(stat.get("accepted") or 0))
    errors = max(0.0, float(stat.get("errors") or 0))

    yield_per_run = min(25.0, accepted / runs)
    error_rate = min(1.0, errors / runs)
    experience = min(0.25, runs * 0.01) * (1.0 - error_rate)

    return round(
        market.base_priority
        + (yield_per_run / 25.0) * 2.0
        + experience
        - error_rate * 2.0,
        6,
    )


def _compatible(
    markets: tuple[GeoMarket, ...],
    source: str,
) -> tuple[GeoMarket, ...]:
    fixed_id = SOURCE_FIXED_MARKET_IDS.get(source)

    if fixed_id:
        fixed = tuple(m for m in markets if m.market_id == fixed_id)
        if fixed:
            return fixed

    allowed = SOURCE_COUNTRIES.get(source)
    if allowed is None:
        return markets

    return tuple(
        m for m in markets
        if m.country_code in allowed
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

    compatible = _compatible(values, source)
    if not compatible:
        raise RuntimeError(
            f"no compatible acquisition market for source={source}"
        )

    cycle = int(state.get("geo_cycle_count") or 0)
    stats = recent_market_stats(log_path, source=source)

    raw = state.get("country_market_cursors")
    cursors = (
        {str(k): int(v) for k, v in raw.items()}
        if isinstance(raw, dict)
        else {}
    )

    fixed_id = SOURCE_FIXED_MARKET_IDS.get(source)

    if fixed_id:
        market = compatible[0]
        selected_index = values.index(market)
        target_bucket = (
            "US" if market.country_code == "US" else "INTL"
        )
        policy = "source_fixed_geography"

    else:
        desired = US_PRIMARY_PATTERN[
            cycle % len(US_PRIMARY_PATTERN)
        ]

        us = tuple(
            m for m in compatible
            if m.country_code == "US"
        )
        intl = tuple(
            m for m in compatible
            if m.country_code != "US"
        )

        if desired == "US" and us:
            bucket = us
            target_bucket = "US"
        elif desired == "INTL" and intl:
            bucket = intl
            target_bucket = "INTL"
        elif us:
            bucket = us
            target_bucket = "US"
        else:
            bucket = intl
            target_bucket = "INTL"

        tested = [
            m for m in bucket
            if float(
                (stats.get(m.metro) or {}).get("runs") or 0
            ) > 0
        ]

        explore = cycle % 4 == 0 or not tested

        if explore:
            cursor_key = f"__{target_bucket}__"
            cursor = int(cursors.get(cursor_key, 0)) % len(bucket)
            market = bucket[cursor]
            cursors[cursor_key] = (cursor + 1) % len(bucket)
            policy = (
                "us_primary_explore"
                if target_bucket == "US"
                else "international_explore"
            )
        else:
            market = max(
                tested,
                key=lambda m: (
                    _score(m, stats.get(m.metro)),
                    m.base_priority,
                    m.market_id,
                ),
            )
            policy = (
                "us_primary_exploit_observed_yield"
                if target_bucket == "US"
                else "international_exploit_observed_yield"
            )

        selected_index = values.index(market)

    return {
        "market": market,
        "market_index": selected_index,
        "next_market_index": (selected_index + 1) % len(values),
        "next_country_index": int(
            state.get("next_country_index") or 0
        ),
        "country_market_cursors": cursors,
        "geo_cycle_count": cycle + 1,
        "policy": policy,
        "target_bucket": target_bucket,
        "compatibility": {
            "source": source,
            "country_code": market.country_code,
            "compatible": True,
            "fixed_market": bool(fixed_id),
        },
        "score": _score(
            market,
            stats.get(market.metro),
        ),
        "recent_stats": stats.get(market.metro) or {
            "runs": 0.0,
            "accepted": 0.0,
            "errors": 0.0,
        },
    }
