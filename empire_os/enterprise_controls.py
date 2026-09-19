"""Phase 17 Enterprise auditability and reliability foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CONTROL_FAMILIES = frozenset({
    "access_control",
    "data_isolation",
    "auditability",
    "security_monitoring",
    "backup_dr",
    "reliability",
    "compliance",
})


@dataclass(frozen=True)
class ControlEvidence:
    control_key: str
    family: str
    tenant_key: str | None
    status: str
    evidence_refs: tuple[str, ...]
    observed_at: str
    source: str

    def validate(self) -> None:
        if not self.control_key.strip():
            raise ValueError("control_key required")
        if self.family not in CONTROL_FAMILIES:
            raise ValueError("unsupported control family")
        if self.status not in {"pass", "fail", "unknown"}:
            raise ValueError("unsupported control status")
        if not self.evidence_refs:
            raise ValueError("control evidence requires evidence refs")
        if not self.observed_at.strip() or not self.source.strip():
            raise ValueError("control evidence provenance required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class SloObservation:
    service_key: str
    metric: str
    target: float
    observed: float | None
    window: str
    observed_at: str
    source: str

    @property
    def meets_target(self) -> bool | None:
        if self.observed is None:
            return None
        return self.observed >= self.target
