"""Read-only founder dashboard projection from canonical runtime evidence."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def build_founder_dashboard(repo_root: Path) -> dict[str, Any]:
    runtime = repo_root / "runtime"
    loop_path = runtime / "commercial_loop" / "latest.json"
    astra_path = runtime / "astra" / "latest.json"
    acquisition_path = runtime / "acquisition" / "latest.json"
    source_path = runtime / "source_health" / "latest.json"

    return {
        "mode": "OBSERVE",
        "side_effects": "none",
        "execution_authority": "none",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commercial_loop": _commercial_loop(_read_json(loop_path), loop_path),
        "astra": _astra(_read_json(astra_path), astra_path),
        "acquisition": _acquisition(
            _read_json(acquisition_path),
            acquisition_path,
        ),
        "source_health": _source_health(_read_json(source_path), source_path),
        "phases": _phase_projection(repo_root / "docs" / "BLUEPRINT_V6.md"),
    }
