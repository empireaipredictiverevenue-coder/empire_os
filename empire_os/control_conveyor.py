"""Canonical commercial conveyor projection for EmpireOS.

This module does not execute work. It converts canonical commercial-loop stage
evidence into a shared workflow state that every agent/UI can consume.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ConveyorStage:
    stage: str
    observed: bool | None
    owner_component: str
    authority: str
    next_event: str | None
    evidence: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("acquisition", "acquisition", "internal_write", "qualification_requested"),
    ("qualification", "qualification", "internal_write", "qualification_requested"),
    ("omega", "omega_readiness", "internal_write", "buyer_readiness_scored"),
    ("identity", "identity_enrichment", "internal_write", "identity_recovery_requested"),
    ("buyer_candidate", "buyer_review", "internal_write", "buyer_review_requested"),
    ("buyer_review", "buyer_review", "internal_write", "buyer_review_requested"),
    ("outbound", "outbound_governor", "governed_external", "outbound_intent_proposed"),
    ("reply", "conversation_os", "internal_write", "buyer_reply_received"),
    ("conversation", "conversation_os", "internal_write", "buyer_conversation_observed"),
    ("terms", "commercial_terms", "founder_gate", "terms_candidate_created"),
    ("verified_buyer_capacity", "buyer_capacity", "internal_write", "capacity_verified"),
    ("inventory_allocation", "fulfilment", "internal_write", "inventory_allocation_requested"),
    ("payment", "payment_governor", "founder_gate", "payment_review_requested"),
    ("fulfilment", "fulfilment", "governed_external", "fulfilment_review_requested"),
    ("commercial_outcome", "outcome_feedback", "internal_write", "commercial_outcome_recorded"),
    ("recognized_revenue", "revenue_recognition", "founder_gate", "revenue_review_requested"),
    ("revenue", "revenue_pulse", "observe", "revenue_pulse_refresh_requested"),
    ("gross_profit", "revenue_pulse", "observe", "revenue_pulse_refresh_requested"),
    ("gp", "revenue_pulse", "observe", "revenue_pulse_refresh_requested"),
)


def _stage_owner(stage: str) -> tuple[str, str, str | None]:
    normalized = str(stage or "").strip().lower()
    for token, component, authority, event in _RULES:
        if token in normalized:
            return component, authority, event
    return "control_fabric", "observe", None


def build_conveyor(loop: Mapping[str, Any]) -> dict[str, Any]:
    raw_stages = loop.get("stages") if isinstance(loop, Mapping) else []
    stages: list[ConveyorStage] = []
    for row in raw_stages or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("stage") or "").strip()
        if not name:
            continue
        observed_raw = row.get("observed")
        observed = (
            observed_raw if isinstance(observed_raw, bool) else None
        )
        component, authority, event = _stage_owner(name)
        stages.append(ConveyorStage(
            stage=name,
            observed=observed,
            owner_component=component,
            authority=authority,
            next_event=event,
            evidence={
                key: value
                for key, value in row.items()
                if key not in {"stage", "observed"}
            },
        ))

    blocker = next(
        (stage for stage in stages if stage.observed is False),
        None,
    )
    unknown = tuple(
        stage.stage for stage in stages if stage.observed is None
    )
    completed = tuple(
        stage.stage for stage in stages if stage.observed is True
    )

    return {
        "schema_version": "empire.control_conveyor.v1",
        "loop_complete": loop.get("loop_complete") is True,
        "current_blocker": blocker.stage if blocker else None,
        "owner_component": blocker.owner_component if blocker else None,
        "authority": blocker.authority if blocker else "none",
        "next_event": blocker.next_event if blocker else None,
        "completed_stages": list(completed),
        "unknown_stages": list(unknown),
        "stages": [stage.as_dict() for stage in stages],
        "execution_authority": "none",
        "controls_execution": False,
    }
