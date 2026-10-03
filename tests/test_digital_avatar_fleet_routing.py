import pytest

from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_fleet import AvatarFleetBinding
from empire_os.digital_avatar_fleet_routing import (
    AvatarFleetMeetingNeed,
    route_avatar_for_meeting,
)
from empire_os.saas_scale import TenantMembership


def membership(role="operator", **overrides):
    values = {
        "tenant_id": "tenant-a",
        "user_id": "user-1",
        "role": role,
        "status": "active",
    }
    values.update(overrides)
    return TenantMembership(**values)


def binding(
    avatar_id,
    capabilities,
    *,
    tenant_id="tenant-a",
    status="active",
):
    return AvatarFleetBinding(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        owner_ref=f"person:{avatar_id}",
        owner_name=f"Owner {avatar_id}",
        owner_consent_evidence_ref=f"consent:{avatar_id}:v1",
        capability_labels=tuple(capabilities),
        status=status,
    )
def need(
    *capabilities,
    preferred_avatar_id=None,
    tenant_id="tenant-a",
    mode=AvatarMeetingMode.COPILOT,
):
    return AvatarFleetMeetingNeed(
        tenant_id=tenant_id,
        meeting_id="meeting-001",
        required_capability_labels=tuple(capabilities),
        objective_evidence_ref="meeting-objective:001",
        requested_mode=mode,
        preferred_avatar_id=preferred_avatar_id,
    )


def test_unique_capability_match_selects_clone():
    result = route_avatar_for_meeting(
        membership=membership(),
        need=need("sales", "product"),
        bindings=(
            binding("avatar-sales", ("sales",)),
            binding("avatar-founder", ("sales", "product", "founder")),
        ),
    )
    assert result.selection_ready is True
    assert result.selected_avatar_id == "avatar-founder"
    assert result.eligible_avatar_ids == ("avatar-founder",)
    assert result.blockers == ()


def test_ambiguous_match_requires_human_selection():
    result = route_avatar_for_meeting(
        membership=membership(),
        need=need("sales"),
        bindings=(
            binding("avatar-b", ("sales",)),
            binding("avatar-a", ("sales", "product")),
        ),
    )
    assert result.selection_ready is False
    assert result.selected_avatar_id is None
    assert result.eligible_avatar_ids == ("avatar-a", "avatar-b")
    assert result.human_selection_required is True
    assert result.blockers == ("human_selection_required",)
def test_no_match_fails_closed():
    result = route_avatar_for_meeting(
        membership=membership(),
        need=need("technical"),
        bindings=(binding("avatar-sales", ("sales",)),),
    )
    assert result.selection_ready is False
    assert result.eligible_avatar_ids == ()
    assert result.blockers == ("no_eligible_avatar",)


def test_preferred_clone_is_selected_only_when_eligible():
    selected = route_avatar_for_meeting(
        membership=membership(),
        need=need("sales", preferred_avatar_id="avatar-b"),
        bindings=(
            binding("avatar-a", ("sales",)),
            binding("avatar-b", ("sales", "product")),
        ),
    )
    assert selected.selected_avatar_id == "avatar-b"
    assert selected.selection_ready is True

    blocked = route_avatar_for_meeting(
        membership=membership(),
        need=need("technical", preferred_avatar_id="avatar-b"),
        bindings=(binding("avatar-b", ("sales",)),),
    )
    assert blocked.selected_avatar_id is None
    assert blocked.blockers == ("preferred_avatar_unavailable",)


def test_preferred_cross_tenant_clone_is_indistinguishable_from_missing():
    bindings = (
        binding("avatar-local", ("sales",)),
        binding(
            "avatar-secret",
            ("sales",),
            tenant_id="tenant-b",
        ),
    )
    cross_tenant = route_avatar_for_meeting(
        membership=membership(),
        need=need("sales", preferred_avatar_id="avatar-secret"),
        bindings=bindings,
    )
    missing = route_avatar_for_meeting(
        membership=membership(),
        need=need("sales", preferred_avatar_id="avatar-missing"),
        bindings=bindings,
    )
    assert cross_tenant.selected_avatar_id is None
    assert missing.selected_avatar_id is None
    assert cross_tenant.blockers == missing.blockers
def test_disabled_clone_is_not_eligible():
    result = route_avatar_for_meeting(
        membership=membership(),
        need=need("sales"),
        bindings=(
            binding("avatar-disabled", ("sales",), status="disabled"),
        ),
    )
    assert result.blockers == ("no_eligible_avatar",)


def test_viewer_cannot_route_clone():
    with pytest.raises(
        PermissionError,
        match="membership_operate_permission_denied",
    ):
        route_avatar_for_meeting(
            membership=membership(role="viewer"),
            need=need("sales"),
            bindings=(binding("avatar-a", ("sales",)),),
        )


def test_membership_tenant_must_match_meeting_need():
    with pytest.raises(
        PermissionError,
        match="meeting_need_membership_tenant_mismatch",
    ):
        route_avatar_for_meeting(
            membership=membership(tenant_id="tenant-b"),
            need=need("sales", tenant_id="tenant-a"),
            bindings=(binding("avatar-a", ("sales",)),),
        )
@pytest.mark.parametrize(
    "mode",
    [
        AvatarMeetingMode.REPRESENT,
        AvatarMeetingMode.NEGOTIATE,
        AvatarMeetingMode.CLOSE,
    ],
)
def test_router_rejects_modes_above_copilot(mode):
    with pytest.raises(ValueError, match="authority ceiling"):
        route_avatar_for_meeting(
            membership=membership(),
            need=need("sales", mode=mode),
            bindings=(binding("avatar-a", ("sales",)),),
        )


def test_capabilities_are_case_normalized_deterministically():
    result = route_avatar_for_meeting(
        membership=membership(),
        need=need("SALES", "Product"),
        bindings=(
            binding("avatar-a", ("product", "sales")),
        ),
    )
    assert result.selection_ready is True
    assert result.required_capability_labels == ("product", "sales")


def test_routing_decision_never_grants_execution_authority():
    result = route_avatar_for_meeting(
        membership=membership(),
        need=need("sales"),
        bindings=(binding("avatar-a", ("sales",)),),
    )
    assert result.recommendation_only is True
    assert result.provider_call_performed is False
    assert result.meeting_join_performed is False
    assert result.speech_execution_allowed is False
    assert result.commercial_execution_allowed is False
    assert result.execution_authority == "none"
