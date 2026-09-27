"""Fail-closed contracts for EmpireOS foundation infrastructure.

These interfaces let Empire adopt NATS, Temporal, OpenFGA and Unleash without
making any of them an implicit execution authority. Defaults are deliberately
inert: no event publication, workflow start, permission grant or feature enable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol


def _text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    event_id: str
    aggregate_ref: str
    payload: Mapping[str, Any]
    traceparent: str | None = None
    schema_version: str = "empire.event.v1"

    def validate(self) -> None:
        if not _text(self.event_type):
            raise ValueError("event_type required")
        if not _text(self.event_id):
            raise ValueError("event_id required")
        if not _text(self.aggregate_ref):
            raise ValueError("aggregate_ref required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


class EventBus(Protocol):
    def publish(self, event: EventEnvelope) -> dict[str, Any]:
        ...


class DisabledEventBus:
    def publish(self, event: EventEnvelope) -> dict[str, Any]:
        event.validate()
        return {
            "published": False,
            "reason": "event_bus_not_activated",
            "execution_authority": "none",
        }


@dataclass(frozen=True)
class WorkflowRequest:
    workflow_type: str
    workflow_id: str
    input_ref: str
    input_payload: Mapping[str, Any]

    def validate(self) -> None:
        if not _text(self.workflow_type):
            raise ValueError("workflow_type required")
        if not _text(self.workflow_id):
            raise ValueError("workflow_id required")
        if not _text(self.input_ref):
            raise ValueError("input_ref required")


class WorkflowEngine(Protocol):
    def start(self, request: WorkflowRequest) -> dict[str, Any]:
        ...


class DisabledWorkflowEngine:
    def start(self, request: WorkflowRequest) -> dict[str, Any]:
        request.validate()
        return {
            "started": False,
            "reason": "workflow_engine_not_activated",
            "execution_authority": "none",
        }


@dataclass(frozen=True)
class AuthorizationCheck:
    subject: str
    relation: str
    resource: str
    tenant_ref: str | None = None

    def validate(self) -> None:
        if not _text(self.subject):
            raise ValueError("authorization subject required")
        if not _text(self.relation):
            raise ValueError("authorization relation required")
        if not _text(self.resource):
            raise ValueError("authorization resource required")


class AuthorizationProvider(Protocol):
    def check(self, request: AuthorizationCheck) -> dict[str, Any]:
        ...


class DenyAllAuthorizationProvider:
    def check(self, request: AuthorizationCheck) -> dict[str, Any]:
        request.validate()
        return {
            "allowed": False,
            "reason": "authorization_provider_not_activated",
            "execution_authority": "none",
        }


@dataclass(frozen=True)
class FeatureFlagCheck:
    flag_key: str
    context: Mapping[str, Any]
    default: bool = False

    def validate(self) -> None:
        if not _text(self.flag_key):
            raise ValueError("feature flag key required")


class FeatureFlagProvider(Protocol):
    def is_enabled(self, request: FeatureFlagCheck) -> dict[str, Any]:
        ...


class DisabledFeatureFlagProvider:
    def is_enabled(self, request: FeatureFlagCheck) -> dict[str, Any]:
        request.validate()
        return {
            "enabled": bool(request.default and False),
            "reason": "feature_flag_provider_not_activated",
            "execution_authority": "none",
        }


def external_foundation_authority_contract() -> dict[str, Any]:
    return {
        "event_bus_can_grant_execution": False,
        "workflow_engine_can_grant_execution": False,
        "authorization_provider_can_move_funds": False,
        "feature_flags_can_bypass_revenue_truth": False,
        "feature_flags_can_bypass_outbound_approval": False,
        "feature_flags_can_bypass_payment_authority": False,
        "canonical_revenue_truth_remains_empire": True,
        "canonical_payment_authority_remains_empire": True,
    }
