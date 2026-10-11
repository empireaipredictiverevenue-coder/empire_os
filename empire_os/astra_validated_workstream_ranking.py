"""Evidence-derived Astra workstream ranking over the existing Router contract.

Advisory priority only. Never creates goals, actions, new agents, commercial
authority or independent buyer validation. Only safely mapped *existing*
internal blocker routes can change relative order inside Astra's existing
evidence completion lane, after first-revenue buyer actions and Quant work.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from empire_os.opportunity_evidence_router import ROUTES as CANONICAL_ROUTES

SCHEMA = "empire.astra.validated_workstream_ranking.v1"
ROUTER_SCHEMA = "empire.opportunity_evidence_routes.v1"
HISTORY_SCHEMA = "empire.opportunity_evidence_history.v1"
ELIGIBLE_STAGES = {"VALIDATE": 2, "EXPERIMENT": 3}
MAX_ROWS = 500
MAX_AGE = timedelta(hours=6)


def _held(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": reason, "validated_opportunity_count": 0,
        "ranked_workstream_count": 0,
        "workstreams": [], "route_priorities": [],
        "source_validation_is_not_buyer_acceptance": True,
        "commercial_authority": "none",
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }


def _stamp(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def rank_validated_workstreams(
    routes: Mapping[str, Any] | None,
    *,
    capability_components: Mapping[str, str],
    component_authorities: Mapping[str, str],
    department_owners: Mapping[str, tuple[str, ...]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Use current, corroborated *derived* validation to rank existing work.

    A new outcome is NOT verified by this function. It requires a current
    router + matching active router-history record, and maps only exact
    canonical internal work that was already eligible before ranking.
    """
    if (not isinstance(routes, Mapping)
            or routes.get("schema_version") != ROUTER_SCHEMA
            or routes.get("mode") != "OBSERVE"
            or routes.get("execution_authority") != "none"
            or routes.get("automatic_external_execution_allowed") is not False):
        return _held("ROUTER_NOT_TRUSTED_FOR_RANKING")
    observed = _stamp(routes.get("generated_at"))
    clock = now or datetime.now(timezone.utc)
    if (not isinstance(clock, datetime) or clock.tzinfo is None
            or observed is None):
        return _held("ROUTER_CLOCK_NOT_VERIFIED")
    age = clock.astimezone(timezone.utc) - observed
    if not -timedelta(minutes=5) <= age <= MAX_AGE:
        return _held("ROUTER_SNAPSHOT_STALE_OR_FUTURE")
    rows = routes.get("items")
    if (not isinstance(rows, list) or len(rows) > MAX_ROWS
            or type(routes.get("opportunity_count")) is not int
            or len(rows) != routes["opportunity_count"]
            or any(not isinstance(row, Mapping) for row in rows)):
        return _held("ROUTER_ROWS_INVALID")

    history = routes.get("history")
    if (not isinstance(history, Mapping)
            or history.get("schema_version") != HISTORY_SCHEMA
            or history.get("mode") != "OBSERVE"
            or history.get("execution_authority") != "none"
            or history.get("automatic_external_execution_allowed") is not False
            or history.get("commercial_stage_independently_verified") is not False
            or _stamp(history.get("generated_at")) != observed
            or history.get("previous_stage_never_promoted") is not True):
        return _held("MATCHING_CURRENT_HISTORY_REQUIRED")
    historical_rows = history.get("entries")
    if (not isinstance(historical_rows, list)
            or len(historical_rows) > MAX_ROWS
            or any(not isinstance(row, Mapping) for row in historical_rows)
            or type(history.get("tracked_identity_count")) is not int
            or len(historical_rows) != history["tracked_identity_count"]):
        return _held("ROUTER_HISTORY_ROWS_INVALID")

    current: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        key = row.get("opportunity_key")
        klass = row.get("opportunity_class")
        if (not isinstance(key, str) or not key
                or not isinstance(klass, str) or not klass
                or key in current):
            return _held("ROUTER_IDENTITY_DUPLICATE_OR_INVALID")
        current[key] = row
    historical: dict[str, Mapping[str, Any]] = {}
    for row in historical_rows:
        key = row.get("opportunity_key")
        if not isinstance(key, str) or not key or key in historical:
            return _held("ROUTER_HISTORY_IDENTITY_INVALID")
        historical[key] = row
    if set(current) - set(historical):
        return _held("ROUTER_HISTORY_NOT_BOUND_TO_CURRENT")

    # Count a validated *candidate* only if it has a current matching
    # history entry. Do not import historic stage from missing opportunities.
    eligible: dict[str, tuple[int, Mapping[str, Any]]] = {}
    for key, row in current.items():
        life = row.get("lifecycle")
        if not isinstance(life, Mapping):
            continue
        stage = life.get("current_stage")
        if (stage not in ELIGIBLE_STAGES
                or life.get("validated") is not True
                or life.get("commercial_validation_observed") is not True):
            continue
        if stage == "EXPERIMENT" and life.get("experiment_ready") is not True:
            continue
        past = historical[key]
        if (past.get("opportunity_class") != row.get("opportunity_class")
                or past.get("tenant_id") != row.get("tenant_id")
                or past.get("active_in_latest_cycle") is not True
                or past.get("missed_cycles") != 0
                or past.get("last_observed_stage") != stage
                or _stamp(past.get("last_seen_at")) != observed
                or past.get("stage_source") !=
                    "DERIVED_FROM_ROUTE_NOT_COMMERCIAL_PROOF"
                or past.get("execution_authority") != "none"):
            return _held("VALIDATED_LIFECYCLE_PROVENANCE_MISMATCH")
        eligible[key] = (ELIGIBLE_STAGES[stage], row)

    # Workstream assignment is a projection onto Astra's EXISTING map.
    # Unknown capabilities, route actions and non-internal work cannot rank.
    per_component: dict[str, dict[str, Any]] = {}
    priorities: list[tuple[int, str, str, str]] = []
    counted: set[str] = set()
    for key, (stage_tier, row) in sorted(eligible.items()):
        for route in row.get("routes") or []:
            if not isinstance(route, Mapping):
                continue
            blocker = route.get("blocker")
            canonical = CANONICAL_ROUTES.get(blocker) if isinstance(blocker, str) else None
            if canonical is None or any(
                route.get(field) != canonical[field]
                for field in ("capability", "action", "mode", "automatic_internal_work")
            ):
                continue
            if route.get("automatic_internal_work") is not True:
                continue
            if route.get("mode") not in {"internal_analysis", "internal_research"}:
                continue
            component = capability_components.get(route["capability"])
            if (not isinstance(component, str)
                    or component_authorities.get(component) not in {"observe", "internal_write"}
                    or component not in department_owners
                    or not department_owners[component]):
                continue
            score = per_component.setdefault(component, {
                "workstream": component,
                "department_keys": list(department_owners[component]),
                "opportunity_keys": set(), "existing_internal_blocker_count": 0,
                "highest_derived_lifecycle_stage": stage_tier,
            })
            score["highest_derived_lifecycle_stage"] = max(
                score["highest_derived_lifecycle_stage"], stage_tier
            )
            signature = (stage_tier, key, blocker, component)
            if signature not in priorities:
                priorities.append(signature)
                score["existing_internal_blocker_count"] += 1
                score["opportunity_keys"].add(key)
                counted.add(key)
    priorities.sort(key=lambda item: (-item[0], item[1], item[3], item[2]))
    workstreams = sorted(per_component.values(), key=lambda x: (
        -x["highest_derived_lifecycle_stage"],
        -len(x["opportunity_keys"]),
        -x["existing_internal_blocker_count"], x["workstream"],
    ))
    ranked = [{
        "rank": index + 1, "workstream": row["workstream"],
        "department_keys": row["department_keys"],
        "validated_opportunity_count": len(row["opportunity_keys"]),
        "opportunity_keys": sorted(row["opportunity_keys"]),
        "existing_internal_blocker_count": row["existing_internal_blocker_count"],
        "highest_derived_lifecycle_stage": (
            "EXPERIMENT" if row["highest_derived_lifecycle_stage"] == 3 else "VALIDATE"
        ),
        "authority_changed": False,
        "execution_authority": "none",
    } for index, row in enumerate(workstreams)]
    return {
        **_held("RANKED_FROM_CURRENT_DERIVED_VALIDATION"),
        "validated_opportunity_count": len(eligible),
        "validated_with_existing_internal_route_count": len(counted),
        "ranked_workstream_count": len(ranked),
        "workstreams": ranked,
        "route_priorities": [{
            "opportunity_key": key, "blocker": blocker,
            "target_component": component,
            "capability": CANONICAL_ROUTES[blocker]["capability"],
            "action": CANONICAL_ROUTES[blocker]["action"],
            "mode": CANONICAL_ROUTES[blocker]["mode"],
        } for tier, key, blocker, component in priorities],
    }
