"""Automated recommendation cycle for Empire Business Optimization.

Reads bounded, evidence-backed request packets from runtime, compiles them into
the shared Empire Optimization IR, runs only Empire-owned solver paths, records
recommendations, benchmarks safe small problems, and emits change signals.

This worker never performs the business action represented by a recommendation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from empire_os.business_optimization_product import (
    build_business_optimization_preview,
    build_enterprise_portfolio_preview,
)
from empire_os.optimization_benchmark_arena import run_benchmark_arena
from empire_os.solver_performance_memory import (
    build_solver_performance_memory,
    recommend_benchmark_solver,
)


SCHEMA_VERSION = "empire.business_optimization_automation.v1"
INBOX = Path("runtime/business_optimization/inbox")
PROCESSING = Path("runtime/business_optimization/processing")
ARCHIVE = Path("runtime/business_optimization/archive")
INVALID = Path("runtime/business_optimization/invalid")
ENQUEUE_STATE = Path("runtime/business_optimization/enqueue_state")
RESULTS = Path("runtime/business_optimization/results")
LATEST = Path("runtime/business_optimization/latest")
CHANGES = Path("runtime/business_optimization/changes")
CYCLE_OUTPUT = Path("runtime/business_optimization/automation_latest.json")
BENCHMARK_HISTORY = Path("runtime/business_optimization/benchmark_history")
SOLVER_MEMORY_OUTPUT = Path("runtime/business_optimization/solver_performance_memory_latest.json")
SOLVER_RECOMMENDATION_OUTPUT = Path("runtime/business_optimization/solver_recommendation_latest.json")
_SAFE_ID = re.compile(r"[^A-Za-z0-9_.:-]+")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_id(value: Any, fallback: str) -> str:
    text = _SAFE_ID.sub("_", _text(value)).strip("._:-")
    return text[:160] or fallback


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(
            f"{path.stem}__{counter}{path.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def _claim_inbox_file(root: Path, path: Path) -> Path | None:
    processing_dir = root / PROCESSING
    processing_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(processing_dir / path.name)
    try:
        path.replace(destination)
    except FileNotFoundError:
        return None
    return destination


def _archive_processing_file(
    root: Path,
    path: Path,
    *,
    current: datetime,
    invalid: bool = False,
) -> Path:
    bucket = INVALID if invalid else ARCHIVE
    destination_dir = (
        root / bucket
        / current.strftime("%Y")
        / current.strftime("%m")
        / current.strftime("%d")
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(destination_dir / path.name)
    path.replace(destination)
    return destination


def _recommendation_signature(preview: Mapping[str, Any]) -> dict[str, Any]:
    result = preview.get("result")
    result = result if isinstance(result, Mapping) else {}
    inner = result.get("result")
    inner = inner if isinstance(inner, Mapping) else {}
    return {
        "selected_variables": sorted(
            str(value)
            for value in (inner.get("selected_variables") or ())
        ),
        "objective_value": inner.get("objective_value"),
        "solver": inner.get("solver"),
        "constraints_satisfied": inner.get("constraints_satisfied"),
    }


def _previous_latest(
    root: Path,
    *,
    tenant_id: str,
    workload_type: str,
) -> dict[str, Any] | None:
    tenant_key = _safe_id(tenant_id, "default")
    workload_key = _safe_id(workload_type, "unknown")
    return _read_json(root / LATEST / tenant_key / f"{workload_key}.json")


def _request_payload(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    workload_type = _text(request.get("workload_type"))
    common = {
        "options": list(request.get("options") or ()),
        "objective_sense": request.get("objective_sense"),
        "tenant_id": _text(request.get("tenant_id")) or None,
        "time_budget_ms": request.get("time_budget_ms"),
        "cost_budget_minor_units": request.get(
            "cost_budget_minor_units"
        ),
    }
    if workload_type == "enterprise_portfolio_strategy":
        return {
            "enterprise": True,
            "objective_unit": request.get("objective_unit"),
            "resource_limits": dict(request.get("resource_limits") or {}),
            **common,
        }
    return {
        "enterprise": False,
        "resource_limits": dict(request.get("resource_limits") or {}),
        "selection_groups": list(request.get("selection_groups") or ()),
        "dependencies": dict(request.get("dependencies") or {}),
        "conflicts": list(request.get("conflicts") or ()),
        "required_options": list(request.get("required_options") or ()),
        "forbidden_options": list(request.get("forbidden_options") or ()),
        "entity_selection": (
            dict(request.get("entity_selection"))
            if isinstance(request.get("entity_selection"), Mapping)
            else None
        ),
        **common,
    }


def _build_preview(request: Mapping[str, Any]) -> dict[str, Any]:
    workload_type = _text(request.get("workload_type"))
    payload = _request_payload(request)
    if payload.pop("enterprise"):
        return build_enterprise_portfolio_preview(
            options=payload["options"],
            objective_unit=_text(payload.get("objective_unit")),
            resource_limits=payload["resource_limits"],
            objective_sense=(
                _text(payload.get("objective_sense")) or "MAXIMIZE"
            ),
            tenant_id=payload.get("tenant_id"),
            time_budget_ms=payload.get("time_budget_ms"),
            cost_budget_minor_units=payload.get(
                "cost_budget_minor_units"
            ),
        )

    payload.pop("objective_unit", None)
    objective_sense = payload.pop("objective_sense", None)
    if not _text(objective_sense):
        objective_sense = None
    return build_business_optimization_preview(
        workload_type=workload_type,
        solve=True,
        objective_sense=objective_sense,
        **payload,
    )


def _benchmark_if_safe(
    preview: Mapping[str, Any],
    *,
    max_variables: int,
) -> dict[str, Any] | None:
    plan = preview.get("plan")
    if not isinstance(plan, Mapping):
        return None
    if str(plan.get("status") or "").upper() != "AVAILABLE":
        return None
    try:
        variable_count = int(plan.get("variable_count") or 0)
    except (TypeError, ValueError):
        return None
    if variable_count <= 0 or variable_count > max_variables:
        return None
    return run_benchmark_arena(
        plan,
        exact_variable_limit=max_variables,
        include_market_references=False,
    )


def _refresh_solver_learning(
    root: Path,
    *,
    benchmark: Mapping[str, Any] | None,
    request_id: str,
    current: datetime,
    history_limit: int = 500,
) -> dict[str, Any] | None:
    if not isinstance(benchmark, Mapping):
        return None
    if str(benchmark.get("status") or "").upper() != "AVAILABLE":
        return None

    history_dir = root / BENCHMARK_HISTORY
    history_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = _text(benchmark.get("problem_fingerprint"))
    history_name = (
        current.strftime("%Y%m%dT%H%M%S%fZ")
        + "_"
        + _safe_id(request_id, "request")
        + "_"
        + (fingerprint[:12] or "no_fingerprint")
        + ".json"
    )
    _atomic_write(history_dir / history_name, benchmark)

    paths = sorted(
        (path for path in history_dir.glob("*.json") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )[-history_limit:]
    packets = [
        packet
        for packet in (_read_json(path) for path in paths)
        if packet is not None
    ]
    memory = build_solver_performance_memory(
        packets,
        minimum_observations=3,
    )
    _atomic_write(root / SOLVER_MEMORY_OUTPUT, memory)
    try:
        recommendation = recommend_benchmark_solver(
            memory=memory,
            arena_shape=benchmark,
        )
    except ValueError as exc:
        recommendation = {
            "schema_version": "empire.solver_performance_recommendation.v1",
            "status": "UNAVAILABLE",
            "reason": "solver_memory_shape_invalid",
            "detail": str(exc),
            "execution_authority": "none",
        }
    recommendation = {
        **recommendation,
        "history_observation_count": len(packets),
        "automatic_production_routing_changed": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
    _atomic_write(root / SOLVER_RECOMMENDATION_OUTPUT, recommendation)
    return {
        "history_ref": str((BENCHMARK_HISTORY / history_name)),
        "history_observation_count": len(packets),
        "memory_status": memory.get("status"),
        "profile_count": memory.get("profile_count"),
        "recommendation_status": recommendation.get("status"),
        "recommended_benchmark_solver": recommendation.get(
            "recommended_benchmark_solver"
        ),
        "automatic_production_routing_changed": False,
        "execution_authority": "none",
    }


def enqueue_optimization_request(
    repo_root: str | Path,
    request: Mapping[str, Any],
    *,
    event_ref: str,
    observed_at: str,
) -> dict[str, Any]:
    """Atomically enqueue one evidence-change event for optimization.

    Producers call this when canonical evidence changes. The queue event grants
    no business execution authority and carries no network/provider action.
    """
    root = Path(repo_root).resolve()
    ref = _text(event_ref)
    if not ref:
        raise ValueError("event_ref required")
    timestamp = _text(observed_at)
    if not timestamp:
        raise ValueError("observed_at required")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    workload_type = _text(request.get("workload_type"))
    if not workload_type:
        raise ValueError("workload_type required")
    if workload_type != "enterprise_portfolio_strategy":
        from empire_os.business_optimization_product import WORKLOAD_SPECS

        if workload_type not in WORKLOAD_SPECS:
            raise ValueError(f"unsupported workload_type:{workload_type}")

    packet = {
        **dict(request),
        "automation_event": {
            "event_ref": ref,
            "observed_at": parsed.isoformat(),
            "source": "empire_internal_evidence",
        },
    }
    fingerprint = _fingerprint(packet)
    request_id = _safe_id(
        request.get("request_id"),
        f"auto-{fingerprint[:24]}",
    )
    packet["request_id"] = request_id

    inbox = root / INBOX
    inbox.mkdir(parents=True, exist_ok=True)
    filename = (
        parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "_"
        + request_id
        + "_"
        + fingerprint[:12]
        + ".json"
    )
    destination = inbox / filename
    tenant_key = _safe_id(request.get("tenant_id"), "default")
    workload_key = _safe_id(workload_type, "unknown")
    state_path = (
        root / ENQUEUE_STATE / tenant_key / f"{workload_key}.json"
    )
    state = _read_json(state_path) or {}
    if state.get("event_fingerprint") == fingerprint:
        return {
            "schema_version": "empire.business_optimization_enqueue.v1",
            "status": "UNCHANGED",
            "request_id": request_id,
            "request_fingerprint": fingerprint,
            "queue_ref": state.get("queue_ref"),
            "enqueued": False,
            "execution_authority": "none",
        }

    _atomic_write(destination, packet)
    queue_ref = str(destination.relative_to(root))
    _atomic_write(
        state_path,
        {
            "schema_version": "empire.business_optimization_enqueue-state.v1",
            "status": "AVAILABLE",
            "tenant_id": _text(request.get("tenant_id")) or "default",
            "workload_type": workload_type,
            "event_ref": ref,
            "observed_at": parsed.isoformat(),
            "event_fingerprint": fingerprint,
            "request_id": request_id,
            "queue_ref": queue_ref,
            "execution_authority": "none",
        },
    )
    return {
        "schema_version": "empire.business_optimization_enqueue.v1",
        "status": "QUEUED",
        "request_id": request_id,
        "request_fingerprint": fingerprint,
        "workload_type": workload_type,
        "event_ref": ref,
        "observed_at": parsed.isoformat(),
        "queue_ref": queue_ref,
        "enqueued": True,
        "automatic_business_action_allowed": False,
        "third_party_service_called": False,
        "execution_authority": "none",
    }


def process_optimization_request(
    repo_root: str | Path,
    request: Mapping[str, Any],
    *,
    source_path: str | None = None,
    benchmark_variable_limit: int = 18,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Process one immutable recommendation request and persist its evidence."""
    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    workload_type = _text(request.get("workload_type"))
    tenant_id = _text(request.get("tenant_id")) or "default"
    request_id = _safe_id(
        request.get("request_id"),
        _fingerprint(dict(request))[:24],
    )
    request_fingerprint = _fingerprint(dict(request))

    previous = _previous_latest(
        root,
        tenant_id=tenant_id,
        workload_type=workload_type,
    )
    if (
        previous
        and previous.get("request_fingerprint") == request_fingerprint
        and previous.get("status") == "AVAILABLE"
    ):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNCHANGED",
            "request_id": request_id,
            "request_fingerprint": request_fingerprint,
            "tenant_id": tenant_id,
            "workload_type": workload_type,
            "previous_result_ref": previous.get("result_ref"),
            "decision_changed": False,
            "recomputed": False,
            "external_action_performed": False,
            "third_party_service_called": False,
            "execution_authority": "none",
        }

    try:
        preview = _build_preview(request)
    except (TypeError, ValueError) as exc:
        preview = {
            "status": "UNAVAILABLE",
            "reason": "request_compile_error",
            "detail": f"{type(exc).__name__}:{exc}",
            "execution_authority": "none",
        }

    benchmark = (
        _benchmark_if_safe(
            preview,
            max_variables=benchmark_variable_limit,
        )
        if str(preview.get("status") or "").upper() == "AVAILABLE"
        else None
    )
    solver_learning = _refresh_solver_learning(
        root,
        benchmark=benchmark,
        request_id=request_id,
        current=current,
    )
    signature = _recommendation_signature(preview)
    previous_signature = (
        dict(previous.get("recommendation_signature") or {})
        if previous
        else {}
    )
    decision_changed = (
        bool(previous)
        and signature != previous_signature
        and str(preview.get("status") or "").upper() == "AVAILABLE"
    )

    result_ref = (
        f"runtime/business_optimization/results/{request_id}.json"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": preview.get("status"),
        "request_id": request_id,
        "request_fingerprint": request_fingerprint,
        "tenant_id": tenant_id,
        "workload_type": workload_type,
        "generated_at": current.isoformat(),
        "source_path": source_path,
        "result_ref": result_ref,
        "preview": preview,
        "benchmark": benchmark,
        "solver_learning": solver_learning,
        "recommendation_signature": signature,
        "previous_recommendation_signature": previous_signature or None,
        "decision_changed": decision_changed,
        "recomputed": True,
        "recommendation_only": True,
        "automatic_business_action_allowed": False,
        "external_action_performed": False,
        "third_party_service_called": False,
        "network_required": False,
        "actual_revenue": False,
        "commercial_authority": "none",
        "financial_authority": "none",
        "payment_authority": "none",
        "execution_authority": "none",
    }

    _atomic_write(root / RESULTS / f"{request_id}.json", payload)
    tenant_key = _safe_id(tenant_id, "default")
    workload_key = _safe_id(workload_type, "unknown")
    _atomic_write(
        root / LATEST / tenant_key / f"{workload_key}.json",
        payload,
    )
    if decision_changed:
        change_ref = (
            current.strftime("%Y%m%dT%H%M%S%fZ")
            + "_"
            + request_id
            + ".json"
        )
        _atomic_write(
            root / CHANGES / tenant_key / workload_key / change_ref,
            {
                "schema_version": "empire.business_optimization_change.v1",
                "status": "AVAILABLE",
                "generated_at": current.isoformat(),
                "request_id": request_id,
                "tenant_id": tenant_id,
                "workload_type": workload_type,
                "previous_recommendation_signature": previous_signature,
                "recommendation_signature": signature,
                "result_ref": result_ref,
                "requires_downstream_review": True,
                "automatic_business_action_allowed": False,
                "execution_authority": "none",
            },
        )
    return payload


def run_business_optimization_cycle(
    repo_root: str | Path,
    *,
    max_requests: int = 24,
    benchmark_variable_limit: int = 18,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Process a bounded, crash-recoverable queue of optimization events."""
    if max_requests <= 0:
        raise ValueError("max_requests must be positive")

    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    inbox = root / INBOX
    processing = root / PROCESSING
    inbox.mkdir(parents=True, exist_ok=True)
    processing.mkdir(parents=True, exist_ok=True)

    recoverable = sorted(
        (path for path in processing.glob("*.json") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )
    claimed: list[Path] = recoverable[:max_requests]
    remaining_slots = max_requests - len(claimed)

    if remaining_slots > 0:
        inbox_paths = sorted(
            (path for path in inbox.glob("*.json") if path.is_file()),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
        )
        for path in inbox_paths:
            if remaining_slots <= 0:
                break
            moved = _claim_inbox_file(root, path)
            if moved is None:
                continue
            claimed.append(moved)
            remaining_slots -= 1

    recoverable_names = {path.name for path in recoverable}
    results: list[dict[str, Any]] = []
    invalid_files: list[str] = []
    archived_refs: list[str] = []
    recovered_count = sum(
        1 for path in claimed if path.name in recoverable_names
    )

    for path in claimed:
        request = _read_json(path)
        if request is None:
            invalid_files.append(path.name)
            archived = _archive_processing_file(
                root,
                path,
                current=current,
                invalid=True,
            )
            archived_refs.append(str(archived.relative_to(root)))
            continue

        result = process_optimization_request(
            root,
            request,
            source_path=str(path.relative_to(root)),
            benchmark_variable_limit=benchmark_variable_limit,
            now=current,
        )
        archived = _archive_processing_file(
            root,
            path,
            current=current,
            invalid=False,
        )
        archived_ref = str(archived.relative_to(root))
        archived_refs.append(archived_ref)
        results.append({
            **result,
            "archived_request_ref": archived_ref,
        })

    status_counts: dict[str, int] = {}
    changed_count = 0
    recomputed_count = 0
    unchanged_count = 0
    for result in results:
        status = _text(result.get("status")) or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1
        changed_count += int(result.get("decision_changed") is True)
        recomputed_count += int(result.get("recomputed") is True)
        unchanged_count += int(result.get("recomputed") is False)

    queued_remaining = sum(
        1 for path in inbox.glob("*.json") if path.is_file()
    )
    processing_remaining = sum(
        1 for path in processing.glob("*.json") if path.is_file()
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "inbox_path": str(INBOX),
        "processing_path": str(PROCESSING),
        "archive_path": str(ARCHIVE),
        "invalid_path": str(INVALID),
        "claimed_request_count": len(claimed),
        "recovered_processing_count": recovered_count,
        "processed_request_count": len(results),
        "recomputed_request_count": recomputed_count,
        "unchanged_request_count": unchanged_count,
        "decision_changed_count": changed_count,
        "invalid_request_file_count": len(invalid_files),
        "invalid_request_files": invalid_files,
        "archived_request_refs": archived_refs,
        "queued_request_count_remaining": queued_remaining,
        "processing_request_count_remaining": processing_remaining,
        "status_counts": status_counts,
        "results": [
            {
                "request_id": result.get("request_id"),
                "workload_type": result.get("workload_type"),
                "tenant_id": result.get("tenant_id"),
                "status": result.get("status"),
                "decision_changed": result.get("decision_changed"),
                "recomputed": result.get("recomputed"),
                "result_ref": result.get("result_ref"),
                "archived_request_ref": result.get("archived_request_ref"),
            }
            for result in results
        ],
        "automation_enabled": True,
        "queue_semantics": {
            "atomic_claim": True,
            "crash_recovery": True,
            "processed_events_archived": True,
            "invalid_events_quarantined": True,
            "idempotent_request_fingerprint": True,
        },
        "benchmarking": {
            "empire_owned_only": True,
            "market_references_included": False,
            "max_variables": benchmark_variable_limit,
        },
        "network_required": False,
        "third_party_service_called": False,
        "automatic_business_action_allowed": False,
        "external_action_performed": False,
        "commercial_authority": "none",
        "financial_authority": "none",
        "payment_authority": "none",
        "execution_authority": "none",
    }
    _atomic_write(root / CYCLE_OUTPUT, payload)
    return payload
