"""Read-only runtime projection for spatial and physical intelligence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _latest_jsonl(path: Path) -> dict[str, Any]:
    try:
        lines = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError:
        return {}
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def build_spatial_physical_runtime(repo_root: Path) -> dict[str, Any]:
    runtime = repo_root / "runtime"
    strike_dir = runtime / "revenue_strike"

    physical_rows: list[dict[str, Any]] = []
    evidence_refs: list[str] = []
    multipliers: list[float] = []

    paths = sorted(strike_dir.glob("*.json")) if strike_dir.exists() else ()
    for path in paths:
        raw = _read_json(path)
        trigger = raw.get("trigger")
        if not isinstance(trigger, dict):
            continue
        observed_at = str(raw.get("observed_at") or "").strip()
        source = str(trigger.get("source") or "").strip()
        if not observed_at or not source:
            continue
        if str(raw.get("execution_authority") or "none") != "none":
            continue

        ref = f"runtime:{path.relative_to(repo_root).as_posix()}"
        physical_rows.append(
            {
                "phenomenon": "storm_exposure",
                "market": raw.get("market"),
                "observed_at": observed_at,
                "source": source,
                "evidence_ref": ref,
            }
        )
        evidence_refs.append(ref)
        multiplier = trigger.get("modeled_multiplier")
        if isinstance(multiplier, (int, float)):
            multipliers.append(float(multiplier))

    satellite = _latest_jsonl(
        runtime / "feedback" / "satellite_damage.jsonl"
    )
    satellite_msg = str(satellite.get("msg") or "").strip()
    satellite_real_imagery: bool | None
    if satellite_msg == "scan_blocked_no_real_imagery":
        satellite_real_imagery = False
    else:
        satellite_real_imagery = None

    return {
        "schema_version": "empire.spatial-physical-runtime.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "available": bool(physical_rows or satellite),
        "volumetric_observations": None,
        "physical_observations": (
            len(physical_rows) if physical_rows else None
        ),
        "modeled_opportunities": None,
        "max_combined_priority_boost": None,
        "storm_multiplier_max": (
            max(multipliers) if multipliers else None
        ),
        "physical_rows": physical_rows,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "source_state": {
            "storm_exposure_observed": bool(physical_rows),
            "satellite_real_imagery": satellite_real_imagery,
            "satellite_state": satellite_msg or None,
            "satellite_observed_at": satellite.get("ts"),
        },
        "unknown_stays_unknown": True,
    }
