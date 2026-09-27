"""Diversified source policy for EmpireOS acquisition.

Guarantees exploration across independent acquisition families while using
recent canonical outcomes to choose within each family. No outreach or writes.
"""
from __future__ import annotations

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


def recent_source_stats(
    log_path: str | Path,
    *,
    max_lines: int = 1500,
) -> dict[str, dict[str, int]]:
    path = Path(log_path)
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
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
        }
    )

    for raw in lines[-max_lines:]:
        try:
            row = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        source = str(row.get("source") or "").strip()
        if not source:
            continue
        msg = str(row.get("msg") or "")
        if msg == "source_run_done":
            stats[source]["runs"] += 1
            stats[source]["accepted"] += int(row.get("accepted") or 0)
            stats[source]["errors"] += int(row.get("errors") or 0)
        elif msg == "prospect_acquired":
            stats[source]["prospects"] += 1
        elif msg == "prospect_matched":
            stats[source]["matches"] += 1
        elif msg == "signal_queued":
            stats[source]["signals"] += 1
    return dict(stats)


def choose_source(
    state: dict[str, Any],
    *,
    log_path: str | Path,
) -> dict[str, Any]:
    start_index = int(state.get("next_family_index", 0)) % len(
        FAMILY_ROTATION
    )
    source_states = {
        str(key): str(value).upper()
        for key, value in (state.get("source_states") or {}).items()
    }
    family_index = start_index
    family = FAMILY_ROTATION[family_index]
    candidates: tuple[str, ...] = ()
    for offset in range(len(FAMILY_ROTATION)):
        family_index = (start_index + offset) % len(FAMILY_ROTATION)
        family = FAMILY_ROTATION[family_index]
        candidates = tuple(
            source for source in SOURCE_FAMILIES[family]
            if source_states.get(source) != "QUARANTINED"
        )
        if candidates:
            break
    if not candidates:
        raise RuntimeError("all acquisition source families are quarantined")
    stats = recent_source_stats(log_path)

    def rank(source: str) -> tuple[float, float, str]:
        row = stats.get(source, {})
        runs = int(row.get("runs") or 0)
        prospects = int(row.get("prospects") or 0)
        signals = int(row.get("signals") or 0)
        errors = int(row.get("errors") or 0)
        novel_yield = (prospects + signals) / max(runs, 1)
        # Under-tested sources win first; only genuinely new canonical
        # prospects or durable signal-inbox records count as useful yield.
        health = novel_yield - (errors / max(runs, 1)) * 5.0
        return (float(runs), -health, source)

    source = min(candidates, key=rank)
    source_stats = stats.get(source, {})
    return {
        "source": source,
        "family": family,
        "family_index": family_index,
        "next_family_index": (family_index + 1) % len(FAMILY_ROTATION),
        "recent_stats": source_stats,
        "policy": "diversified_exploration_then_yield",
        "families": {
            key: list(value)
            for key, value in SOURCE_FAMILIES.items()
        },
    }
