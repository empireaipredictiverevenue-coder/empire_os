import pytest

from empire_os.data_cloud_contract import DataBackend, MigrationState
from empire_os.data_fabric import (
    DataOperation,
    DataRequestContext,
    DataRoutePlan,
    DataScope,
    route_for_migration_state,
    shadow_compare_allowed,
)


def test_tenant_scoped_requests_require_tenant_identity():
    with pytest.raises(ValueError, match="tenant_id"):
        DataRequestContext(
            actor_id="empire-test",
            operation=DataOperation.READ,
        )


def test_platform_scope_can_be_explicit_without_tenant():
    context = DataRequestContext(
        actor_id="empire-reliability-agent",
        operation=DataOperation.READ,
        scope=DataScope.PLATFORM,
    )
    assert context.tenant_id is None


def test_supabase_remains_primary_before_canonical_cutover():
    for state in (
        MigrationState.DISCOVER,
        MigrationState.SHADOW,
        MigrationState.COPY,
        MigrationState.VERIFY,
        MigrationState.DUAL_READ_COMPARE,
        MigrationState.CUTOVER_READY,
        MigrationState.FOUNDER_APPROVED_CUTOVER,
    ):
        plan = route_for_migration_state(state, DataOperation.WRITE)
        assert plan.primary is DataBackend.SUPABASE_LEGACY
        assert plan.dual_write is False
        assert plan.shadow_reads == ()


def test_dual_read_compare_shadows_empiredb_without_dual_write():
    context = DataRequestContext(
        actor_id="migration-verifier",
        tenant_id="tenant-1",
        operation=DataOperation.READ,
    )
    plan = route_for_migration_state(
        MigrationState.DUAL_READ_COMPARE,
        DataOperation.READ,
    )

    assert plan.primary is DataBackend.SUPABASE_LEGACY
    assert plan.shadow_reads == (DataBackend.EMPIREDB,)
    assert plan.dual_write is False
    assert shadow_compare_allowed(context, plan) is True


def test_write_never_shadow_routes_during_dual_read_compare():
    context = DataRequestContext(
        actor_id="migration-verifier",
        tenant_id="tenant-1",
        operation=DataOperation.WRITE,
    )
    plan = route_for_migration_state(
        MigrationState.DUAL_READ_COMPARE,
        DataOperation.WRITE,
    )

    assert plan.primary is DataBackend.SUPABASE_LEGACY
    assert plan.shadow_reads == ()
    assert plan.dual_write is False
    assert shadow_compare_allowed(context, plan) is False


def test_empiredb_routes_only_after_canonical_state():
    for state in (
        MigrationState.EMPIREDB_CANONICAL,
        MigrationState.SUPABASE_RETIRED,
    ):
        plan = route_for_migration_state(state, DataOperation.READ)
        assert plan == DataRoutePlan(primary=DataBackend.EMPIREDB)
