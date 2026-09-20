"""Standing-authority policy for the Empire GTM Agent.

The GTM Agent is an orchestrator over existing GTM/Omega/buyer/outbound modules.
It does not gain wildcard authority. Internal reversible work is automatic;
bounded external/commercial actions may use a standing authority grant; hard
founder gates remain explicit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class GTMAuthorityLane(str, Enum):
    AUTO = "AUTO"
    APPROVED_ACTION = "APPROVED_ACTION"
    STANDING_AUTHORITY = "STANDING_AUTHORITY"
    FOUNDER_GATE = "FOUNDER_GATE"


AUTO_ACTIONS = frozenset({
    "evidence.read",
    "acquisition.run",
    "enrichment.run",
    "identity.observe",
    "qualification.run",
    "omega.score",
    "buyer.discovery",
    "buyer.readiness.observe",
    "gtm.plan",
    "gtm.publish_internal_jobs",
    "content.draft",
    "outreach.prepare",
    "conversation.monitor",
    "commercial_terms.draft",
    "payment.monitor",
    "outcome.observe",
    "learning.run",
    "experiment.preview",
    "forecast.preview",
    "commercial_loop.observe",
})

STANDING_ACTIONS = frozenset({
    "outreach.approve",
    "outreach.send",
    "voice.call",
    "campaign.mutate",
    "buyer.activate",
    "inventory.allocate",
    "payment_request.issue",
    "fulfilment.execute",
})

FOUNDER_GATE_ACTIONS = frozenset({
    "commercial_terms.accept",
    "contract.accept",
    "payment.move",
    "revenue.recognize",
    "infrastructure.change",
    "model.promote",
    "authority.expand",
})


@dataclass(frozen=True)
class GTMStandingAuthority:
    authority_id: str
    approved_by: str
    approved_at: str
    expires_at: str
    capabilities: tuple[str, ...]
    channels: tuple[str, ...] = ()
    offer_keys: tuple[str, ...] = ()
    daily_external_action_cap: int = 0
    enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GTMActionReview:
    action: str
    lane: GTMAuthorityLane
    permitted: bool
    requires_founder_approval: bool
    standing_authority_used: bool
    authority_id: str | None
    blockers: tuple[str, ...]
    execution_performed: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lane"] = self.lane.value
        return data


def _parse_ts(value: str, *, label: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{label} required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def authority_lane(action: str) -> GTMAuthorityLane:
    key = str(action or "").strip()
    if key in AUTO_ACTIONS:
        return GTMAuthorityLane.AUTO
    if key in STANDING_ACTIONS:
        return GTMAuthorityLane.STANDING_AUTHORITY
    if key in FOUNDER_GATE_ACTIONS:
        return GTMAuthorityLane.FOUNDER_GATE
    return GTMAuthorityLane.FOUNDER_GATE


def review_gtm_action(
    action: str,
    *,
    now: datetime,
    standing_authority: GTMStandingAuthority | None = None,
    context: Mapping[str, Any] | None = None,
    external_actions_used_today: int = 0,
) -> GTMActionReview:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if external_actions_used_today < 0:
        raise ValueError("external_actions_used_today must be nonnegative")

    key = str(action or "").strip()
    lane = authority_lane(key)
    ctx = dict(context or {})

    if lane is GTMAuthorityLane.AUTO:
        return GTMActionReview(
            action=key,
            lane=lane,
            permitted=True,
            requires_founder_approval=False,
            standing_authority_used=False,
            authority_id=None,
            blockers=(),
        )

    if lane is GTMAuthorityLane.FOUNDER_GATE:
        return GTMActionReview(
            action=key,
            lane=lane,
            permitted=False,
            requires_founder_approval=True,
            standing_authority_used=False,
            authority_id=None,
            blockers=("founder_gate_required",),
        )

    authority_blockers: list[str] = []
    readiness_blockers: list[str] = []
    authority = standing_authority
    specific_approval = ctx.get("specific_approval_present") is True
    specific_approval_ref = str(
        ctx.get("specific_approval_ref") or ""
    ).strip()

    if specific_approval:
        if not specific_approval_ref:
            authority_blockers.append("specific_approval_ref_missing")
        result_lane = GTMAuthorityLane.APPROVED_ACTION
    else:
        result_lane = GTMAuthorityLane.STANDING_AUTHORITY
        if authority is None:
            authority_blockers.append("standing_authority_missing")
        else:
            if not authority.enabled:
                authority_blockers.append("standing_authority_disabled")
            if not str(authority.authority_id or "").strip():
                authority_blockers.append("authority_id_missing")
            if not str(authority.approved_by or "").strip():
                authority_blockers.append("approved_by_missing")

            current = now.astimezone(timezone.utc)
            approved_at = _parse_ts(
                authority.approved_at,
                label="approved_at",
            )
            expires_at = _parse_ts(
                authority.expires_at,
                label="expires_at",
            )
            if approved_at > current:
                authority_blockers.append(
                    "standing_authority_not_yet_active"
                )
            if expires_at <= current:
                authority_blockers.append(
                    "standing_authority_expired"
                )

            allowed = set(authority.capabilities)
            if key not in allowed:
                authority_blockers.append(
                    "capability_not_in_standing_authority"
                )

            cap = int(authority.daily_external_action_cap or 0)
            if cap <= 0:
                authority_blockers.append(
                    "external_action_cap_missing"
                )
            elif external_actions_used_today >= cap:
                authority_blockers.append(
                    "external_action_cap_reached"
                )

            channel = str(
                ctx.get("channel") or ""
            ).strip().lower()
            if channel:
                channels = {
                    str(value).strip().lower()
                    for value in authority.channels
                    if str(value).strip()
                }
                if channels and channel not in channels:
                    authority_blockers.append(
                        "channel_outside_standing_authority"
                    )

            offer_key = str(
                ctx.get("offer_key") or ""
            ).strip()
            if offer_key:
                offers = {
                    str(value).strip()
                    for value in authority.offer_keys
                    if str(value).strip()
                }
                if offers and offer_key not in offers:
                    authority_blockers.append(
                        "offer_outside_standing_authority"
                    )

    # Approval/authority never overrides readiness. Missing evidence,
    # compliance, or governor readiness is a system blocker, not a reason
    # to repeatedly ask the founder for approval.
    if ctx.get("evidence_ready") is not True:
        readiness_blockers.append("evidence_not_ready")
    if ctx.get("compliance_ready") is not True:
        readiness_blockers.append("compliance_not_ready")
    if ctx.get("governor_ready") is not True:
        readiness_blockers.append("governor_not_ready")

    blockers = tuple(
        dict.fromkeys(authority_blockers + readiness_blockers)
    )
    permitted = not blockers

    founder_authority_blockers = {
        "standing_authority_missing",
        "standing_authority_disabled",
        "standing_authority_expired",
        "authority_id_missing",
        "approved_by_missing",
        "specific_approval_ref_missing",
        "external_action_cap_missing",
        "capability_not_in_standing_authority",
        "channel_outside_standing_authority",
        "offer_outside_standing_authority",
    }
    requires_founder_approval = any(
        blocker in founder_authority_blockers
        for blocker in authority_blockers
    )

    authority_id = None
    if permitted and specific_approval:
        authority_id = specific_approval_ref
    elif permitted and authority is not None:
        authority_id = authority.authority_id

    return GTMActionReview(
        action=key,
        lane=result_lane,
        permitted=permitted,
        requires_founder_approval=requires_founder_approval,
        standing_authority_used=(
            permitted and not specific_approval
        ),
        authority_id=authority_id,
        blockers=blockers,
    )
