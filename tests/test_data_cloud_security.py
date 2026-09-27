import pytest

from empire_os.data_cloud_security import (
    Capability,
    ServiceIdentity,
    autonomous_capability_allowed,
    require_capability,
)


def test_missing_capability_is_denied():
    identity = ServiceIdentity("crawler", frozenset({Capability.DATA_READ}), "tenant-1")
    with pytest.raises(PermissionError, match="capability denied"):
        require_capability(identity, Capability.DATA_WRITE)


def test_schema_and_platform_admin_are_not_autonomous():
    assert autonomous_capability_allowed(Capability.MIGRATE_SCHEMA) is False
    assert autonomous_capability_allowed(Capability.PLATFORM_ADMIN) is False


def test_tenant_identity_cannot_hold_platform_admin():
    with pytest.raises(ValueError, match="cannot masquerade"):
        ServiceIdentity(
            "bad",
            frozenset({Capability.PLATFORM_ADMIN}),
            "tenant-1",
        ).validate()
