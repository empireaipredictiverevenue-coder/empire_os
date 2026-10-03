"""Deterministic tenant-scoped capability routing for Digital Avatar fleets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_fleet import (
    AvatarFleetBinding,
    normalize_avatar_fleet_bindings,
)
from empire_os.saas_scale import TenantMembership


def _capability(value: str) -> str:
    return str(value or "").strip().lower()


@dataclass(frozen=True)
class AvatarFleetMeetingNeed:
    tenant_id: str
    meeting_id: str
    required_capability_labels: tuple[str, ...]
    objective_evidence_ref: str
    requested_mode: AvatarMeetingMode
    preferred_avatar_id: str | None = None

    def validate(self) -> None:
        if not self.tenant_id.strip() or not self.meeting_id.strip():
            raise ValueError("meeting need tenant_id and meeting_id required")
        if not self.objective_evidence_ref.strip():
            raise ValueError("meeting objective evidence ref required")
        required = tuple(
            _capability(value)
            for value in self.required_capability_labels
        )
        if not required or any(not value for value in required):
            raise ValueError("required capability labels required")
        if len(required) != len(set(required)):
            raise ValueError("required capability labels must be unique")
        if self.requested_mode not in {
            AvatarMeetingMode.SHADOW,
            AvatarMeetingMode.COPILOT,
        }:
            raise ValueError("meeting need mode exceeds V1 authority ceiling")
@dataclass(frozen=True)
class AvatarFleetRoutingDecision:
    tenant_id: str
    meeting_id: str
    requested_mode: str
    required_capability_labels: tuple[str, ...]
    selected_avatar_id: str | None
    eligible_avatar_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    human_selection_required: bool
    recommendation_only: bool = True
    provider_call_performed: bool = False
    meeting_join_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    execution_authority: str = "none"

    @property
    def selection_ready(self) -> bool:
        return self.selected_avatar_id is not None and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["selection_ready"] = self.selection_ready
        return value


def route_avatar_for_meeting(
    *,
    membership: TenantMembership,
    need: AvatarFleetMeetingNeed,
    bindings: Iterable[AvatarFleetBinding],
) -> AvatarFleetRoutingDecision:
    membership.validate()
    need.validate()
    if membership.tenant_id != need.tenant_id:
        raise PermissionError("meeting_need_membership_tenant_mismatch")
    if not membership.can("operate"):
        raise PermissionError("membership_operate_permission_denied")

    normalized = normalize_avatar_fleet_bindings(bindings)
    required = frozenset(
        _capability(value)
        for value in need.required_capability_labels
    )
    own_active = tuple(
        binding
        for binding in normalized
        if binding.tenant_id == membership.tenant_id
        and binding.status == "active"
    )
    eligible = tuple(
        sorted(
            (
                binding
                for binding in own_active
                if required.issubset(
                    frozenset(
                        _capability(value)
                        for value in binding.capability_labels
                    )
                )
            ),
            key=lambda value: value.avatar_id,
        )
    )
    eligible_ids = tuple(
        binding.avatar_id
        for binding in eligible
    )

    preferred = str(need.preferred_avatar_id or "").strip()
    if preferred:
        selected = next(
            (
                binding.avatar_id
                for binding in eligible
                if binding.avatar_id == preferred
            ),
            None,
        )
        blockers = () if selected else ("preferred_avatar_unavailable",)
        return AvatarFleetRoutingDecision(
            tenant_id=need.tenant_id,
            meeting_id=need.meeting_id,
            requested_mode=need.requested_mode.value,
            required_capability_labels=tuple(sorted(required)),
            selected_avatar_id=selected,
            eligible_avatar_ids=eligible_ids,
            blockers=blockers,
            human_selection_required=False,
        )
    if not eligible_ids:
        return AvatarFleetRoutingDecision(
            tenant_id=need.tenant_id,
            meeting_id=need.meeting_id,
            requested_mode=need.requested_mode.value,
            required_capability_labels=tuple(sorted(required)),
            selected_avatar_id=None,
            eligible_avatar_ids=(),
            blockers=("no_eligible_avatar",),
            human_selection_required=False,
        )

    if len(eligible_ids) > 1:
        return AvatarFleetRoutingDecision(
            tenant_id=need.tenant_id,
            meeting_id=need.meeting_id,
            requested_mode=need.requested_mode.value,
            required_capability_labels=tuple(sorted(required)),
            selected_avatar_id=None,
            eligible_avatar_ids=eligible_ids,
            blockers=("human_selection_required",),
            human_selection_required=True,
        )

    return AvatarFleetRoutingDecision(
        tenant_id=need.tenant_id,
        meeting_id=need.meeting_id,
        requested_mode=need.requested_mode.value,
        required_capability_labels=tuple(sorted(required)),
        selected_avatar_id=eligible_ids[0],
        eligible_avatar_ids=eligible_ids,
        blockers=(),
        human_selection_required=False,
    )
