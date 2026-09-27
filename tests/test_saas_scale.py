import pytest

from empire_os.saas_scale import TenantMembership, UsageObservation


def test_owner_has_admin_and_member_management():
    membership = TenantMembership(
        tenant_id="tenant-1",
        user_id="user-1",
        role="owner",
    )
    assert membership.can("read") is True
    assert membership.can("admin") is True
    assert membership.can("manage_members") is True


def test_viewer_cannot_operate():
    membership = TenantMembership(
        tenant_id="tenant-1",
        user_id="user-2",
        role="viewer",
    )
    assert membership.can("read") is True
    assert membership.can("operate") is False


def test_disabled_membership_has_no_permissions():
    membership = TenantMembership(
        tenant_id="tenant-1",
        user_id="user-2",
        role="admin",
        status="disabled",
    )
    assert membership.can("read") is False
    assert membership.can("admin") is False


def test_usage_observation_requires_nonnegative_value():
    with pytest.raises(ValueError, match="nonnegative"):
        UsageObservation(
            tenant_id="tenant-1",
            metric="predictions",
            value=-1,
            period="2026-09",
            source="canonical_usage_meter",
        ).validate()


def test_usage_observation_requires_provenance():
    with pytest.raises(ValueError, match="period and source"):
        UsageObservation(
            tenant_id="tenant-1",
            metric="predictions",
            value=1,
            period="",
            source="",
        ).validate()
