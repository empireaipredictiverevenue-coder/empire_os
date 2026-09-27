"""Backup, PITR and restore-verification contracts for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BackupPolicy:
    max_backup_age_seconds: int = 86400
    target_rpo_seconds: int = 300
    target_rto_seconds: int = 3600
    encryption_required: bool = True
    off_node_required: bool = True
    pitr_required: bool = True


@dataclass(frozen=True)
class RestoreEvidence:
    backup_age_seconds: float | None
    encrypted: bool
    off_node: bool
    wal_archiving_verified: bool
    wal_archive_lag_seconds: float | None
    pitr_restore_verified: bool
    full_restore_verified: bool
    restore_duration_seconds: float | None
    restored_integrity_verified: bool


def evaluate_restore_readiness(
    evidence: RestoreEvidence,
    *,
    policy: BackupPolicy = BackupPolicy(),
) -> dict[str, Any]:
    findings: list[str] = []

    if evidence.backup_age_seconds is None:
        findings.append("backup_age_unknown")
    elif evidence.backup_age_seconds > policy.max_backup_age_seconds:
        findings.append("backup_stale")

    if policy.encryption_required and not evidence.encrypted:
        findings.append("backup_unencrypted")
    if policy.off_node_required and not evidence.off_node:
        findings.append("backup_not_off_node")
    if policy.pitr_required and not evidence.wal_archiving_verified:
        findings.append("wal_archiving_unverified")
    if policy.pitr_required and not evidence.pitr_restore_verified:
        findings.append("pitr_restore_unverified")
    if policy.pitr_required:
        if evidence.wal_archive_lag_seconds is None:
            findings.append("wal_archive_lag_unknown")
        elif evidence.wal_archive_lag_seconds > policy.target_rpo_seconds:
            findings.append("wal_archive_lag_exceeds_rpo")
    if not evidence.full_restore_verified:
        findings.append("full_restore_unverified")
    if not evidence.restored_integrity_verified:
        findings.append("restored_integrity_unverified")
    if evidence.restore_duration_seconds is None:
        findings.append("restore_duration_unknown")
    elif evidence.restore_duration_seconds > policy.target_rto_seconds:
        findings.append("restore_exceeds_rto")

    return {
        "schema_version": "empire.data-cloud-restore-readiness.v1",
        "ready": not findings,
        "findings": findings,
        "policy": asdict(policy),
        "evidence": asdict(evidence),
        "authority": {
            "backup_delete": False,
            "production_restore": False,
            "production_cutover": False,
            "canonical_data_write": False,
        },
    }
