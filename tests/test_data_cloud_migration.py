import pytest

from empire_os.data_cloud_contract import MigrationState
from empire_os.data_cloud_migration import MigrationPlan, VerificationManifest


def _verified():
    return VerificationManifest(
        schema_verified=True,
        row_counts_verified=True,
        content_integrity_verified=True,
        commercial_evidence_verified=True,
        payment_evidence_verified=True,
        backup_restore_verified=True,
        rollback_verified=True,
        tenant_isolation_verified=True,
    )


def test_cutover_ready_requires_all_verification():
    with pytest.raises(ValueError, match="complete verification"):
        MigrationPlan(
            current_state=MigrationState.DUAL_READ_COMPARE,
            target_state=MigrationState.CUTOVER_READY,
            verification=VerificationManifest(),
        ).validate()


def test_verified_plan_can_reach_cutover_ready():
    plan = MigrationPlan(
        current_state=MigrationState.DUAL_READ_COMPARE,
        target_state=MigrationState.CUTOVER_READY,
        verification=_verified(),
    )
    assert plan.as_dict()["target_state"] == "cutover_ready"


def test_founder_gate_cannot_be_skipped():
    with pytest.raises(ValueError, match="invalid migration transition"):
        MigrationPlan(
            current_state=MigrationState.CUTOVER_READY,
            target_state=MigrationState.FOUNDER_APPROVED_CUTOVER,
            verification=_verified(),
            founder_cutover_approved=False,
        ).validate()
