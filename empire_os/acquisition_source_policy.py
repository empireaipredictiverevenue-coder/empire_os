"""Adaptive diversified source policy for EmpireOS acquisition."""
from __future__ import annotations

from collections.abc import Collection

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

SOURCE_FAMILIES = {
    "coverage": ("overpass",),
    "intent": ("reddit", "courtlistener"),
    "property": ("permits", "chicago_311", "nyc_hpd"),
    "event": ("nws_alerts",),
}

FAMILY_ROTATION = ("coverage", "intent", "property", "event")
EXPLORATION_INTERVAL = 12


def recent_source_stats(
    log_path: str | Path,
    *,
    max_lines: int = 5000,
) -> dict[str, dict[str, int]]:
    path = Path(log_path)
    try:
        lines = path.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
    except OSError:
        return {}

    stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "runs": 0,
            "accepted": 0,
            "errors": 0,
            "prospects": 0,
            "matches": 0,
            "signals": 0,
            "productive_runs": 0,
            "zero_yield_runs": 0,
        }
    )

    current_source = None
    current_useful_yield = 0

    for raw in lines[-max_lines:]:
        try:
            row = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict):
            continue

        msg = str(row.get("msg") or "")
        row_source = str(row.get("source") or "").strip()

        if msg == "source_run_start":
            current_source = row_source or None
            current_useful_yield = 0
            continue

        source = row_source or current_source or ""
        if not source:
            continue

        if msg == "prospect_acquired":
            stats[source]["prospects"] += 1
            if source == current_source:
                current_useful_yield += 1

        elif msg == "prospect_matched":
            # Existing/deduped identity is NOT new canonical prospect yield.
            stats[source]["matches"] += 1

        elif msg == "signal_queued":
            stats[source]["signals"] += 1
            if source == current_source:
                current_useful_yield += 1

        elif msg == "source_run_done":
            stat = stats[source]
            stat["runs"] += 1
            stat["accepted"] += int(row.get("accepted") or 0)
            stat["errors"] += int(row.get("errors") or 0)

            if source == current_source and current_useful_yield > 0:
                stat["productive_runs"] += 1
            else:
                stat["zero_yield_runs"] += 1

            current_source = None
            current_useful_yield = 0

    return dict(stats)


def source_health(row: dict[str, Any] | None) -> float:
    row = row or {}
    runs = max(0, int(row.get("runs") or 0))
    prospects = max(0, int(row.get("prospects") or 0))
    signals = max(0, int(row.get("signals") or 0))
    errors = max(0, int(row.get("errors") or 0))
    zero_yield = max(0, int(row.get("zero_yield_runs") or 0))

    if runs == 0:
        return 0.10

    useful_per_run = (prospects + signals) / runs
    error_rate = min(1.0, errors / runs)
    zero_rate = min(1.0, zero_yield / runs)

    return round(
        useful_per_run
        - (3.0 * error_rate)
        - (0.75 * zero_rate),
        6,
    )


def choose_source(
    state: dict[str, Any],
    *,
    log_path: str | Path,
    excluded_sources: Collection[str] = (),
) -> dict[str, Any]:
    """Select an eligible acquisition source.

    Persistent quarantine and transient execution degradation are deliberately
    separate. excluded_sources applies only to the current bounded invocation.
    """
    start_index = int(
        state.get("next_family_index", 0)
    ) % len(FAMILY_ROTATION)

    persistent_states = {
        str(key): str(value).upper()
        for key, value in (state.get("source_states") or {}).items()
    }

    excluded = {
        str(source).strip()
        for source in excluded_sources
        if str(source).strip()
    }

    eligible: list[tuple[int, str, str]] = []

    for family_index, family in enumerate(FAMILY_ROTATION):
        for source in SOURCE_FAMILIES[family]:
            if persistent_states.get(source) == "QUARANTINED":
                continue
            if source in excluded:
                continue
            eligible.append((family_index, family, source))

    if not eligible:
        raise RuntimeError("no eligible acquisition sources remain")

    stats = recent_source_stats(log_path)
    cycle = int(state.get("geo_cycle_count") or 0)

    exploration = (
        cycle % EXPLORATION_INTERVAL
        == EXPLORATION_INTERVAL - 1
    )

    target_family = FAMILY_ROTATION[start_index]

    family_candidates = [
        item
        for item in eligible
        if item[1] == target_family
    ]

    if exploration and family_candidates:
        family_index, family, source = min(
            family_candidates,
            key=lambda item: (
                int(
                    (stats.get(item[2]) or {}).get("runs")
                    or 0
                ),
                -source_health(stats.get(item[2])),
                item[2],
            ),
        )
        policy = "bounded_family_exploration"

    else:
        def rank(
            item: tuple[int, str, str],
        ) -> tuple[float, int, str]:
            _, family, source = item

            family_bonus = (
                0.10
                if family == target_family
                else 0.0
            )

            return (
                source_health(stats.get(source)) + family_bonus,
                -int(
                    (stats.get(source) or {}).get("runs")
                    or 0
                ),
                source,
            )

        family_index, family, source = max(
            eligible,
            key=rank,
        )

        policy = "canonical_yield_health_exploitation"

    recent = stats.get(source, {})

    return {
        "source": source,
        "family": family,
        "family_index": family_index,
        "next_family_index": (
            family_index + 1
        ) % len(FAMILY_ROTATION),
        "recent_stats": recent,
        "score": source_health(recent),
        "exploration": exploration,
        "policy": policy,
        "excluded_sources": sorted(excluded),
        "families": {
            key: list(value)
            for key, value in SOURCE_FAMILIES.items()
        },
    }
