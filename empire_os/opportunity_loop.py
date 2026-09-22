"""Canonical autonomous Predictive Cloud opportunity loop.

Sequence:
Opportunity Radar -> bounded public research -> bounded AI planning.

This loop is safe internal intelligence work. It does not send outreach, accept
commercial terms, move funds, recognize revenue or expand authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.opportunity_ai_planner import plan_radar_opportunities
from empire_os.opportunity_radar import refresh_opportunity_radar
from empire_os.opportunity_research import refresh_opportunity_research


OUTPUT_RELATIVE = Path("runtime/opportunity_radar/loop_latest.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_ts(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(
            raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        )
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def run_opportunity_loop(
    repo_root: str | Path,
    *,
    min_interval_seconds: int = 1500,
    force: bool = False,
    radar_fn: Callable[[Path], Mapping[str, Any]] = (
        refresh_opportunity_radar
    ),
    research_fn: Callable[[Path], Mapping[str, Any]] = (
        refresh_opportunity_research
    ),
    planner_fn: Callable[..., Mapping[str, Any]] = (
        plan_radar_opportunities
    ),
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output_path = root / OUTPUT_RELATIVE
    previous = _read_json(output_path)
    now = datetime.now(timezone.utc)
    previous_at = _parse_ts(previous.get("generated_at"))
    bounded_interval = max(300, min(int(min_interval_seconds), 21600))

    if (
        not force
        and previous_at is not None
        and (now - previous_at).total_seconds() < bounded_interval
    ):
        return {
            **previous,
            "ok": True,
            "skipped_fresh": True,
            "minimum_interval_seconds": bounded_interval,
            "automatic_external_execution_allowed": False,
            "execution_authority": "none",
        }

    radar = dict(radar_fn(root))
    research = dict(research_fn(root))
    planner = dict(planner_fn(root, limit=3))

    payload = {
        "schema_version": "empire.predictive_cloud.opportunity_loop.v1",
        "ok": True,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "skipped_fresh": False,
        "minimum_interval_seconds": bounded_interval,
        "radar_candidate_count": int(
            radar.get("candidate_count") or 0
        ),
        "research_candidate_count": int(
            research.get("researched_candidate_count") or 0
        ),
        "research_observation_count": int(
            research.get("observation_count") or 0
        ),
        "ai_plan_queued_count": int(
            planner.get("queued_count") or 0
        ),
        "ai_plan_skipped_unchanged": int(
            planner.get("skipped_unchanged") or 0
        ),
        "source_status": radar.get("source_status") or {},
        "next_layer": (
            "opportunity_factory_evidence_completion_and_astra_priority"
        ),
        "automatic_radar": True,
        "automatic_public_research": True,
        "automatic_ai_planning": True,
        "automatic_external_execution_allowed": False,
        "outreach_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }
    _write(output_path, payload)
    return payload
