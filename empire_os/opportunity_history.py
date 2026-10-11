"""Bounded, observation-only Opportunity Radar lifecycle history.

Reuses the canonical Evidence Router output, never promotes an old stage,
buyer intent, offer economics, external execution or commercial authority.
The history lives inside the existing atomic evidence_routes_latest.json;
there is no new store, worker, timer or migration.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re
from typing import Any, Mapping

from empire_os.opportunity_lifecycle import STAGES

SCHEMA = "empire.opportunity_evidence_history.v1"
ROUTES_SCHEMA = "empire.opportunity_evidence_routes.v1"
MAX_IDENTITIES = 500
# Existing canonical market keys preserve metro labels ("baltimore, md");
# reject addresses, control characters, markup, query strings or free text.
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/, -]{2,219}$")
_CLASS = re.compile(r"^[a-z][a-z0-9_]{2,69}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,99}$")


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 45:
        raise ValueError("HISTORY_TIMESTAMP_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("HISTORY_TIMESTAMP_INVALID") from exc
    if result.tzinfo is None:
        raise ValueError("HISTORY_TIMESTAMP_NOT_AWARE")
    return result.astimezone(timezone.utc)


def _identity(row: Mapping[str, Any]) -> tuple[str, str, str | None]:
    key = row.get("opportunity_key")
    klass = row.get("opportunity_class")
    tenant = row.get("tenant_id")
    if (not isinstance(key, str) or not _KEY.fullmatch(key)
            or not isinstance(klass, str) or not _CLASS.fullmatch(klass)
            or tenant is not None and (
                not isinstance(tenant, str) or not _TENANT.fullmatch(tenant)
            )):
        raise ValueError("HISTORY_IDENTITY_NOT_CANONICAL")
    return key, klass, tenant


def _bounded_items(
    payload: Mapping[str, Any], *, previous: bool
) -> tuple[datetime, list[Mapping[str, Any]]]:
    if (not isinstance(payload, Mapping)
            or payload.get("schema_version") != ROUTES_SCHEMA
            or payload.get("mode") != "OBSERVE"
            or payload.get("execution_authority") != "none"
            or payload.get("automatic_external_execution_allowed") is not False):
        raise ValueError("HISTORY_ROUTER_SOURCE_UNTRUSTED")
    generated = _time(payload.get("generated_at"))
    raw = payload.get("items")
    if (not isinstance(raw, list)
            or len(raw) > MAX_IDENTITIES
            or any(not isinstance(item, Mapping) for item in raw)):
        raise ValueError("HISTORY_ROUTE_ITEMS_INVALID")
    if (type(payload.get("opportunity_count")) is not int
            or len(raw) != payload["opportunity_count"]):
        raise ValueError("HISTORY_ROUTE_COUNT_MISMATCH")
    return generated, raw


def _records_from_legacy(
    routes: Mapping[str, Any],
) -> list[dict[str, Any]]:
    generated, items = _bounded_items(routes, previous=True)
    existing: dict[str, dict[str, Any]] = {}
    for item in items:
        key, klass, tenant = _identity(item)
        lifecycle = item.get("lifecycle")
        stage = lifecycle.get("current_stage") if isinstance(lifecycle, Mapping) else None
        if stage not in STAGES or key in existing:
            raise ValueError("HISTORY_LEGACY_DUPLICATE_OR_INVALID_STAGE")
        existing[key] = {
            "opportunity_key": key,
            "opportunity_class": klass,
            "tenant_id": tenant,
            "first_seen_at": generated.isoformat(),
            "last_seen_at": generated.isoformat(),
            "observation_count": 1,
            "missed_cycles": 0,
            "active_in_latest_cycle": True,
            "last_observed_stage": stage,
            "stage_transition_count": 0,
            "stage_source": "DERIVED_FROM_ROUTE_NOT_COMMERCIAL_PROOF",
            "execution_authority": "none",
        }
    return list(existing.values())


def _load_previous(previous: Mapping[str, Any] | None) -> tuple[str, list[dict[str, Any]], datetime | None]:
    if previous is None:
        return "INITIAL", [], None

    generated, _ = _bounded_items(previous, previous=True)
    history = previous.get("history")
    if history is None:
        return "BOOTSTRAPPED_PREVIOUS_ROUTE", _records_from_legacy(previous), generated
    if (not isinstance(history, Mapping)
            or history.get("schema_version") != SCHEMA
            or history.get("mode") != "OBSERVE"
            or history.get("execution_authority") != "none"):
        raise ValueError("HISTORY_PREVIOUS_INVALID")
    rows = history.get("entries")
    if (not isinstance(rows, list) or len(rows) > MAX_IDENTITIES
            or any(not isinstance(row, Mapping) for row in rows)):
        raise ValueError("HISTORY_PREVIOUS_ROWS_INVALID")
    old: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key, klass, tenant = _identity(row)
        first = _time(row.get("first_seen_at"))
        last = _time(row.get("last_seen_at"))
        stage = row.get("last_observed_stage")
        count = row.get("observation_count")
        misses = row.get("missed_cycles")
        transitions = row.get("stage_transition_count")
        if (key in seen or stage not in STAGES
                or row.get("stage_source") != "DERIVED_FROM_ROUTE_NOT_COMMERCIAL_PROOF"
                or row.get("execution_authority") != "none"
                or not first <= last <= generated
                or type(count) is not int or not 1 <= count <= 1_000_000
                or type(misses) is not int or not 0 <= misses <= 1_000_000
                or type(transitions) is not int or not 0 <= transitions <= count
                or row.get("active_in_latest_cycle") is not (misses == 0)):
            raise ValueError("HISTORY_PREVIOUS_ROW_CONFLICT")
        seen.add(key)
        old.append({
            "opportunity_key": key, "opportunity_class": klass, "tenant_id": tenant,
            "first_seen_at": first.isoformat(), "last_seen_at": last.isoformat(),
            "observation_count": count, "missed_cycles": misses,
            "active_in_latest_cycle": misses == 0,
            "last_observed_stage": stage, "stage_transition_count": transitions,
            "stage_source": "DERIVED_FROM_ROUTE_NOT_COMMERCIAL_PROOF",
            "execution_authority": "none",
        })
    return "CONTINUING", old, generated


def build_opportunity_history(
    current_routes: Mapping[str, Any],
    previous_routes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Dedupe repeated cycles by exact key, preserving *observed* stages.

    A disappeared opportunity is MISSING, not retired. Any stage regression is
    retained and counted instead of falsely restoring the former high stage.
    Duplicate, changed-tenant or changed-class keys fail closed.
    """
    now, items = _bounded_items(current_routes, previous=False)
    state, historical, previous_at = _load_previous(previous_routes)
    if previous_at is not None and now <= previous_at:
        raise ValueError("HISTORY_CYCLE_MUST_ADVANCE")
    previous_by_key = {row["opportunity_key"]: row for row in historical}
    new_rows: dict[str, dict[str, Any]] = {}
    for raw in items:
        key, klass, tenant = _identity(raw)
        if key in new_rows:
            raise ValueError("HISTORY_DUPLICATE_CURRENT_KEY")
        lifecycle = raw.get("lifecycle")
        stage = lifecycle.get("current_stage") if isinstance(lifecycle, Mapping) else None
        if stage not in STAGES:
            raise ValueError("HISTORY_CURRENT_STAGE_UNTRUSTED")
        old = previous_by_key.get(key)
        if old is not None and (
            old["opportunity_class"] != klass or old["tenant_id"] != tenant
        ):
            raise ValueError("HISTORY_CROSS_TENANT_OR_CLASS_COLLISION")
        new_rows[key] = {
            "opportunity_key": key, "opportunity_class": klass, "tenant_id": tenant,
            "first_seen_at": old["first_seen_at"] if old else now.isoformat(),
            "last_seen_at": now.isoformat(),
            "observation_count": old["observation_count"] + 1 if old else 1,
            "missed_cycles": 0, "active_in_latest_cycle": True,
            "last_observed_stage": stage,
            "stage_transition_count": (
                old["stage_transition_count"] + int(old["last_observed_stage"] != stage)
                if old else 0
            ),
            "stage_source": "DERIVED_FROM_ROUTE_NOT_COMMERCIAL_PROOF",
            "execution_authority": "none",
        }
        if new_rows[key]["observation_count"] > 1_000_000:
            raise ValueError("HISTORY_OBSERVATION_COUNT_EXCEEDED")

    absent = 0
    for key, old in previous_by_key.items():
        if key in new_rows:
            continue
        if old["missed_cycles"] >= 1_000_000:
            raise ValueError("HISTORY_MISSED_CYCLES_EXCEEDED")
        missing = dict(old)
        missing["missed_cycles"] += 1
        missing["active_in_latest_cycle"] = False
        new_rows[key] = missing
        absent += 1
    if len(new_rows) > MAX_IDENTITIES:
        raise ValueError("HISTORY_RETENTION_LIMIT_HELD")

    ordered = [new_rows[key] for key in sorted(new_rows)]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": now.isoformat(), "previous_source_status": state,
        "tracked_identity_count": len(ordered),
        "active_identity_count": len(items),
        "not_observed_in_latest_cycle_count": absent,
        "new_identity_count": sum(
            key not in previous_by_key for key in new_rows
        ),
        "reappeared_count": sum(
            key in previous_by_key and previous_by_key[key]["missed_cycles"] > 0
            for key in new_rows if new_rows[key]["active_in_latest_cycle"]
        ),
        "stage_transition_count_this_cycle": sum(
            key in previous_by_key
            and new_rows[key]["active_in_latest_cycle"]
            and new_rows[key]["last_observed_stage"] != previous_by_key[key]["last_observed_stage"]
            for key in new_rows
        ),
        "stage_counts_current": dict(sorted(Counter(
            row["last_observed_stage"] for row in ordered
            if row["active_in_latest_cycle"]
        ).items())),
        "previous_stage_never_promoted": True,
        "commercial_stage_independently_verified": False,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
        "entries": ordered,
    }
