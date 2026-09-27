"""Empire Data Cloud migration readiness contracts.

No database connections, data copy, schema mutation or cutover are performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.data_cloud_contract import MigrationState, migration_can_advance


@dataclass(frozen=True)
class VerificationManifest:
    schema_verified: bool = False
    row_counts_verified: bool = False
    content_integrity_verified: bool = False
    commercial_evidence_verified: bool = False
    payment_evidence_verified: bool = False
    backup_restore_verified: bool = False
    rollback_verified: bool = False
    tenant_isolation_verified: bool = False

    @property
    def cutover_ready(self) -> bool:
        return all(asdict(self).values())

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class MigrationPlan:
    current_state: MigrationState
    target_state: MigrationState
    verification: VerificationManifest
    founder_cutover_approved: bool = False

    def validate(self) -> None:
        if not migration_can_advance(
            self.current_state,
            self.target_state,
            founder_cutover_approved=self.founder_cutover_approved,
        ):
            raise ValueError("invalid migration transition")
        if self.target_state is MigrationState.CUTOVER_READY and not self.verification.cutover_ready:
            raise ValueError("cutover readiness requires complete verification")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "current_state": self.current_state.value,
            "target_state": self.target_state.value,
            "verification": self.verification.as_dict(),
            "founder_cutover_approved": self.founder_cutover_approved,
        }


def classify_dependencies(
    findings: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    counts = {
        "requires_review": 0,
        "adapter_candidate": 0,
        "migration_only": 0,
        "retire_after_cutover": 0,
    }
    for finding in findings:
        classification = str(finding.get("classification") or "requires_review")
        if classification not in counts:
            classification = "requires_review"
        counts[classification] += 1
    return counts
