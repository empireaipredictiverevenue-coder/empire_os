"""OBSERVE-only readiness analysis for Empire's scalable data plane.

This module recommends infrastructure review from measured workload evidence.
It cannot deploy, provision, migrate, mutate schemas, or activate providers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ComponentReview:
    component: str
    state: str
    reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "reasons": list(self.reasons),
            "missing_evidence": list(self.missing_evidence),
        }


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    return int(number)


def _review(
    *,
    component: str,
    evidence: Mapping[str, Any],
    required: tuple[str, ...],
    triggers: tuple[tuple[str, str, float], ...],
) -> ComponentReview:
    missing = tuple(
        key for key in required
        if _number(evidence.get(key)) is None
    )
    reasons: list[str] = []

    for key, op, threshold in triggers:
        value = _number(evidence.get(key))
        if value is None:
            continue
        if op == ">=" and value >= threshold:
            reasons.append(f"{key}>={threshold:g}")
        elif op == ">" and value > threshold:
            reasons.append(f"{key}>{threshold:g}")

    if missing:
        state = "INSUFFICIENT_EVIDENCE"
    elif reasons:
        state = "REVIEW_RECOMMENDED"
    else:
        state = "CURRENT_STACK_SUFFICIENT"

    return ComponentReview(
        component=component,
        state=state,
        reasons=tuple(reasons),
        missing_evidence=missing,
    )


def assess_data_plane_readiness(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Review when heavier data infrastructure deserves operator evaluation.

    Thresholds are Empire internal review triggers, not vendor limits.
    Passing a trigger recommends architecture review only.
    """
    ev = dict(evidence or {})

    raw_vault = _review(
        component="durable_raw_object_storage",
        evidence=ev,
        required=("raw_gb_per_day", "raw_retention_days", "multimodal_objects_per_day"),
        triggers=(
            ("raw_gb_per_day", ">=", 5),
            ("raw_retention_days", ">=", 30),
            ("multimodal_objects_per_day", ">=", 1000),
        ),
    )

    event_backbone = _review(
        component="event_backbone_kafka_redpanda",
        evidence=ev,
        required=("event_backlog", "independent_consumers", "p95_ingest_lag_seconds"),
        triggers=(
            ("event_backlog", ">=", 10000),
            ("independent_consumers", ">=", 4),
            ("p95_ingest_lag_seconds", ">=", 60),
        ),
    )

    analytics = _review(
        component="analytical_engine_clickhouse",
        evidence=ev,
        required=("analytical_rows", "p95_analytical_query_seconds", "postgres_analytics_cpu_pct"),
        triggers=(
            ("analytical_rows", ">=", 100_000_000),
            ("p95_analytical_query_seconds", ">=", 5),
            ("postgres_analytics_cpu_pct", ">=", 60),
        ),
    )

    search = _review(
        component="dedicated_search_engine",
        evidence=ev,
        required=("search_documents", "p95_search_latency_ms", "search_qps"),
        triggers=(
            ("search_documents", ">=", 10_000_000),
            ("p95_search_latency_ms", ">=", 750),
            ("search_qps", ">=", 100),
        ),
    )

    graph = _review(
        component="dedicated_graph_engine",
        evidence=ev,
        required=("multi_hop_graph_queries_per_minute", "p95_graph_query_ms"),
        triggers=(
            ("multi_hop_graph_queries_per_minute", ">=", 1000),
            ("p95_graph_query_ms", ">=", 1500),
        ),
    )

    multi_region = _review(
        component="multi_region_data_plane",
        evidence=ev,
        required=("required_regions", "monthly_unavailability_minutes", "cross_region_users_pct"),
        triggers=(
            ("required_regions", ">=", 2),
            ("monthly_unavailability_minutes", ">=", 30),
            ("cross_region_users_pct", ">=", 35),
        ),
    )

    components = [
        raw_vault,
        event_backbone,
        analytics,
        search,
        graph,
        multi_region,
    ]

    review = [c.component for c in components if c.state == "REVIEW_RECOMMENDED"]
    unknown = [c.component for c in components if c.state == "INSUFFICIENT_EVIDENCE"]

    return {
        "schema_version": "data_plane_readiness.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "deployment_enabled": False,
        "provisioning_enabled": False,
        "schema_mutation": False,
        "credential_mutation": False,
        "migration_execution": False,
        "threshold_semantics": "empire_internal_review_triggers_not_vendor_limits",
        "components": [c.as_dict() for c in components],
        "review_recommended": review,
        "insufficient_evidence": unknown,
        "current_stack": {
            "canonical_operational_truth": "supabase_postgresql",
            "heavy_infrastructure_default": "disabled_until_measured_need",
        },
    }


def assess_data_contract_readiness(
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a proposed data contract without registering or persisting it."""
    required_text = (
        "namespace",
        "schema_name",
        "schema_version",
        "owner",
        "compatibility_mode",
        "privacy_class",
        "idempotency_semantics",
        "retention_class",
    )
    missing = [
        field for field in required_text
        if not str(contract.get(field) or "").strip()
    ]

    fields = contract.get("fields")
    if not isinstance(fields, list) or not fields:
        missing.append("fields")

    allowed_privacy = {
        "PUBLIC", "INTERNAL", "COMMERCIAL", "PII",
        "PAYMENT_EVIDENCE", "SECRET",
    }
    privacy = str(contract.get("privacy_class") or "").strip().upper()
    blockers: list[str] = []
    if privacy and privacy not in allowed_privacy:
        blockers.append("unsupported_privacy_class")

    time_semantics = contract.get("time_semantics")
    if not isinstance(time_semantics, Mapping):
        blockers.append("time_semantics_required")
    else:
        if not str(time_semantics.get("event_time_field") or "").strip():
            blockers.append("event_time_field_required")
        if not str(time_semantics.get("processing_time_field") or "").strip():
            blockers.append("processing_time_field_required")

    ready = not missing and not blockers
    return {
        "schema_version": "data_contract_readiness.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "registry_mutation": False,
        "ready_for_review": ready,
        "missing": list(dict.fromkeys(missing)),
        "blockers": blockers,
    }


def assess_replay_plan(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a bounded dry-run replay plan with zero mutation authority."""
    source_key = str(request.get("source_key") or "").strip()
    partition = str(request.get("partition") or "").strip()
    start_at = str(request.get("start_at") or "").strip()
    end_at = str(request.get("end_at") or "").strip()
    max_records = _integer(request.get("max_records"))

    blockers: list[str] = []
    if not source_key:
        blockers.append("source_key_required")
    if not partition:
        blockers.append("partition_required")
    if not start_at or not end_at:
        blockers.append("bounded_time_window_required")
    if max_records is None or max_records <= 0:
        blockers.append("positive_max_records_required")
    elif max_records > 100_000:
        blockers.append("max_records_exceeds_preview_limit")

    return {
        "schema_version": "data_replay_plan.v1",
        "mode": "DRY_RUN",
        "execution_authority": "none",
        "replay_execution": False,
        "production_write": False,
        "source_key": source_key or None,
        "partition": partition or None,
        "start_at": start_at or None,
        "end_at": end_at or None,
        "max_records": max_records,
        "idempotency_required": True,
        "checkpoint_required": True,
        "diff_before_apply_required": True,
        "ready_for_operator_review": not blockers,
        "blockers": blockers,
    }
