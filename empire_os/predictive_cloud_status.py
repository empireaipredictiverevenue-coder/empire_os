"""Canonical read-only status contract for Predictive Cloud.

Aggregates runtime artifacts without mutating business state. Missing artifacts
stay unavailable/unknown rather than becoming zero or healthy.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


OUTPUT = Path("runtime/predictive_cloud/status_latest.json")

COMPONENTS: dict[str, dict[str, Any]] = {
    "source_health": {
        "path": Path("runtime/source_health/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 1800,
    },
    "community_intent": {
        "path": Path("runtime/community_intent/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 3600,
    },
    "market_gps": {
        "path": Path("runtime/market_sweeps/revenue_gps_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 7200,
    },
    "opportunity_loop": {
        "path": Path("runtime/opportunity_radar/loop_latest.json"),
        "time_keys": ("finished_at", "generated_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_radar": {
        "path": Path("runtime/opportunity_radar/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_research": {
        "path": Path("runtime/opportunity_radar/research_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_normalizer": {
        "path": Path(
            "runtime/opportunity_factory/normalized_signals_latest.json"
        ),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "opportunity_factory_intake": {
        "path": Path("runtime/opportunity_factory/intake_latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
    "conversion_intelligence": {
        "path": Path("runtime/conversion/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 3600,
    },
    "revenue_pulse": {
        "path": Path("runtime/revenue_pulse/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 900,
    },
    "commercial_loop": {
        "path": Path("runtime/commercial_loop/latest.json"),
        "time_keys": ("generated_at", "observed_at"),
        "fresh_seconds": 900,
    },
    "astra": {
        "path": Path("runtime/astra/latest.json"),
        "time_keys": ("observed_at", "generated_at"),
        "fresh_seconds": 900,
    },
    "founder_directives": {
        "path": Path("runtime/founder_directives/latest.json"),
        "time_keys": ("generated_at", "updated_at", "observed_at"),
        "fresh_seconds": 3600,
    },
}


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _observed_at(
    payload: Mapping[str, Any],
    keys: tuple[str, ...],
) -> datetime | None:
    for key in keys:
        parsed = _time(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _summary(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if name == "source_health":
        return {
            "end_to_end_healthy": payload.get("end_to_end_healthy"),
            "blockers": payload.get("blockers"),
        }
    if name == "community_intent":
        return {
            "observations": payload.get("observations"),
            "new_observations": payload.get("new_observations"),
            "high_intent": payload.get("high_intent"),
        }
    if name == "market_gps":
        return {
            "market_count": payload.get("market_count"),
            "commercial_demand_market_count": payload.get(
                "commercial_demand_market_count"
            ),
            "research_queue_count": len(
                payload.get("research_queue") or []
            ),
        }
    if name == "opportunity_loop":
        return {
            "ok": payload.get("ok"),
            "step_count": len(payload.get("steps") or []),
            "radar_candidate_count": payload.get(
                "radar_candidate_count"
            ),
            "research_observation_count": payload.get(
                "research_observation_count"
            ),
            "candidates_with_any_normalized_score": payload.get(
                "candidates_with_any_normalized_score"
            ),
            "total_normalized_scores": payload.get(
                "total_normalized_scores"
            ),
            "factory_ready_count": payload.get(
                "factory_ready_count"
            ),
            "factory_blocked_count": payload.get(
                "factory_blocked_count"
            ),
            "ai_plan_queued_count": payload.get(
                "ai_plan_queued_count"
            ),
        }
    if name == "opportunity_radar":
        return {
            "candidate_count": payload.get("candidate_count"),
            "factory_ready_count": payload.get("factory_ready_count"),
        }
    if name == "opportunity_research":
        return {
            "researched_candidate_count": payload.get(
                "researched_candidate_count"
            ),
            "observation_count": payload.get("observation_count"),
            "error_count": payload.get("error_count"),
        }
    if name == "opportunity_normalizer":
        return {
            "candidate_count": payload.get("candidate_count"),
            "candidates_with_any_normalized_score": payload.get(
                "candidates_with_any_normalized_score"
            ),
            "total_normalized_scores": payload.get(
                "total_normalized_scores"
            ),
            "search_result_counts_used_as_scores": payload.get(
                "search_result_counts_used_as_scores"
            ),
        }
    if name == "opportunity_factory_intake":
        return {
            "candidate_count": payload.get("candidate_count"),
            "factory_ready_count": payload.get("factory_ready_count"),
            "blocked_count": payload.get("blocked_count"),
        }
    if name == "conversion_intelligence":
        return {
            "available": payload.get("available"),
            "primary_bottleneck": payload.get("primary_bottleneck"),
        }
    if name == "revenue_pulse":
        truth = payload.get("recognized_revenue_truth")
        truth = truth if isinstance(truth, Mapping) else {}
        return {
            "pulse_state": payload.get("pulse_state"),
            "highest_priority_blocker": payload.get(
                "highest_priority_blocker"
            ),
            "recognized_revenue_cents": truth.get(
                "recognized_revenue_cents"
            ),
            "realized_gp_cents": truth.get("realized_gp_cents"),
        }
    if name == "commercial_loop":
        return {
            "loop_complete": payload.get("loop_complete"),
            "highest_priority_blocker": payload.get(
                "highest_priority_blocker"
            ),
        }
    if name == "astra":
        return {
            "available": payload.get("available"),
            "mode": payload.get("mode"),
            "decision": payload.get("decision"),
        }
    if name == "founder_directives":
        return {
            "directive_count": payload.get("directive_count"),
            "founder_gate_count": payload.get("founder_gate_count"),
        }
    return {}


def build_predictive_cloud_status(
    repo_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    components: dict[str, Any] = {}

    for name, config in COMPONENTS.items():
        path = repo_root / config["path"]
        payload = _read(path)
        if payload is None:
            components[name] = {
                "available": False,
                "freshness": "unknown",
                "observed_at": None,
                "age_seconds": None,
                "path": str(config["path"]),
                "summary": {},
            }
            continue

        observed = _observed_at(payload, config["time_keys"])
        age_seconds = None
        freshness = "unknown"
        if observed is not None:
            age_seconds = max(
                0,
                int((current - observed).total_seconds()),
            )
            freshness = (
                "fresh"
                if age_seconds <= int(config["fresh_seconds"])
                else "stale"
            )

        components[name] = {
            "available": True,
            "freshness": freshness,
            "observed_at": (
                observed.isoformat() if observed is not None else None
            ),
            "age_seconds": age_seconds,
            "mode": payload.get("mode"),
            "execution_authority": payload.get("execution_authority"),
            "path": str(config["path"]),
            "summary": _summary(name, payload),
        }

    unavailable = [
        name for name, row in components.items()
        if row["available"] is False
    ]
    stale = [
        name for name, row in components.items()
        if row["freshness"] == "stale"
    ]
    unknown_freshness = [
        name for name, row in components.items()
        if row["available"] and row["freshness"] == "unknown"
    ]

    return {
        "schema_version": "empire.predictive_cloud.status.v1",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "component_count": len(components),
        "available_component_count": sum(
            row["available"] for row in components.values()
        ),
        "unavailable_components": unavailable,
        "stale_components": stale,
        "unknown_freshness_components": unknown_freshness,
        "components": components,
        "outreach_sent_by_status": False,
        "payment_action_by_status": False,
        "revenue_recognized_by_status": False,
        "execution_authority": "none",
    }


def refresh_predictive_cloud_status(repo_root: Path) -> dict[str, Any]:
    payload = build_predictive_cloud_status(repo_root)
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
