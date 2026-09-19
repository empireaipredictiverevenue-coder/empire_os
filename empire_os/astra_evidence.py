"""Strict evidence adapter for Astra operational snapshots."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping

from empire_os.astra import AstraSnapshot


DB_FIELDS = (
    "replies_waiting",
    "failed_jobs",
    "owned_inventory_count",
    "qualified_unallocated_count",
    "active_buyer_capacity",
    "buyer_candidates_due",
)

BINDING_FIELDS = (
    "premium_ai_budget_cents",
    "outbound_domain_verified",
    "source_health_ok",
)


@dataclass(frozen=True)
class AstraEvidenceResult:
    snapshot: AstraSnapshot | None
    missing: tuple[str, ...]
    observed: Mapping[str, Any]
    sources: Mapping[str, str]

    @property
    def available(self) -> bool:
        return self.snapshot is not None
def _as_nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{name} must be nonnegative")
    return parsed


def _as_bool(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{name} must be an explicit boolean")


def build_astra_evidence(
    *,
    actual_revenue_cents: int,
    operational_row: Mapping[str, Any] | None,
    bindings: Mapping[str, Any] | None,
) -> AstraEvidenceResult:
    row = dict(operational_row or {})
    policy = dict(bindings or {})
    missing = tuple(
        name
        for name in (*DB_FIELDS, *BINDING_FIELDS)
        if (name not in row if name in DB_FIELDS else name not in policy)
        or (row.get(name) if name in DB_FIELDS else policy.get(name)) is None
    )
    observed: dict[str, Any] = {
        "actual_revenue_cents": _as_nonnegative_int(
            "actual_revenue_cents",
            actual_revenue_cents,
        ),
    }
    sources = {
        "actual_revenue_cents": "commercial_outcome_calibration",
    }

    for name in DB_FIELDS:
        if name in row and row[name] is not None:
            observed[name] = _as_nonnegative_int(name, row[name])
            sources[name] = "canonical_operational_rpc"

    if "premium_ai_budget_cents" in policy and policy["premium_ai_budget_cents"] is not None:
        observed["premium_ai_budget_cents"] = _as_nonnegative_int(
            "premium_ai_budget_cents",
            policy["premium_ai_budget_cents"],
        )
        sources["premium_ai_budget_cents"] = "explicit_runtime_policy"

    for name in ("outbound_domain_verified", "source_health_ok"):
        if name in policy and policy[name] is not None:
            observed[name] = _as_bool(name, policy[name])
            sources[name] = "explicit_runtime_policy"

    if missing:
        return AstraEvidenceResult(
            snapshot=None,
            missing=missing,
            observed=observed,
            sources=sources,
        )

    snapshot = AstraSnapshot(
        execution_mode="observe",
        actual_revenue_cents=observed["actual_revenue_cents"],
        premium_ai_budget_cents=observed["premium_ai_budget_cents"],
        replies_waiting=observed["replies_waiting"],
        failed_jobs=observed["failed_jobs"],
        owned_inventory_count=observed["owned_inventory_count"],
        qualified_unallocated_count=observed["qualified_unallocated_count"],
        active_buyer_capacity=observed["active_buyer_capacity"],
        buyer_candidates_due=observed["buyer_candidates_due"],
        outbound_domain_verified=observed["outbound_domain_verified"],
        source_health_ok=observed["source_health_ok"],
    )
    return AstraEvidenceResult(
        snapshot=snapshot,
        missing=(),
        observed=observed,
        sources=sources,
    )


def astra_policy_bindings_from_env(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    bindings: dict[str, Any] = {}
    names = {
        "premium_ai_budget_cents": "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS",
        "outbound_domain_verified": "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED",
        "source_health_ok": "EMPIRE_ASTRA_SOURCE_HEALTH_OK",
    }
    for field, key in names.items():
        if key in env and str(env[key]).strip() != "":
            bindings[field] = env[key]
    return bindings
