"""Canonical evidence watchers for automated Empire Business Optimization.

Watchers never invent budgets, capacity, economics or evidence. They only
enqueue recommendation requests when both source evidence and an explicit
optimization policy are complete.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.business_optimization_automation import (
    enqueue_optimization_request,
)
from empire_os.business_optimization_product import WORKLOAD_SPECS


SCHEMA_VERSION = "empire.business_optimization_sources.v1"
POLICY_DIR = Path("runtime/business_optimization/policies")
OUTPUT = Path("runtime/business_optimization/source_readiness_latest.json")

OPPORTUNITY_VALUE = Path("runtime/opportunity_factory/value_latest.json")
OPPORTUNITY_RADAR = Path("runtime/opportunity_radar/latest.json")

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    key: {
        "source_adapter": (
            "opportunity_economics"
            if key in {"portfolio_strategy", "market_expansion"}
            else "policy_mapped_runtime_evidence"
        ),
        "source_adapter_implemented": True,
    }
    for key in WORKLOAD_SPECS
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _file_evidence_ref(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return f"{path.as_posix()}#sha256={sha256(data).hexdigest()}"


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _policy(
    root: Path,
    workload_type: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    path = root / POLICY_DIR / f"{workload_type}.json"
    packet = _read_json(path)
    blockers: list[str] = []
    if packet is None:
        return None, ["optimization_policy_not_configured"]
    if str(packet.get("status") or "").upper() not in {
        "APPROVED",
        "ACTIVE",
    }:
        blockers.append("optimization_policy_not_active")
    refs = [
        _text(value)
        for value in (packet.get("evidence_refs") or ())
        if _text(value)
    ]
    if not refs:
        blockers.append("optimization_policy_evidence_refs_required")
    if packet.get("time_budget_ms") is None:
        blockers.append("optimization_policy_time_budget_required")
    return packet, blockers


def _safe_runtime_source_path(
    root: Path,
    raw_path: Any,
) -> tuple[Path | None, str | None]:
    configured = _text(raw_path)
    if not configured:
        return None, "optimization_source_file_not_configured"
    candidate = Path(configured)
    if candidate.is_absolute():
        return None, "optimization_source_file_must_be_relative"
    resolved = (root / candidate).resolve()
    runtime_root = (root / "runtime").resolve()
    try:
        resolved.relative_to(runtime_root)
    except ValueError:
        return None, "optimization_source_file_outside_runtime"
    return resolved, None


def _rows_at_path(
    payload: Mapping[str, Any],
    rows_path: str,
) -> list[Mapping[str, Any]] | None:
    current: Any = payload
    for part in [value for value in rows_path.split(".") if value]:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    if not isinstance(current, list):
        return None
    return [row for row in current if isinstance(row, Mapping)]


def _policy_mapped_runtime_request(
    root: Path,
    *,
    workload_type: str,
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    source_path, source_error = _safe_runtime_source_path(
        root,
        policy.get("source_file"),
    )
    if source_error or source_path is None:
        return None, {
            "source_ready": False,
            "blockers": [source_error or "optimization_source_file_invalid"],
            "candidate_count": 0,
            "evidence_refs": [],
        }

    source = _read_json(source_path)
    source_ref = _file_evidence_ref(source_path)
    if source is None or not source_ref:
        return None, {
            "source_ready": False,
            "blockers": ["configured_runtime_source_unavailable"],
            "candidate_count": 0,
            "evidence_refs": [ref for ref in (source_ref,) if ref],
        }

    rows_path = _text(policy.get("rows_path"))
    if not rows_path:
        return None, {
            "source_ready": False,
            "blockers": ["optimization_rows_path_required"],
            "candidate_count": 0,
            "evidence_refs": [source_ref],
        }
    rows = _rows_at_path(source, rows_path)
    if rows is None:
        return None, {
            "source_ready": False,
            "blockers": ["optimization_rows_path_not_list"],
            "candidate_count": 0,
            "evidence_refs": [source_ref],
        }

    option_key_field = _text(policy.get("option_key_field"))
    entity_key_field = _text(policy.get("entity_key_field"))
    objective_field = _text(policy.get("objective_field"))
    if not option_key_field or not entity_key_field or not objective_field:
        missing = []
        if not option_key_field:
            missing.append("option_key_field")
        if not entity_key_field:
            missing.append("entity_key_field")
        if not objective_field:
            missing.append("objective_field")
        return None, {
            "source_ready": False,
            "blockers": [
                "optimization_source_mapping_incomplete:" + ",".join(missing)
            ],
            "candidate_count": 0,
            "evidence_refs": [source_ref],
        }

    row_evidence_field = _text(policy.get("row_evidence_refs_field"))
    status_field = _text(policy.get("status_field"))
    allowed_statuses = {
        _text(value).upper()
        for value in (policy.get("allowed_statuses") or ("AVAILABLE",))
        if _text(value)
    }
    resource_field_map = {
        _text(resource): _text(field)
        for resource, field in dict(
            policy.get("resource_field_map") or {}
        ).items()
        if _text(resource) and _text(field)
    }
    resource_limits = dict(policy.get("resource_limits") or {})
    partition_field = _text(policy.get("partition_field"))
    metadata_fields = [
        _text(value)
        for value in (policy.get("metadata_fields") or ())
        if _text(value)
    ]

    options: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        option_key = _text(raw.get(option_key_field))
        entity_key = _text(raw.get(entity_key_field))
        missing: list[str] = []
        if not option_key:
            missing.append(f"option_key:{option_key_field}")
        if not entity_key:
            missing.append(f"entity_key:{entity_key_field}")
        if status_field:
            status = _text(raw.get(status_field)).upper()
            if not status or status not in allowed_statuses:
                blocked_candidates.append({
                    "row_index": index,
                    "option_key": option_key or None,
                    "reason": "source_status_not_eligible",
                    "status": status or None,
                })
                continue
        objective = raw.get(objective_field)
        if objective is None:
            missing.append(f"objective_value:{objective_field}")

        refs = {source_ref}
        if row_evidence_field:
            observed_refs = raw.get(row_evidence_field)
            if isinstance(observed_refs, (list, tuple)):
                refs.update(
                    _text(ref)
                    for ref in observed_refs
                    if _text(ref)
                )
            elif _text(observed_refs):
                refs.add(_text(observed_refs))

        usage: dict[str, Any] = {}
        for resource in resource_limits:
            field = resource_field_map.get(_text(resource))
            if not field:
                missing.append(f"resource_field_map:{resource}")
                continue
            value = raw.get(field)
            if value is None:
                missing.append(f"resource_value:{resource}:{field}")
                continue
            usage[_text(resource)] = value

        if missing:
            blocked_candidates.append({
                "row_index": index,
                "option_key": option_key or None,
                "reason": "source_evidence_incomplete",
                "missing_fields": sorted(set(missing)),
            })
            continue

        options.append({
            "option_key": option_key,
            "entity_key": entity_key,
            "target_key": (
                _text(raw.get(_text(policy.get("target_key_field"))))
                if _text(policy.get("target_key_field"))
                else None
            ),
            "objective_value": objective,
            "resource_usage": usage,
            "partition_key": (
                _text(raw.get(partition_field))
                if partition_field
                else None
            ),
            "evidence_refs": sorted(refs),
            "metadata": {
                field: raw.get(field)
                for field in metadata_fields
                if field in raw
            },
        })

    generated_at_field = _text(
        policy.get("source_observed_at_field")
    ) or "generated_at"
    source_observed_at = _text(source.get(generated_at_field))
    if not source_observed_at:
        source_observed_at = datetime.fromtimestamp(
            source_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()

    if not options:
        return None, {
            "source_ready": False,
            "blockers": ["no_evidence_complete_source_candidates"],
            "candidate_count": 0,
            "blocked_candidate_count": len(blocked_candidates),
            "blocked_candidates": blocked_candidates[:50],
            "evidence_refs": [source_ref],
            "source_observed_at": source_observed_at,
        }

    request = {
        "workload_type": workload_type,
        "tenant_id": _text(policy.get("tenant_id")) or None,
        "options": options,
        "resource_limits": resource_limits,
        "selection_groups": list(policy.get("selection_groups") or ()),
        "dependencies": dict(policy.get("dependencies") or {}),
        "conflicts": list(policy.get("conflicts") or ()),
        "required_options": list(policy.get("required_options") or ()),
        "forbidden_options": list(policy.get("forbidden_options") or ()),
        "entity_selection": (
            dict(policy.get("entity_selection"))
            if isinstance(policy.get("entity_selection"), Mapping)
            else None
        ),
        "objective_sense": (
            _text(policy.get("objective_sense"))
            or WORKLOAD_SPECS[workload_type]["default_objective_sense"]
        ),
        "time_budget_ms": policy.get("time_budget_ms"),
        "cost_budget_minor_units": policy.get(
            "cost_budget_minor_units"
        ),
    }
    return request, {
        "source_ready": True,
        "blockers": [],
        "candidate_count": len(options),
        "blocked_candidate_count": len(blocked_candidates),
        "blocked_candidates": blocked_candidates[:50],
        "evidence_refs": [source_ref],
        "source_observed_at": source_observed_at,
        "configured_source_file": str(source_path.relative_to(root)),
        "rows_path": rows_path,
    }


def _opportunity_economics_request(
    root: Path,
    *,
    workload_type: str,
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    value_path = root / OPPORTUNITY_VALUE
    radar_path = root / OPPORTUNITY_RADAR
    value = _read_json(value_path)
    radar = _read_json(radar_path)
    value_ref = _file_evidence_ref(value_path)
    radar_ref = _file_evidence_ref(radar_path)

    blockers: list[str] = []
    if value is None or not value_ref:
        blockers.append("opportunity_value_source_unavailable")
    if radar is None or not radar_ref:
        blockers.append("opportunity_radar_source_unavailable")
    if blockers:
        return None, {
            "source_ready": False,
            "blockers": blockers,
            "candidate_count": 0,
            "evidence_refs": [
                ref for ref in (value_ref, radar_ref) if ref
            ],
        }

    radar_by_key = {
        _text(row.get("opportunity_key")): row
        for row in (radar.get("candidates") or ())
        if isinstance(row, Mapping)
        and _text(row.get("opportunity_key"))
    }
    objective_field = _text(
        policy.get("objective_field")
    ) or "expected_gross_profit_cents"
    resource_field_map = {
        _text(resource): _text(field)
        for resource, field in dict(
            policy.get("resource_field_map") or {}
        ).items()
        if _text(resource) and _text(field)
    }
    resource_limits = dict(policy.get("resource_limits") or {})

    options: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    for raw in value.get("items") or ():
        if not isinstance(raw, Mapping):
            continue
        key = _text(raw.get("opportunity_key"))
        if not key:
            continue
        if str(raw.get("status") or "").upper() != "AVAILABLE":
            blocked_candidates.append({
                "opportunity_key": key,
                "reason": "opportunity_value_unavailable",
            })
            continue
        objective = raw.get(objective_field)
        quant = (
            raw.get("quant_input_evidence")
            if isinstance(raw.get("quant_input_evidence"), Mapping)
            else {}
        )
        refs = {
            _text(ref)
            for ref in (quant.get("evidence_refs") or ())
            if _text(ref)
        }
        radar_row = radar_by_key.get(key)
        if radar_row:
            refs.update(
                _text(ref)
                for ref in (radar_row.get("evidence_refs") or ())
                if _text(ref)
            )
        refs.update((value_ref, radar_ref))
        missing: list[str] = []
        if objective is None:
            missing.append(objective_field)
        if not refs:
            missing.append("evidence_refs")

        usage: dict[str, Any] = {}
        for resource in resource_limits:
            field = resource_field_map.get(_text(resource))
            if not field:
                missing.append(f"resource_field_map:{resource}")
                continue
            observed = raw.get(field)
            if observed is None:
                missing.append(f"resource_value:{resource}:{field}")
                continue
            usage[_text(resource)] = observed

        if workload_type == "market_expansion":
            if not radar_row:
                missing.append("market_identity")
            elif radar_row.get("opportunity_factory_ready") is not True:
                missing.append("opportunity_factory_ready")

        if missing:
            blocked_candidates.append({
                "opportunity_key": key,
                "reason": "source_evidence_incomplete",
                "missing_fields": sorted(set(missing)),
            })
            continue

        options.append({
            "option_key": key,
            "entity_key": key,
            "objective_value": objective,
            "resource_usage": usage,
            "partition_key": (
                _text(radar_row.get("metro"))
                if radar_row
                else None
            ),
            "evidence_refs": sorted(refs),
            "metadata": {
                "opportunity_class": raw.get("opportunity_class"),
                "metro": radar_row.get("metro") if radar_row else None,
                "niche": radar_row.get("niche") if radar_row else None,
                "source_value_rank": raw.get("rank"),
            },
        })

    source_observed_at = (
        _text(value.get("generated_at"))
        or _text(radar.get("generated_at"))
    )
    if not options:
        return None, {
            "source_ready": False,
            "blockers": ["no_evidence_complete_source_candidates"],
            "candidate_count": 0,
            "blocked_candidate_count": len(blocked_candidates),
            "blocked_candidates": blocked_candidates[:50],
            "evidence_refs": [value_ref, radar_ref],
            "source_observed_at": source_observed_at or None,
        }

    request = {
        "workload_type": workload_type,
        "tenant_id": _text(policy.get("tenant_id")) or None,
        "options": options,
        "resource_limits": resource_limits,
        "objective_sense": (
            _text(policy.get("objective_sense")) or "MAXIMIZE"
        ),
        "time_budget_ms": policy.get("time_budget_ms"),
        "cost_budget_minor_units": policy.get(
            "cost_budget_minor_units"
        ),
    }
    return request, {
        "source_ready": True,
        "blockers": [],
        "candidate_count": len(options),
        "blocked_candidate_count": len(blocked_candidates),
        "blocked_candidates": blocked_candidates[:50],
        "evidence_refs": [value_ref, radar_ref],
        "source_observed_at": source_observed_at or None,
    }


def run_business_optimization_source_cycle(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Observe domain sources and enqueue only newly ready evidence states."""
    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows: dict[str, dict[str, Any]] = {}
    enqueued_count = 0
    ready_count = 0

    for workload_type in sorted(WORKLOAD_SPECS):
        spec = SOURCE_SPECS[workload_type]
        policy, policy_blockers = _policy(root, workload_type)
        row: dict[str, Any] = {
            "workload_type": workload_type,
            "source_adapter": spec["source_adapter"],
            "source_adapter_implemented": spec[
                "source_adapter_implemented"
            ],
            "policy_ready": not policy_blockers,
            "source_ready": False,
            "automation_ready": False,
            "enqueued": False,
            "blockers": list(policy_blockers),
        }
        if not spec["source_adapter_implemented"]:
            row["blockers"].append("source_adapter_not_implemented")
            rows[workload_type] = row
            continue
        if policy_blockers or policy is None:
            rows[workload_type] = row
            continue

        if spec["source_adapter"] == "opportunity_economics":
            request, source = _opportunity_economics_request(
                root,
                workload_type=workload_type,
                policy=policy,
            )
        elif spec["source_adapter"] == "policy_mapped_runtime_evidence":
            request, source = _policy_mapped_runtime_request(
                root,
                workload_type=workload_type,
                policy=policy,
            )
        else:
            request, source = None, {
                "source_ready": False,
                "blockers": ["source_adapter_not_implemented"],
            }

        contract_request, contract_source = _canonical_contract_request(
            root,
            workload_type=workload_type,
            policy=policy,
        )
        if contract_request is not None:
            request, source = contract_request, contract_source

        row.update(source)
        row["blockers"] = sorted(set([
            *row.get("blockers", []),
            *source.get("blockers", []),
        ]))
        row["automation_ready"] = (
            request is not None
            and source.get("source_ready") is True
            and not row["blockers"]
        )
        if row["automation_ready"]:
            ready_count += 1
            observed_at = (
                _text(source.get("source_observed_at"))
                or current.isoformat()
            )
            event_refs = [
                _text(ref)
                for ref in (source.get("evidence_refs") or ())
                if _text(ref)
            ]
            event_ref = "|".join(sorted(event_refs))
            enqueue = enqueue_optimization_request(
                root,
                request,
                event_ref=event_ref,
                observed_at=observed_at,
            )
            row["enqueue"] = enqueue
            row["enqueued"] = enqueue.get("enqueued") is True
            enqueued_count += int(row["enqueued"])

        rows[workload_type] = row

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "workload_count": len(rows),
        "source_adapter_implemented_count": sum(
            row["source_adapter_implemented"] is True
            for row in rows.values()
        ),
        "automation_ready_count": ready_count,
        "ready_workload_count": ready_count,
        "blocked_workload_count": len(rows) - ready_count,
        "enqueued_count": enqueued_count,
        "generated_request_count": enqueued_count,
        "synthetic_economics_generated": False,
        "workloads": rows,
        "unknown_is_zero": False,
        "automatic_business_action_allowed": False,
        "third_party_service_called": False,
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload


def materialize_business_optimization_sources(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compatibility view for the canonical source-watcher cycle."""
    result = run_business_optimization_source_cycle(repo_root, now=now)
    ready = int(result.get("automation_ready_count") or 0)
    total = int(result.get("workload_count") or 0)
    return {
        **result,
        "ready_workload_count": ready,
        "blocked_workload_count": max(0, total - ready),
        "generated_request_count": int(result.get("enqueued_count") or 0),
    }


SOURCE_INPUT_DIR = Path("runtime/business_optimization/source_inputs")


def publish_business_optimization_source(
    repo_root: str | Path,
    *,
    workload_type: str,
    options: list[Mapping[str, Any]],
    source_ref: str,
    observed_at: str,
    evidence_refs: list[str],
    tenant_id: str | None = None,
    selection_groups: list[Mapping[str, Any]] | None = None,
    dependencies: Mapping[str, list[str]] | None = None,
    conflicts: list[list[str]] | None = None,
    required_options: list[str] | None = None,
    forbidden_options: list[str] | None = None,
    entity_selection: Mapping[str, Any] | None = None,
    policy_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish one canonical internal source snapshot for any product domain."""
    workload = _text(workload_type)
    if workload not in WORKLOAD_SPECS:
        raise ValueError(f"unsupported workload_type:{workload}")
    ref = _text(source_ref)
    if not ref:
        raise ValueError("source_ref required")
    timestamp = _text(observed_at)
    if not timestamp:
        raise ValueError("observed_at required")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    refs = sorted({
        _text(value)
        for value in evidence_refs
        if _text(value)
    })
    if not refs:
        raise ValueError("evidence_refs required")

    packet = {
        "schema_version": "empire.business_optimization.source-input.v1",
        "status": "AVAILABLE",
        "workload_type": workload,
        "tenant_id": _text(tenant_id) or None,
        "source_ref": ref,
        "observed_at": parsed.isoformat(),
        "evidence_refs": refs,
        "options": [
            dict(row)
            for row in options
            if isinstance(row, Mapping)
        ],
        "selection_groups": [
            dict(row)
            for row in (selection_groups or ())
            if isinstance(row, Mapping)
        ],
        "dependencies": {
            str(key): list(values)
            for key, values in dict(dependencies or {}).items()
        },
        "conflicts": list(conflicts or ()),
        "required_options": list(required_options or ()),
        "forbidden_options": list(forbidden_options or ()),
        "entity_selection": (
            dict(entity_selection)
            if isinstance(entity_selection, Mapping)
            else None
        ),
        "policy_contract": (
            dict(policy_contract)
            if isinstance(policy_contract, Mapping)
            else None
        ),
        "automatic_business_action_allowed": False,
        "third_party_service_called": False,
        "execution_authority": "none",
    }
    root = Path(repo_root).resolve()
    path = root / SOURCE_INPUT_DIR / f"{workload}.json"
    _atomic_write(path, packet)
    return {
        "schema_version": "empire.business_optimization.source-publish.v1",
        "status": "AVAILABLE",
        "workload_type": workload,
        "source_ref": ref,
        "observed_at": parsed.isoformat(),
        "source_input_ref": str(path.relative_to(root)),
        "option_count": len(packet["options"]),
        "automatic_business_action_allowed": False,
        "execution_authority": "none",
    }


def _canonical_contract_request(
    root: Path,
    *,
    workload_type: str,
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    path = root / SOURCE_INPUT_DIR / f"{workload_type}.json"
    source = _read_json(path)
    evidence_ref = _file_evidence_ref(path)
    if source is None or not evidence_ref:
        return None, {
            "source_ready": False,
            "blockers": ["canonical_source_input_unavailable"],
            "candidate_count": 0,
            "evidence_refs": [],
        }
    if str(source.get("status") or "").upper() != "AVAILABLE":
        return None, {
            "source_ready": False,
            "blockers": ["canonical_source_input_not_available"],
            "candidate_count": 0,
            "evidence_refs": [evidence_ref],
        }
    if _text(source.get("workload_type")) != workload_type:
        return None, {
            "source_ready": False,
            "blockers": ["canonical_source_workload_mismatch"],
            "candidate_count": 0,
            "evidence_refs": [evidence_ref],
        }
    options = [
        dict(row)
        for row in (source.get("options") or ())
        if isinstance(row, Mapping)
    ]
    if not options:
        return None, {
            "source_ready": False,
            "blockers": ["canonical_source_has_no_options"],
            "candidate_count": 0,
            "evidence_refs": [evidence_ref],
        }
    refs = sorted({
        evidence_ref,
        *(
            _text(value)
            for value in (source.get("evidence_refs") or ())
            if _text(value)
        ),
    })
    request = {
        "workload_type": workload_type,
        "tenant_id": (
            _text(source.get("tenant_id"))
            or _text(policy.get("tenant_id"))
            or None
        ),
        "options": options,
        "resource_limits": dict(policy.get("resource_limits") or {}),
        "selection_groups": list(source.get("selection_groups") or ()),
        "dependencies": dict(source.get("dependencies") or {}),
        "conflicts": list(source.get("conflicts") or ()),
        "required_options": list(source.get("required_options") or ()),
        "forbidden_options": list(source.get("forbidden_options") or ()),
        "entity_selection": source.get("entity_selection"),
        "objective_sense": (
            _text(policy.get("objective_sense")) or None
        ),
        "time_budget_ms": policy.get("time_budget_ms"),
        "cost_budget_minor_units": policy.get("cost_budget_minor_units"),
    }
    return request, {
        "source_ready": True,
        "blockers": [],
        "candidate_count": len(options),
        "evidence_refs": refs,
        "source_observed_at": source.get("observed_at"),
        "source_ref": source.get("source_ref"),
    }
