"""Canonical autonomous Predictive Cloud opportunity loop.

Sequence:
Opportunity Radar -> bounded public research -> truth-preserving Opportunity
Factory intake -> bounded AI planning.

This is safe internal intelligence work. It does not send outreach, accept
commercial terms, move funds, recognize revenue or expand authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.opportunity_ai_planner import plan_radar_opportunities
from empire_os.opportunity_factory_intake import refresh_factory_intake
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


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "candidate_count",
        "factory_ready_count",
        "blocked_count",
        "researched_candidate_count",
        "observation_count",
        "error_count",
        "queued_count",
        "skipped_unchanged",
        "skipped_no_evidence",
    )
    return {
        key: result.get(key)
        for key in keys
        if key in result
    }


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
    intake_fn: Callable[[Path], Mapping[str, Any]] = (
        refresh_factory_intake
    ),
    planner_fn: Callable[..., Mapping[str, Any]] = (
        plan_radar_opportunities
    ),
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output_path = root / OUTPUT_RELATIVE
    previous = _read_json(output_path)
    now = datetime.now(timezone.utc)
    previous_at = _parse_ts(previous.get("finished_at"))
    bounded_interval = max(
        300,
        min(int(min_interval_seconds), 21600),
    )

    if (
        not force
        and previous.get("ok") is True
        and previous_at is not None
        and (now - previous_at).total_seconds() < bounded_interval
    ):
        return {
            **previous,
            "skipped_fresh": True,
            "minimum_interval_seconds": bounded_interval,
            "automatic_external_execution_allowed": False,
            "execution_authority": "none",
        }

    started = now
    steps: list[dict[str, Any]] = []
    step_results: dict[str, Mapping[str, Any]] = {}

    sequence: tuple[
        tuple[str, Callable[..., Mapping[str, Any]], dict[str, Any]],
        ...,
    ] = (
        ("opportunity_radar", radar_fn, {}),
        ("opportunity_research", research_fn, {}),
        ("opportunity_factory_intake", intake_fn, {}),
        ("opportunity_ai_planner", planner_fn, {"limit": 3}),
    )

    for name, fn, kwargs in sequence:
        try:
            result = dict(fn(root, **kwargs))
            step_results[name] = result
            steps.append({
                "step": name,
                "ok": True,
                "summary": _summary(result),
            })
        except Exception as exc:
            steps.append({
                "step": name,
                "ok": False,
                "error": str(exc)[:1000],
            })
            break

    finished = datetime.now(timezone.utc)
    radar = step_results.get("opportunity_radar") or {}
    research = step_results.get("opportunity_research") or {}
    intake = step_results.get("opportunity_factory_intake") or {}
    planner = step_results.get("opportunity_ai_planner") or {}
    complete = len(steps) == len(sequence) and all(
        row["ok"] for row in steps
    )

    payload = {
        "schema_version": "empire.predictive_cloud.opportunity_loop.v2",
        "mode": "OBSERVE",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "ok": complete,
        "skipped_fresh": False,
        "minimum_interval_seconds": bounded_interval,
        "steps": steps,
        "radar_candidate_count": int(
            radar.get("candidate_count") or 0
        ),
        "research_candidate_count": int(
            research.get("researched_candidate_count") or 0
        ),
        "research_observation_count": int(
            research.get("observation_count") or 0
        ),
        "factory_ready_count": int(
            intake.get("factory_ready_count") or 0
        ),
        "factory_blocked_count": int(
            intake.get("blocked_count") or 0
        ),
        "ai_plan_queued_count": int(
            planner.get("queued_count") or 0
        ),
        "ai_plan_skipped_unchanged": int(
            planner.get("skipped_unchanged") or 0
        ),
        "next_layer": (
            "astra_priority_and_safe_internal_execution"
            if complete
            else "repair_failed_opportunity_loop_step"
        ),
        "automatic_radar": True,
        "automatic_internal_research": True,
        "automatic_factory_intake": True,
        "automatic_ai_planning": True,
        "automatic_external_execution_allowed": False,
        "outreach_sent": False,
        "commercial_terms_accepted": False,
        "payment_action": False,
        "revenue_recognized": False,
        "outreach_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }
    _write(output_path, payload)
    return payload
