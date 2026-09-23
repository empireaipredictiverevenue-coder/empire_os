"""Recurring Tag Intelligence monitor runtime."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.tag_intelligence import (
    compare_tag_snapshots,
    review_tag_intelligence,
)
from empire_os.tag_intelligence_probe import observe_tag_surface


TARGETS = Path("runtime/tag_intelligence/targets.json")
OUTPUT = Path("runtime/tag_intelligence/latest.json")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _previous_by_id(previous: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for raw in previous.get("targets") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        key = str(row.get("target_id") or "").strip()
        if key:
            rows[key] = row
    return rows


def refresh_tag_intelligence_monitor(
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    config = _read(root / TARGETS)
    previous = _read(root / OUTPUT)
    previous_rows = _previous_by_id(previous)

    configured = [
        dict(row)
        for row in (config.get("targets") or [])
        if isinstance(row, Mapping)
        and row.get("enabled", True) is not False
    ]

    results: list[dict[str, Any]] = []
    critical_issues = 0
    high_issues = 0
    critical_changes = 0
    failed = 0

    for index, target in enumerate(configured, start=1):
        target_id = str(
            target.get("id")
            or target.get("url")
            or f"target-{index}"
        ).strip()
        url = str(target.get("url") or "").strip()
        expectations = (
            dict(target.get("expectations"))
            if isinstance(target.get("expectations"), Mapping)
            else {}
        )
        evidence = (
            dict(target.get("measurement_evidence"))
            if isinstance(target.get("measurement_evidence"), Mapping)
            else {}
        )

        observed = observe_tag_surface(url)
        if observed.get("ok") is not True:
            failed += 1
            results.append({
                "target_id": target_id,
                "url": url,
                "available": False,
                "error": observed.get("error"),
                "status_code": observed.get("status_code"),
                "mode": "OBSERVE",
                "execution_authority": "none",
            })
            continue

        page_tags = dict(observed.get("page_tags") or {})
        measurement_tags = dict(
            observed.get("measurement_tags") or {}
        )
        measurement_tags.update(evidence)

        analysis = review_tag_intelligence(
            page_tags=page_tags,
            measurement_tags=measurement_tags,
            expectations=expectations,
        ).as_dict()

        previous_row = previous_rows.get(target_id) or {}
        changes = compare_tag_snapshots(
            previous_page_tags=previous_row.get("page_tags"),
            current_page_tags=page_tags,
            previous_measurement_tags=previous_row.get(
                "measurement_tags"
            ),
            current_measurement_tags=measurement_tags,
        )

        critical_issues += int(analysis.get("critical_count") or 0)
        high_issues += int(analysis.get("high_count") or 0)
        critical_changes += int(
            changes.get("critical_change_count") or 0
        )

        results.append({
            "target_id": target_id,
            "url": url,
            "available": True,
            "page_tags": page_tags,
            "measurement_tags": measurement_tags,
            "expectations": expectations,
            "analysis": analysis,
            "changes": changes,
            "limitations": observed.get("limitations") or [],
            "mode": "OBSERVE",
            "execution_authority": "none",
        })

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": "empire.tag_intelligence.monitor.v1",
        "mode": "OBSERVE",
        "generated_at": now,
        "target_count": len(configured),
        "available_target_count": sum(
            row.get("available") is True for row in results
        ),
        "failed_target_count": failed,
        "critical_issue_count": critical_issues,
        "high_issue_count": high_issues,
        "critical_change_count": critical_changes,
        "targets": results,
        "automatic_tag_mutation": False,
        "publishing_execution": False,
        "measurement_platform_write": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }

    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
