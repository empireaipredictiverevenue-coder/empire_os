from empire_os.saas_scale import TenantMembership
from empire_os.tenant_isolation import (
    TenantResourceRef,
    authorize_tenant_resource,
)


def resource(tenant_id="tenant-1"):
    return TenantResourceRef(
        tenant_id=tenant_id,
        resource_type="revenue_crm_prospect",
        resource_id="prospect-1",
    )


def test_same_tenant_read_is_allowed_for_viewer():
    decision = authorize_tenant_resource(
        membership=TenantMembership(
            tenant_id="tenant-1",
            user_id="user-1",
            role="viewer",
        ),
        resource=resource(),
        permission="read",
    )
    assert decision.allowed is True
    assert decision.reason == "tenant_membership_authorized"
    assert decision.cross_tenant is False
    assert decision.execution_authority == "none"


def test_cross_tenant_access_fails_closed():
    decision = authorize_tenant_resource(
        membership=TenantMembership(
            tenant_id="tenant-1",
            user_id="user-1",
            role="owner",
        ),
        resource=resource("tenant-2"),
        permission="read",
    )
    assert decision.allowed is False
    assert decision.reason == "cross_tenant_access_denied"
    assert decision.cross_tenant is True


def test_viewer_cannot_operate_even_same_tenant():
    decision = authorize_tenant_resource(
        membership=TenantMembership(
            tenant_id="tenant-1",
            user_id="user-1",
            role="viewer",
        ),
        resource=resource(),
        permission="operate",
    )
    assert decision.allowed is False
    assert decision.reason == "membership_permission_denied"


def test_disabled_membership_cannot_read():
    decision = authorize_tenant_resource(
        membership=TenantMembership(
            tenant_id="tenant-1",
            user_id="user-1",
            role="admin",
            status="disabled",
        ),
        resource=resource(),
        permission="read",
    )
    assert decision.allowed is False
