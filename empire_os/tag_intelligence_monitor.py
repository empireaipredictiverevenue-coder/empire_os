"""Recurring Tag Intelligence monitor runtime."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

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


def _baseline_change_summary() -> dict[str, Any]:
    return {
        "schema_version": "empire.tag_change_monitor.v1",
        "mode": "OBSERVE",
        "comparison_state": "BASELINE_ESTABLISHED",
        "previous_snapshot_available": False,
        "change_count": 0,
        "critical_change_count": 0,
        "high_change_count": 0,
        "changes": [],
        "automatic_repair": False,
        "execution_authority": "none",
    }


def _issue_codes(analysis: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("code") or "")
        for row in (analysis.get("issues") or [])
        if isinstance(row, Mapping)
        and str(row.get("code") or "").strip()
    ]


def _static_observation_state(
    rows: list[dict[str, Any]],
    key: str,
) -> str:
    available = [row for row in rows if row.get("available") is True]
    if not available:
        return "UNKNOWN"
    if any((row.get("measurement_tags") or {}).get(key) for row in available):
        return "OBSERVED_IN_STATIC_MARKUP"
    return "NOT_OBSERVED_IN_STATIC_MARKUP"


def _configured_evidence_state(
    rows: list[dict[str, Any]],
    key: str,
) -> str:
    values = [
        (row.get("measurement_tags") or {}).get(key)
        for row in rows
        if row.get("available") is True
        and (row.get("measurement_tags") or {}).get(key) is not None
    ]
    if not values:
        return "UNKNOWN"
    if all(value is True for value in values):
        return "VERIFIED_BY_CONFIGURED_EVIDENCE"
    if any(value is False for value in values):
        return "NOT_VERIFIED"
    return "UNKNOWN"


def _site_count(configured: list[dict[str, Any]]) -> int:
    hosts: set[str] = set()
    for row in configured:
        value = str(row.get("url") or "").strip()
        if not value:
            continue
        parsed = urlparse(
            value if "://" in value else f"https://{value}"
        )
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return len(hosts)


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

    if not configured:
        env_urls = [
            value.strip()
            for value in os.environ.get(
                "EMPIRE_TAG_MONITOR_URLS", ""
            ).split(",")
            if value.strip()
        ]
        configured = [
            {
                "id": f"default-{index}",
                "url": url,
                "expectations": {
                    "intended_public": True,
                    "schema_expected": True,
                },
            }
            for index, url in enumerate(env_urls, start=1)
        ]

    results: list[dict[str, Any]] = []
    critical_issues = 0
    high_issues = 0
    search_issues = 0
    measurement_issues = 0
    change_count = 0
    critical_changes = 0
    pages_with_public_noindex = 0
    pages_missing_canonical = 0
    pages_missing_schema = 0
    missing_conversion_events = 0
    duplicate_conversion_events = 0
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
        has_previous_snapshot = (
            previous_row.get("available") is True
            and isinstance(previous_row.get("page_tags"), Mapping)
            and isinstance(
                previous_row.get("measurement_tags"),
                Mapping,
            )
        )
        if has_previous_snapshot:
            changes = compare_tag_snapshots(
                previous_page_tags=previous_row.get("page_tags"),
                current_page_tags=page_tags,
                previous_measurement_tags=previous_row.get(
                    "measurement_tags"
                ),
                current_measurement_tags=measurement_tags,
            )
            changes["comparison_state"] = "COMPARED"
            changes["previous_snapshot_available"] = True
        else:
            changes = _baseline_change_summary()

        codes = _issue_codes(analysis)
        critical_issues += int(analysis.get("critical_count") or 0)
        high_issues += int(analysis.get("high_count") or 0)
        search_issues += int(analysis.get("search_tag_issue_count") or 0)
        measurement_issues += int(
            analysis.get("measurement_tag_issue_count") or 0
        )
        change_count += int(changes.get("change_count") or 0)
        critical_changes += int(
            changes.get("critical_change_count") or 0
        )
        pages_with_public_noindex += int(
            "public_page_noindex" in codes
        )
        pages_missing_canonical += int(
            "missing_canonical" in codes
        )
        pages_missing_schema += int(
            "structured_data_missing" in codes
        )
        missing_conversion_events += codes.count(
            "required_conversion_event_missing"
        )
        duplicate_conversion_events += codes.count(
            "duplicate_conversion_event"
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
        "monitored_site_count": _site_count(configured),
        "monitored_page_count": sum(
            row.get("available") is True for row in results
        ),
        "available_target_count": sum(
            row.get("available") is True for row in results
        ),
        "failed_target_count": failed,
        "critical_issue_count": critical_issues,
        "high_issue_count": high_issues,
        "search_issue_count": search_issues,
        "measurement_issue_count": measurement_issues,
        "change_count": change_count,
        "critical_change_count": critical_changes,
        "pages_with_public_noindex": pages_with_public_noindex,
        "pages_missing_canonical": pages_missing_canonical,
        "pages_missing_schema": pages_missing_schema,
        "missing_conversion_event_count": missing_conversion_events,
        "duplicate_conversion_event_count": duplicate_conversion_events,
        "measurement_observation": {
            "meta_pixel": _static_observation_state(
                results, "meta_pixel_ids"
            ),
            "ga4": _static_observation_state(
                results, "ga4_measurement_ids"
            ),
            "gtm": _static_observation_state(
                results, "gtm_container_ids"
            ),
            "google_ads_conversion": _static_observation_state(
                results, "google_ads_conversion_ids"
            ),
            "meta_capi_dedup": _configured_evidence_state(
                results, "meta_event_id_dedup"
            ),
            "revenue_truth_linkage": _configured_evidence_state(
                results, "revenue_truth_linked"
            ),
        },
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
