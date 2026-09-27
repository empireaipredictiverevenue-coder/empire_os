from empire_os.data_cloud_backup_restore import (
    BackupPolicy,
    RestoreEvidence,
    evaluate_restore_readiness,
)


def _evidence(**overrides):
    values = {
        "backup_age_seconds": 60.0,
        "encrypted": True,
        "off_node": True,
        "wal_archiving_verified": True,
        "pitr_restore_verified": True,
        "full_restore_verified": True,
        "restore_duration_seconds": 600.0,
        "restored_integrity_verified": True,
    }
    values.update(overrides)
    return RestoreEvidence(**values)


def test_restore_readiness_requires_real_restore_proof():
    result = evaluate_restore_readiness(_evidence())
    assert result["ready"] is True
    assert result["findings"] == []


def test_missing_pitr_or_integrity_blocks_readiness():
    result = evaluate_restore_readiness(
        _evidence(
            pitr_restore_verified=False,
            restored_integrity_verified=False,
        )
    )
    assert result["ready"] is False
    assert "pitr_restore_unverified" in result["findings"]
    assert "restored_integrity_unverified" in result["findings"]


def test_restore_readiness_never_grants_production_authority():
    result = evaluate_restore_readiness(_evidence())
    assert result["authority"]["production_restore"] is False
    assert result["authority"]["production_cutover"] is False
    assert result["authority"]["backup_delete"] is False


def test_restore_must_meet_rto():
    result = evaluate_restore_readiness(
        _evidence(restore_duration_seconds=7200.0),
        policy=BackupPolicy(target_rto_seconds=3600),
    )
    assert result["ready"] is False
    assert "restore_exceeds_rto" in result["findings"]
