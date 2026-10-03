import pytest

from empire_os.digital_avatar_fleet import AvatarFleetBinding
from empire_os.digital_avatar_fleet_read import (
    build_avatar_fleet_read_snapshot,
    get_avatar_fleet_read_item,
)
from empire_os.saas_scale import TenantMembership


def binding(
    avatar_id,
    *,
    tenant_id="tenant-a",
    owner_name="Owner",
    status="active",
    consent_ref="consent:verified:v1",
):
    return AvatarFleetBinding(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        owner_ref=f"person:{avatar_id}",
        owner_name=owner_name,
        owner_consent_evidence_ref=consent_ref,
        capability_labels=("sales", "product"),
        status=status,
    )


def membership(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "user_id": "user-1",
        "role": "viewer",
        "status": "active",
    }
    values.update(overrides)
    return TenantMembership(**values)
def test_snapshot_returns_only_own_tenant_and_redacts_consent_ref():
    snapshot = build_avatar_fleet_read_snapshot(
        membership=membership(),
        bindings=(
            binding("avatar-b", owner_name="B"),
            binding("avatar-other", tenant_id="tenant-b"),
            binding("avatar-a", owner_name="A"),
        ),
    )
    assert snapshot.tenant_id == "tenant-a"
    assert snapshot.avatar_count == 2
    assert [item.avatar_id for item in snapshot.avatars] == [
        "avatar-a",
        "avatar-b",
    ]
    assert snapshot.cross_tenant_metadata_included is False
    payload = snapshot.as_dict()
    serialized = repr(payload)
    assert "consent:verified:v1" not in serialized
    assert "tenant-b" not in serialized
    assert "avatar-other" not in serialized


def test_snapshot_exposes_status_but_zero_execution_authority():
    snapshot = build_avatar_fleet_read_snapshot(
        membership=membership(),
        bindings=(
            binding("avatar-active"),
            binding("avatar-disabled", status="disabled"),
        ),
    )
    assert [item.status for item in snapshot.avatars] == [
        "active",
        "disabled",
    ]
    for item in snapshot.avatars:
        assert item.consent_verified is True
        assert item.runtime_authority == "observe"
        assert item.execution_authority == "none"
        assert item.speech_execution_allowed is False
        assert item.commercial_execution_allowed is False
        assert item.payment_execution_allowed is False
        assert item.revenue_recognition_allowed is False
def test_disabled_membership_cannot_read_snapshot():
    with pytest.raises(
        PermissionError,
        match="membership_read_permission_denied",
    ):
        build_avatar_fleet_read_snapshot(
            membership=membership(status="disabled"),
            bindings=(binding("avatar-a"),),
        )


def test_cross_tenant_item_lookup_is_indistinguishable_from_missing():
    bindings = (
        binding("avatar-a"),
        binding("avatar-secret", tenant_id="tenant-b"),
    )
    own = get_avatar_fleet_read_item(
        membership=membership(),
        bindings=bindings,
        avatar_id="avatar-a",
    )
    other = get_avatar_fleet_read_item(
        membership=membership(),
        bindings=bindings,
        avatar_id="avatar-secret",
    )
    missing = get_avatar_fleet_read_item(
        membership=membership(),
        bindings=bindings,
        avatar_id="avatar-missing",
    )
    assert own is not None
    assert other is None
    assert missing is None


def test_invalid_avatar_id_is_rejected():
    with pytest.raises(ValueError, match="avatar_id required"):
        get_avatar_fleet_read_item(
            membership=membership(),
            bindings=(binding("avatar-a"),),
            avatar_id="",
        )
def test_conflicting_cross_tenant_avatar_binding_fails_before_projection():
    with pytest.raises(
        ValueError,
        match="avatar_id_cross_tenant_binding_conflict",
    ):
        build_avatar_fleet_read_snapshot(
            membership=membership(),
            bindings=(
                binding("avatar-shared", tenant_id="tenant-a"),
                binding("avatar-shared", tenant_id="tenant-b"),
            ),
        )


def test_snapshot_does_not_mutate_or_prepare_meeting_runtime():
    snapshot = build_avatar_fleet_read_snapshot(
        membership=membership(),
        bindings=(binding("avatar-a"),),
    )
    assert snapshot.execution_authority == "none"
    assert snapshot.mutation_allowed is False
    assert snapshot.meeting_execution_allowed is False
