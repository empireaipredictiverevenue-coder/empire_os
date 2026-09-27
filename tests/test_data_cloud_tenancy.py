import pytest

from empire_os.data_cloud_tenancy import TenantContext, require_same_tenant


def test_cross_tenant_access_is_denied():
    with pytest.raises(PermissionError, match="cross-tenant"):
        require_same_tenant(
            TenantContext("tenant-a", "actor", "project-1"),
            TenantContext("tenant-b", "actor", "project-1"),
        )


def test_cross_project_access_is_denied_even_for_same_tenant():
    with pytest.raises(PermissionError, match="cross-tenant"):
        require_same_tenant(
            TenantContext("tenant-a", "actor", "project-1"),
            TenantContext("tenant-a", "actor", "project-2"),
        )
