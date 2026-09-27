from empire_os.data_cloud_contract import (
    API_SURFACES,
    DataBackend,
    DataCloudAuthority,
    DataCloudContract,
    MigrationState,
    canonical_backend_for_state,
    external_api_enabled_by_default,
    migration_can_advance,
)


def test_external_surfaces_fail_closed_by_default():
    assert external_api_enabled_by_default() is False
    assert API_SURFACES
    assert all(surface.public_by_default is False for surface in API_SURFACES)


def test_authority_does_not_expand_consequential_actions():
    authority = DataCloudAuthority().as_dict()
    assert authority["internal_read"] is True
    assert authority["internal_write"] is True
    assert authority["schema_mutation"] is False
    assert authority["destructive_operation"] is False
    assert authority["cross_tenant_access"] is False
    assert authority["live_outbound"] is False
    assert authority["fund_movement"] is False
    assert authority["revenue_recognition"] is False
    assert authority["authority_expansion"] is False


def test_contract_requires_portable_resilient_foundation():
    contract = DataCloudContract().as_dict()
    assert contract["postgres_major"] == 18
    assert contract["tenant_aware"] is True
    assert contract["point_in_time_recovery_required"] is True
    assert contract["off_node_backup_required"] is True
    assert contract["private_database_network_required"] is True
    assert contract["vendor_neutral_application_boundary"] is True


def test_migration_advances_one_state_at_a_time():
    assert migration_can_advance(MigrationState.DISCOVER, MigrationState.SHADOW)
    assert not migration_can_advance(MigrationState.DISCOVER, MigrationState.VERIFY)


def test_cutover_requires_founder_approval():
    assert not migration_can_advance(
        MigrationState.CUTOVER_READY,
        MigrationState.FOUNDER_APPROVED_CUTOVER,
    )
    assert migration_can_advance(
        MigrationState.CUTOVER_READY,
        MigrationState.FOUNDER_APPROVED_CUTOVER,
        founder_cutover_approved=True,
    )


def test_empiredb_is_not_canonical_before_cutover():
    for state in (
        MigrationState.DISCOVER,
        MigrationState.SHADOW,
        MigrationState.COPY,
        MigrationState.VERIFY,
        MigrationState.DUAL_READ_COMPARE,
        MigrationState.CUTOVER_READY,
        MigrationState.FOUNDER_APPROVED_CUTOVER,
    ):
        assert canonical_backend_for_state(state) is DataBackend.SUPABASE_LEGACY


def test_empiredb_is_canonical_only_after_canonical_promotion():
    assert canonical_backend_for_state(
        MigrationState.EMPIREDB_CANONICAL
    ) is DataBackend.EMPIREDB
    assert canonical_backend_for_state(
        MigrationState.SUPABASE_RETIRED
    ) is DataBackend.EMPIREDB
