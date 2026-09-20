"""Bounded AUTO enrichment execution for Empire Hunter."""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from empire_os.hunter.domain_intelligence import analyze_domain
from empire_os.hunter.evidence_graph import build_evidence_plan
from empire_os.hunter.materializer import SupabaseHunterMaterializer
from empire_os.hunter.priority_worker import build_priority_queue
from empire_os.qualification_worker_v2 import request_json


DEPTH_PAGES = {
    "shallow": 4,
    "standard": 7,
    "deep": 12,
}


DEFAULT_STATE_PATH = Path(
    "/srv/empire_os/runtime/hunter/enrichment_state.json"
)


def _load_state(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_state(path: str | Path, state: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)


def _cooldown_active(
    *,
    entity_id: str,
    state: dict[str, Any],
    now: datetime,
    cooldown_hours: float,
) -> bool:
    row = state.get(entity_id)
    if not isinstance(row, dict):
        return False
    raw = str(row.get("last_attempt_at") or "").strip()
    if not raw:
        return False
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        last = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    if last.tzinfo is None:
        return False
    return (
        now.astimezone(timezone.utc)
        - last.astimezone(timezone.utc)
    ) < timedelta(hours=max(0.0, cooldown_hours))


def _get(path: str, params: dict[str, str]) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(params)
    rows = request_json("GET", f"{path}?{query}") or []
    return [row for row in rows if isinstance(row, dict)]


def _entity(entity_id: str) -> dict[str, Any] | None:
    rows = _get(
        "/rest/v1/business_entities",
        {
            "select": (
                "id,canonical_name,canonical_website,"
                "identity_confidence,resolution_state"
            ),
            "id": f"eq.{entity_id}",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


def run_hunter_enrichment_cycle(
    *,
    limit: int = 3,
    write_authorized: bool = True,
    cooldown_hours: float = 6.0,
    state_path: str | Path = DEFAULT_STATE_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    bounded = max(1, min(int(limit), 5))
    current = (now or datetime.now(timezone.utc)).astimezone(
        timezone.utc
    )
    queue = build_priority_queue(25)
    eligible = [
        item for item in queue.get("items", [])
        if (
            isinstance(item, dict)
            and item.get("contact_ready") is not True
            and item.get("depth") in DEPTH_PAGES
        )
    ]

    state = _load_state(state_path)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    skipped_cooldown = 0
    materializer = SupabaseHunterMaterializer()

    for item in eligible:
        if len(results) + len(errors) >= bounded:
            break
        entity_id = str(item.get("entity_id") or "").strip()
        if _cooldown_active(
            entity_id=entity_id,
            state=state,
            now=current,
            cooldown_hours=cooldown_hours,
        ):
            skipped_cooldown += 1
            continue
        try:
            entity = _entity(entity_id)
            if not entity:
                raise RuntimeError("canonical entity not found")
            website = str(
                entity.get("canonical_website") or ""
            ).strip()
            if not website:
                raise RuntimeError("canonical website missing")

            depth = str(item.get("depth") or "shallow")
            report = analyze_domain(
                website,
                max_pages=DEPTH_PAGES[depth],
                request_timeout=5.0,
                time_budget_seconds=35.0,
            )
            plan = build_evidence_plan(
                report,
                entity_id=entity_id,
            )
            write_result = materializer.materialize(
                plan,
                write_authorized=write_authorized,
            )
            state[entity_id] = {
                "last_attempt_at": current.isoformat(),
                "status": "processed",
                "depth": depth,
            }
            results.append({
                "entity_id": entity_id,
                "canonical_name": entity.get("canonical_name"),
                "website": website,
                "priority_score": item.get("priority_score"),
                "depth": depth,
                "pages_checked": report.pages_checked,
                "evidence_score": report.evidence_score,
                "contacts_observed": len(report.contacts),
                "confirmed_contacts": len(
                    report.confirmed_contacts
                ),
                "outreach_ready": report.outreach_ready,
                "materialization": write_result,
            })
        except Exception as exc:
            state[entity_id] = {
                "last_attempt_at": current.isoformat(),
                "status": "failed",
            }
            errors.append({
                "entity_id": entity_id,
                "error": f"{type(exc).__name__}:{str(exc)[:300]}",
            })

    _write_state(state_path, state)

    return {
        "schema_version": "empire_hunter_enrichment_cycle.v1",
        "mode": (
            "INTERNAL_MATERIALIZE"
            if write_authorized
            else "OBSERVE"
        ),
        "write_authorized": write_authorized,
        "candidates_seen": len(eligible),
        "processed": len(results),
        "failed": len(errors),
        "skipped_cooldown": skipped_cooldown,
        "results": results,
        "errors": errors,
        "outbound_actions": False,
        "payment_actions": False,
        "revenue_actions": False,
    }


def write_enrichment_snapshot(
    result: dict[str, Any],
    path: str | Path = (
        "/srv/empire_os/runtime/hunter/enrichment_latest.json"
    ),
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target
