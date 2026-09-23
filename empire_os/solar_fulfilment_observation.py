"""Resource observations for Solar Opportunity Map fulfilment.

These observations are evidence about execution resources only. They are not
monetary fulfilment cost, acquisition cost, gross margin, or revenue. A cash
cost remains UNKNOWN until Empire has a verified allocation rule or invoice/
provider evidence that converts resource use into the product currency.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import time
from typing import Any, Callable, Mapping


DEFAULT_ROOT = Path(os.getenv(
    "EMPIRE_SOLAR_ECONOMICS_DIR",
    "/srv/empire_os/runtime/solar_opportunity_maps/economics",
))


def begin_resource_observation() -> dict[str, float]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "wall_started": time.perf_counter(),
        "user_cpu_started": float(usage.ru_utime),
        "system_cpu_started": float(usage.ru_stime),
        "max_rss_started_kb": float(usage.ru_maxrss),
    }


def finish_resource_observation(
    started: Mapping[str, Any],
    *,
    prospect_id: str,
    product_code: str | None,
    currency: str | None,
    artifact_paths: Mapping[str, Any] | None = None,
    priority_actions: int | None = None,
    observed_sections: int | None = None,
    unavailable_sections: int | None = None,
) -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall_started = float(started.get("wall_started") or 0.0)
    user_started = float(started.get("user_cpu_started") or 0.0)
    system_started = float(started.get("system_cpu_started") or 0.0)

    paths = dict(artifact_paths or {})
    artifact_bytes = 0
    artifact_files = []
    for key in ("json_path", "markdown_path"):
        raw = str(paths.get(key) or "").strip()
        if not raw:
            continue
        path = Path(raw)
        size = None
        try:
            size = path.stat().st_size
            artifact_bytes += int(size)
        except OSError:
            size = None
        artifact_files.append({
            "kind": key,
            "path": raw,
            "bytes": size,
        })

    return {
        "schema_version": "empire.solar-fulfilment-resource-observation.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "prospect_id": str(prospect_id or "").strip() or None,
        "product_code": str(product_code or "").strip() or None,
        "currency": str(currency or "").strip().upper() or None,
        "resource_observation": {
            "wall_seconds": round(max(
                0.0,
                time.perf_counter() - wall_started,
            ), 6),
            "user_cpu_seconds": round(max(
                0.0,
                float(usage.ru_utime) - user_started,
            ), 6),
            "system_cpu_seconds": round(max(
                0.0,
                float(usage.ru_stime) - system_started,
            ), 6),
            "max_rss_kb": int(usage.ru_maxrss),
            "max_rss_started_kb": int(
                float(started.get("max_rss_started_kb") or 0.0)
            ),
            "artifact_bytes": artifact_bytes,
            "artifact_files": artifact_files,
        },
        "work_output": {
            "priority_actions": priority_actions,
            "observed_sections": observed_sections,
            "unavailable_sections": unavailable_sections,
        },
        "monetary_cost": {
            "state": "UNKNOWN",
            "amount_minor": None,
            "currency": str(currency or "").strip().upper() or None,
            "reason": (
                "resource_usage_has_no_verified_cash_allocation_rule"
            ),
        },
        "acquisition_cost_basis": {
            "state": "UNKNOWN",
            "reason": "prospect_acquisition_cost_not_attributed_by_this_observation",
        },
        "fulfilment_cost_basis": {
            "state": "PARTIAL",
            "reason": "resource_use_observed_but_cash_cost_not_allocated",
        },
        "margin_inferred": False,
        "actual_revenue": False,
        "payment_mutation": False,
        "execution_authority": "observe_only",
    }


def write_resource_observation(
    observation: Mapping[str, Any],
    *,
    root: str | Path | None = None,
) -> Path:
    target_root = Path(root or DEFAULT_ROOT)
    target_root.mkdir(parents=True, exist_ok=True)
    prospect_id = str(observation.get("prospect_id") or "unknown").strip()
    observed_at = str(observation.get("observed_at") or "").strip()
    safe_ts = (
        observed_at
        .replace(":", "")
        .replace("-", "")
        .replace("+", "_")
        .replace(".", "_")
    )
    target = target_root / f"{prospect_id}-{safe_ts}.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(dict(observation), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    os.chmod(target, 0o600)
    return target


def materialize_with_resource_observation(
    prospect_id: str,
    *,
    build: Callable[[str], Mapping[str, Any]],
    write: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    observation_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build/write one map and persist non-monetary resource evidence."""
    started = begin_resource_observation()
    try:
        payload = dict(build(prospect_id))
        paths = dict(write(payload))
    except Exception as exc:
        failed = finish_resource_observation(
            started,
            prospect_id=prospect_id,
            product_code=None,
            currency=None,
            artifact_paths=None,
        )
        failed["status"] = "failed"
        failed["error"] = f"{type(exc).__name__}:{str(exc)[:260]}"
        evidence_path = write_resource_observation(
            failed,
            root=observation_root,
        )
        raise

    offer = payload.get("offer")
    offer = offer if isinstance(offer, Mapping) else {}
    report = payload.get("search_opportunity_report")
    report = report if isinstance(report, Mapping) else {}
    observation = finish_resource_observation(
        started,
        prospect_id=prospect_id,
        product_code=offer.get("product_code"),
        currency=offer.get("currency"),
        artifact_paths=paths,
        priority_actions=len(payload.get("priority_backlog") or []),
        observed_sections=report.get("observed_sections"),
        unavailable_sections=report.get("unavailable_sections"),
    )
    observation["status"] = "success"
    evidence_path = write_resource_observation(
        observation,
        root=observation_root,
    )
    return {
        "payload": payload,
        "artifacts": paths,
        "resource_observation": observation,
        "resource_observation_path": str(evidence_path),
    }
