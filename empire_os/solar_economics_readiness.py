"""Solar Opportunity Map economics readiness from observed runtime evidence.

This module summarizes resource observations. It deliberately does not convert
CPU, memory, time, or bytes into money without a verified cash allocation rule.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from statistics import median
from typing import Any, Mapping


OBSERVATION_ROOT = Path(os.getenv(
    "EMPIRE_SOLAR_ECONOMICS_DIR",
    "/srv/empire_os/runtime/solar_opportunity_maps/economics",
))
SNAPSHOT_PATH = Path(os.getenv(
    "EMPIRE_SOLAR_ECONOMICS_LATEST",
    "/srv/empire_os/runtime/solar_opportunity_maps/economics_latest.json",
))


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def load_observations(
    *,
    root: str | Path | None = None,
    product_code: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    target = Path(root or OBSERVATION_ROOT)
    if not target.exists():
        return []
    bounded = max(1, min(int(limit), 5000))
    rows: list[dict[str, Any]] = []
    for path in sorted(
        target.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        row = _read(path)
        if row is None:
            continue
        if product_code and str(row.get("product_code") or "") != product_code:
            continue
        row["_path"] = str(path)
        rows.append(row)
        if len(rows) >= bounded:
            break
    return rows


def _number(row: Mapping[str, Any], key: str) -> float | None:
    resources = row.get("resource_observation")
    if not isinstance(resources, Mapping):
        return None
    value = resources.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(rows: list[Mapping[str, Any]], key: str) -> float | None:
    values = [
        value
        for row in rows
        for value in [_number(row, key)]
        if value is not None
    ]
    return round(float(median(values)), 6) if values else None


def build_economics_readiness(
    observations: list[Mapping[str, Any]],
    *,
    product_code: str | None = None,
) -> dict[str, Any]:
    matching = [
        dict(row)
        for row in observations
        if (
            not product_code
            or str(row.get("product_code") or "") == product_code
        )
    ]
    success = [
        row for row in matching
        if str(row.get("status") or "") == "success"
    ]
    failed = [
        row for row in matching
        if str(row.get("status") or "") == "failed"
    ]

    currencies = sorted({
        str(row.get("currency") or "").upper()
        for row in success
        if str(row.get("currency") or "").strip()
    })

    cash_cost_known = any(
        isinstance(row.get("monetary_cost"), Mapping)
        and str(row["monetary_cost"].get("state") or "").upper() == "VERIFIED"
        and row["monetary_cost"].get("amount_minor") is not None
        for row in success
    )
    acquisition_cost_known = any(
        isinstance(row.get("acquisition_cost_basis"), Mapping)
        and str(
            row["acquisition_cost_basis"].get("state") or ""
        ).upper() == "VERIFIED"
        for row in success
    )

    blockers = []
    if not success:
        blockers.append("no_successful_fulfilment_resource_observation")
    if not cash_cost_known:
        blockers.append("cash_allocation_rule_unverified")
    if not acquisition_cost_known:
        blockers.append("acquisition_cost_basis_unverified")
    blockers.append("founder_margin_policy_unverified")

    return {
        "schema_version": "empire.solar-economics-readiness.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product_code": product_code,
        "observation_count": len(matching),
        "successful_observation_count": len(success),
        "failed_observation_count": len(failed),
        "currencies_observed": currencies,
        "resource_summary": {
            "median_wall_seconds": _median(success, "wall_seconds"),
            "median_user_cpu_seconds": _median(
                success,
                "user_cpu_seconds",
            ),
            "median_system_cpu_seconds": _median(
                success,
                "system_cpu_seconds",
            ),
            "median_artifact_bytes": _median(
                success,
                "artifact_bytes",
            ),
            "max_observed_rss_kb": max(
                [
                    int(_number(row, "max_rss_kb") or 0)
                    for row in success
                ],
                default=0,
            ),
        },
        "fulfilment_resource_evidence": (
            "OBSERVED"
            if success
            else "UNKNOWN"
        ),
        "monetary_fulfilment_cost_state": (
            "VERIFIED"
            if cash_cost_known
            else "UNKNOWN"
        ),
        "acquisition_cost_state": (
            "VERIFIED"
            if acquisition_cost_known
            else "UNKNOWN"
        ),
        "margin_policy_state": "UNKNOWN",
        "binding_economics_ready": not blockers,
        "readiness_blockers": blockers,
        "cost_inferred_from_resource_usage": False,
        "margin_inferred": False,
        "actual_revenue": False,
        "execution_authority": "observe_only",
    }


def refresh_economics_snapshot(
    *,
    observation_root: str | Path | None = None,
    output: str | Path | None = None,
) -> dict[str, Any]:
    observations = load_observations(root=observation_root)
    payload = build_economics_readiness(observations)
    target = Path(output or SNAPSHOT_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    os.chmod(target, 0o600)
    return payload
