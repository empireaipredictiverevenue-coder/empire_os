"""Fail-closed inbound number ownership contract and offline provider event mapping.

This module is not a webhook or signature verifier. Only a trusted server-side
adapter that has already authenticated a provider event may call this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from empire_os.inbound_revenue_recovery import RecoveryEvent


@dataclass(frozen=True)
class InboundNumberRoute:
    tenant_id: str
    e164_number: str
    business_name: str
    provider: str = "vonage"
    number_ownership_verified: bool = False
    inbound_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.business_name.strip():
            raise ValueError("tenant_and_business_required")
        if not re.fullmatch(r"\+[1-9][0-9]{6,14}", self.e164_number):
            raise ValueError("valid_e164_number_required")
        if self.provider != "vonage":
            raise ValueError("unsupported_provider")


class InboundNumberRegistry:
    def __init__(self, routes: list[InboundNumberRoute] | tuple[InboundNumberRoute, ...]):
        self._routes: dict[str, InboundNumberRoute] = {}
        for route in routes:
            if route.e164_number in self._routes:
                raise ValueError("duplicate_inbound_number_assignment")
            self._routes[route.e164_number] = route

    def resolve(self, did: str) -> InboundNumberRoute:
        route = self._routes.get(did)
        if route is None:
            raise ValueError("unregistered_inbound_number")
        if not route.number_ownership_verified or not route.inbound_enabled:
            raise ValueError("inbound_number_not_verified_and_enabled")
        return route


def map_inbound_provider_status(status: str) -> str | None:
    """Match canonical Voice Lab statuses without importing outbound execution."""
    return {
        "started": "ringing",
        "ringing": "ringing",
        "answered": "answered",
        "unanswered": "unanswered",
        "timeout": "unanswered",
        "busy": "busy",
        "rejected": "rejected",
        "cancelled": "rejected",
        "failed": "failed",
        "completed": "completed",
    }.get(str(status or "").strip().lower())


def build_trusted_inbound_status(
    payload: dict[str, Any],
    *,
    registry: InboundNumberRegistry,
    provider_signature_verified: bool = False,
) -> RecoveryEvent:
    """Convert a previously authenticated event; no verification is performed here.

    Requires a unique call id, actual DID and ISO timestamp. Synthetic stays
    false only after an upstream authenticated-source adapter explicitly
    verifies the webhook/signature. No tenant_id supplied in payload is trusted.
    """
    if provider_signature_verified is not True:
        raise ValueError("signed_provider_event_required")
    did = str(payload.get("to") or "").strip()
    route = registry.resolve(did)
    event_tenant = str(payload.get("tenant_id") or "").strip()
    if event_tenant and event_tenant != route.tenant_id:
        raise ValueError("provider_tenant_mismatch")
    if route.provider != "vonage":
        raise ValueError("unsupported_provider")
    kind = map_inbound_provider_status(str(payload.get("status") or ""))
    if not kind:
        raise ValueError("unsupported_inbound_provider_status")
    call_id = str(payload.get("uuid") or "").strip()
    event_id = str(payload.get("event_id") or "").strip()
    occurred_at = str(payload.get("timestamp") or "").strip()
    if not call_id or not event_id or not occurred_at:
        raise ValueError("provider_call_event_and_timestamp_required")
    return RecoveryEvent(
        tenant_id=route.tenant_id,
        event_id=event_id,
        call_id=call_id,
        occurred_at=occurred_at,
        kind=kind,
        origin="provider",
        synthetic=False,
        verified=True,
        evidence_ref=event_id,
    )
