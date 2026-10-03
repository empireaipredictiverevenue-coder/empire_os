from hashlib import sha256
from pathlib import Path

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import (
    AvatarFleetBinding,
    AvatarFleetOperation,
    authorize_avatar_fleet_access,
    normalize_avatar_fleet_bindings,
    prepare_avatar_fleet_runtime,
)
from empire_os.saas_scale import TenantMembership


def identity(**overrides):
    values = {
        "avatar_id": "avatar-phil-v1",
        "owner_name": "Phil Livesley",
        "display_name": "Phil — Empire AI Digital Avatar",
        "organisation_name": "Empire AI",
        "disclosure_text": "I am Phil's authorised Empire AI Digital Avatar.",
        "owner_consent_evidence_ref": "consent:phil:avatar:v1",
        "voice_profile_ref": "voice:phil:v1",
        "visual_profile_ref": "visual:phil:v1",
    }
    values.update(overrides)
    return DigitalAvatarIdentity(**values)
def binding(**overrides):
    values = {
        "tenant_id": "tenant-empire",
        "avatar_id": "avatar-phil-v1",
        "owner_ref": "person:phil-livesley",
        "owner_name": "Phil Livesley",
        "owner_consent_evidence_ref": "consent:phil:avatar:v1",
        "capability_labels": ("founder", "sales", "product"),
        "status": "active",
    }
    values.update(overrides)
    return AvatarFleetBinding(**values)


def member(role="operator", **overrides):
    values = {
        "tenant_id": "tenant-empire",
        "user_id": "user-phil",
        "role": role,
        "status": "active",
    }
    values.update(overrides)
    return TenantMembership(**values)
def test_operator_can_prepare_only_tenant_bound_runtime():
    decision = authorize_avatar_fleet_access(
        membership=member(),
        binding=binding(),
        operation=AvatarFleetOperation.PREPARE_RUNTIME,
    )
    assert decision.allowed is True
    assert decision.cross_tenant is False
    assert decision.execution_authority == "none"
    assert decision.speech_execution_allowed is False
    assert decision.commercial_execution_allowed is False
    assert decision.payment_execution_allowed is False
    assert decision.revenue_recognition_allowed is False


def test_viewer_can_read_but_cannot_prepare_runtime():
    read = authorize_avatar_fleet_access(
        membership=member(role="viewer"),
        binding=binding(),
        operation=AvatarFleetOperation.READ,
    )
    operate = authorize_avatar_fleet_access(
        membership=member(role="viewer"),
        binding=binding(),
        operation=AvatarFleetOperation.PREPARE_RUNTIME,
    )
    assert read.allowed is True
    assert operate.allowed is False
    assert operate.reason == "membership_permission_denied"
def test_admin_can_manage_binding():
    decision = authorize_avatar_fleet_access(
        membership=member(role="admin"),
        binding=binding(),
        operation=AvatarFleetOperation.MANAGE_BINDING,
    )
    assert decision.allowed is True
    assert decision.execution_authority == "none"


def test_cross_tenant_access_is_denied():
    decision = authorize_avatar_fleet_access(
        membership=member(tenant_id="tenant-other"),
        binding=binding(),
        operation=AvatarFleetOperation.READ,
    )
    assert decision.allowed is False
    assert decision.cross_tenant is True
    assert decision.reason == "cross_tenant_access_denied"


def test_disabled_membership_or_binding_is_denied():
    disabled_member = authorize_avatar_fleet_access(
        membership=member(status="disabled"),
        binding=binding(),
        operation=AvatarFleetOperation.READ,
    )
    disabled_binding = authorize_avatar_fleet_access(
        membership=member(),
        binding=binding(status="disabled"),
        operation=AvatarFleetOperation.PREPARE_RUNTIME,
    )
    assert disabled_member.allowed is False
    assert disabled_member.reason == "membership_permission_denied"
    assert disabled_binding.allowed is False
    assert disabled_binding.reason == "avatar_binding_disabled"
@pytest.mark.parametrize(
    ("identity_value", "message"),
    [
        ({"avatar_id": "avatar-other"}, "avatar_identity_binding_mismatch"),
        ({"owner_name": "Other Owner"}, "avatar_owner_binding_mismatch"),
        (
            {"owner_consent_evidence_ref": "consent:other:v1"},
            "avatar_owner_consent_binding_mismatch",
        ),
    ],
)
def test_runtime_binding_rejects_identity_or_consent_mismatch(
    identity_value,
    message,
):
    with pytest.raises(PermissionError, match=message):
        prepare_avatar_fleet_runtime(
            membership=member(),
            binding=binding(),
            identity=identity(**identity_value),
        )


def test_runtime_binding_never_grants_execution_authority():
    runtime = prepare_avatar_fleet_runtime(
        membership=member(),
        binding=binding(),
        identity=identity(),
    )
    assert runtime.tenant_id == "tenant-empire"
    assert runtime.avatar_id == "avatar-phil-v1"
    assert runtime.runtime_authority == "observe"
    assert runtime.execution_authority == "none"
    assert runtime.speech_execution_allowed is False
    assert runtime.commercial_execution_allowed is False
    assert runtime.payment_execution_allowed is False
    assert runtime.revenue_recognition_allowed is False
def test_identical_binding_is_idempotently_deduplicated():
    value = binding()
    normalized = normalize_avatar_fleet_bindings((value, value))
    assert normalized == (value,)


def test_conflicting_same_tenant_binding_fails_closed():
    with pytest.raises(ValueError, match="avatar_binding_conflict"):
        normalize_avatar_fleet_bindings((
            binding(),
            binding(owner_ref="person:someone-else"),
        ))


def test_same_avatar_id_cannot_be_rebound_cross_tenant():
    with pytest.raises(
        ValueError,
        match="avatar_id_cross_tenant_binding_conflict",
    ):
        normalize_avatar_fleet_bindings((
            binding(),
            binding(tenant_id="tenant-other"),
        ))


def test_migration_018_remains_protected_and_unchanged():
    path = Path(
        "/srv/empire_os/migrations/empiredb/018_tenant_context_foundation.sql"
    )
    digest = sha256(path.read_bytes()).hexdigest()
    assert digest == (
        "e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21"
    )
