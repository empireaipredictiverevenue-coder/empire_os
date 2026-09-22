"""Read-only founder dashboard projection from canonical runtime evidence."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.control_conveyor import build_conveyor
from empire_os.permit_intelligence_runtime import build_permit_intelligence_runtime
from empire_os.vertical_intelligence_runtime import (
    build_private_capital_intelligence_runtime,
    build_property_intelligence_runtime,
)
from empire_os.commercial_recovery_registry import (
    recovery_product_catalog,
    recovery_summary,
)
from empire_os.competitor_audience_runtime import (
    build_competitor_audience_runtime,
)
from empire_os.competitor_audience_research_executor import (
    build_account_research_runtime,
)
from empire_os.commercial_marketing_registry import (
    marketing_plan_catalog,
    marketing_summary,
)

PHASE_RE = re.compile(
    r"^### Phase\s+(\d+)\s+—\s+(.+?)(?:\s+←\s+CURRENT)?$",
    re.MULTILINE,
)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _mtime_iso(path: Path) -> str | None:
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()


def _phase_projection(blueprint: Path) -> list[dict[str, Any]]:
    try:
        text = blueprint.read_text()
    except OSError:
        return []

    matches = list(PHASE_RE.finditer(text))
    phases: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        number = int(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]

        heading_line = match.group(0)
        if number == 3 or "FROZEN" in title.upper():
            state = "implementation_frozen_proof_pending"
        elif "CURRENT" in heading_line or number == 4:
            state = "current_observe"
        else:
            state = "parallel_build"

        phases.append(
            {
                "phase": number,
                "title": title.replace(
                    " — IMPLEMENTATION FROZEN / PRODUCTION PROOF GATES CARRIED FORWARD",
                    "",
                ),
                "state": state,
                "verified_markers": section.count("✅"),
            }
        )
    return phases


def _commercial_operating_state(
    raw: dict[str, Any],
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    blocker = str(raw.get("highest_priority_blocker") or "").strip() or None
    observed = {
        str(row.get("stage") or ""): row.get("observed")
        for row in stages
        if isinstance(row, dict)
    }

    if raw.get("loop_complete") is True:
        return {
            "class": "COMPLETE",
            "next_event": None,
            "founder_action_required": False,
        }

    if blocker == "buyer_conversation" and observed.get("outbound_sent") is True:
        return {
            "class": "WAITING_EXTERNAL",
            "next_event": "genuine_buyer_reply",
            "founder_action_required": False,
        }

    founder_gates = {
        "commercial_terms": "binding_commercial_terms",
        "bsc_payment_request": "payment_request_authority",
        "recognized_revenue": "revenue_recognition",
    }
    if blocker in founder_gates:
        return {
            "class": "FOUNDER_GATE",
            "next_event": founder_gates[blocker],
            "founder_action_required": True,
        }

    return {
        "class": "SYSTEM_WORK",
        "next_event": blocker,
        "founder_action_required": False,
    }


def _commercial_loop(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "mode": "unknown",
            "loop_complete": False,
            "highest_priority_blocker": "unavailable",
            "stages": [],
        }
    stages = raw.get("stages")
    clean_stages = stages if isinstance(stages, list) else []
    return {
        "available": True,
        "observed_at": _mtime_iso(path),
        "mode": raw.get("mode"),
        "loop_complete": raw.get("loop_complete") is True,
        "blocker_state": raw.get("blocker_state"),
        "highest_priority_blocker": raw.get("highest_priority_blocker"),
        "operating_state": _commercial_operating_state(raw, clean_stages),
        "stages": clean_stages,
    }


def _astra(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}

    evidence = raw.get("operational_evidence")
    observed = evidence.get("observed") if isinstance(evidence, dict) else {}
    freshness = evidence.get("freshness") if isinstance(evidence, dict) else {}
    board = raw.get("operating_board")
    board_result = board.get("result") if isinstance(board, dict) else {}
    items = board_result.get("items") if isinstance(board_result, dict) else []
    calibration = raw.get("calibration")

    return {
        "available": True,
        "observed_at": _mtime_iso(path),
        "mode": raw.get("mode"),
        "fresh": freshness.get("fresh") if isinstance(freshness, dict) else None,
        "freshness_reason": (
            freshness.get("reason") if isinstance(freshness, dict) else None
        ),
        "observed": observed if isinstance(observed, dict) else {},
        "board": items if isinstance(items, list) else [],
        "calibration": calibration if isinstance(calibration, dict) else {},
    }


def _source_health(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}
    return {
        "available": True,
        "snapshot_updated_at": _mtime_iso(path),
        "observed_at": raw.get("observed_at"),
        "source": raw.get("source"),
        "metro": raw.get("metro"),
        "mode": raw.get("mode"),
        "endpoint_healthy": raw.get("endpoint_healthy"),
        "end_to_end_healthy": raw.get("end_to_end_healthy"),
        "candidates_seen": raw.get("candidates_seen"),
        "quality_accepted": raw.get("quality_accepted"),
        "quality_rejected": raw.get("quality_rejected"),
        "canonical_writes": raw.get("canonical_writes"),
        "blockers": raw.get("blockers") if isinstance(raw.get("blockers"), list) else [],
        "errors": raw.get("errors") if isinstance(raw.get("errors"), list) else [],
    }


def _acquisition(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}
    # This is explicitly the last run record, not the current source-health truth.
    return {
        "available": True,
        "snapshot_updated_at": _mtime_iso(path),
        "started_at": raw.get("started_at"),
        "source": raw.get("source"),
        "metro": raw.get("metro"),
        "real_data_only": raw.get("real_data_only"),
        "recorded_ok": raw.get("ok"),
        "returncode": raw.get("returncode"),
        "max_candidates": raw.get("max_candidates"),
    }




def _conversion(raw: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if raw is None:
        return {"available": False, "observed_at": _mtime_iso(path)}
    stages = raw.get("stages")
    unknown = raw.get("unknown_stages")
    return {
        "available": True,
        "observed_at": raw.get("observed_at") or _mtime_iso(path),
        "mode": raw.get("mode"),
        "source": raw.get("source"),
        "min_sample_size": raw.get("min_sample_size"),
        "primary_bottleneck": raw.get("primary_bottleneck"),
        "primary_bottleneck_rate": raw.get("primary_bottleneck_rate"),
        "experiment_candidate": raw.get("experiment_candidate"),
        "unknown_stages": unknown if isinstance(unknown, list) else [],
        "stages": stages if isinstance(stages, list) else [],
        "counts": raw.get("counts") if isinstance(raw.get("counts"), dict) else {},
        "execution_authority": raw.get("execution_authority", "none"),
    }

def _commercial_catalog(
    raw: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    if raw is None:
        return {
            "available": False,
            "observed_at": _mtime_iso(path),
            "product_count": 0,
            "binding_terms_ready_count": 0,
            "blocker_counts": {},
        }
    return {
        "available": True,
        "observed_at": _mtime_iso(path),
        "schema_version": raw.get("schema_version"),
        "product_count": int(raw.get("product_count") or 0),
        "active_count": int(raw.get("active_count") or 0),
        "binding_terms_ready_count": int(
            raw.get("binding_terms_ready_count") or 0
        ),
        "blocker_counts": (
            raw.get("blocker_counts")
            if isinstance(raw.get("blocker_counts"), dict)
            else {}
        ),
        "actual_revenue": False,
        "execution_authority": "none",
    }


def build_founder_dashboard(repo_root: Path) -> dict[str, Any]:
    runtime = repo_root / "runtime"
    loop_path = runtime / "commercial_loop" / "latest.json"
    astra_path = runtime / "astra" / "latest.json"
    acquisition_path = runtime / "acquisition" / "latest.json"
    source_path = runtime / "source_health" / "latest.json"
    conversion_path = runtime / "conversion" / "latest.json"
    catalog_path = runtime / "commercial_catalog" / "latest.json"

    raw_loop = _read_json(loop_path)
    conveyor = build_conveyor(raw_loop or {"stages": []})

    return {
        "mode": "OBSERVE",
        "side_effects": "none",
        "execution_authority": "none",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commercial_loop": _commercial_loop(raw_loop, loop_path),
        "control_conveyor": conveyor,
        "founder_gate": {
            "required": conveyor.get("authority") == "founder_gate",
            "current_blocker": conveyor.get("current_blocker"),
            "owner_component": conveyor.get("owner_component"),
            "next_event": conveyor.get("next_event"),
            "authority": conveyor.get("authority"),
        },
        "astra": _astra(_read_json(astra_path), astra_path),
        "acquisition": _acquisition(
            _read_json(acquisition_path),
            acquisition_path,
        ),
        "source_health": _source_health(_read_json(source_path), source_path),
        "conversion": _conversion(
            _read_json(conversion_path),
            conversion_path,
        ),
        "commercial_catalog": _commercial_catalog(
            _read_json(catalog_path),
            catalog_path,
        ),
        "permit_intelligence": build_permit_intelligence_runtime(repo_root),
        "property_intelligence": build_property_intelligence_runtime(repo_root),
        "private_capital_intelligence": (
            build_private_capital_intelligence_runtime(repo_root)
        ),
        "competitor_audience_intelligence": (
            build_competitor_audience_runtime(repo_root)
        ),
        "competitor_account_research": (
            build_account_research_runtime(repo_root)
        ),
        "recovery_portfolio": {
            "summary": recovery_summary(),
            "products": recovery_product_catalog(),
            "marketing_summary": marketing_summary(),
            "marketing_plans": marketing_plan_catalog(),
            "pricing_authority": "none",
            "execution_authority": "none",
            "actual_revenue": False,
        },
        "phases": _phase_projection(repo_root / "docs" / "BLUEPRINT_V6.md"),
    }
