"""Phase 17 evidence-only enterprise remediation triage."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_freshness import EnterpriseEvidenceReview


@dataclass(frozen=True)
class EnterpriseRemediationItem:
    kind: str
    key: str
    state: str
    family: str | None
    source: str
    evidence_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnterpriseRemediationReview:
    remediation_review_required: bool
    operator_queue_ready: bool
    items: tuple[EnterpriseRemediationItem, ...]
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    control_mutation: bool = False
    infrastructure_mutation: bool = False
    identity_mutation: bool = False
    backup_mutation: bool = False
    slo_target_mutation: bool = False
    compliance_mutation: bool = False
    deployment_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["items"] = [item.as_dict() for item in self.items]
        return data


def review_enterprise_remediation(
    *,
    controls: Iterable[ControlEvidence],
    slos: Iterable[SloObservation],
    freshness: EnterpriseEvidenceReview,
) -> EnterpriseRemediationReview:
    control_rows = list(controls)
    slo_rows = list(slos)
    if not control_rows:
        raise ValueError("control evidence required")
    if not slo_rows:
        raise ValueError("SLO observations required")

    items: list[EnterpriseRemediationItem] = []
    for row in control_rows:
        row.validate()
        if row.status in {"fail", "unknown"}:
            items.append(
                EnterpriseRemediationItem(
                    kind="control",
                    key=row.control_key,
                    state=row.status,
                    family=row.family,
                    source=row.source,
                    evidence_refs=row.evidence_refs,
                )
            )

    for row in slo_rows:
        state = row.meets_target
        if state is True:
            continue
        label = f"{row.service_key}:{row.metric}:{row.window}"
        items.append(
            EnterpriseRemediationItem(
                kind="slo",
                key=label,
                state="breach" if state is False else "unknown",
                family="reliability",
                source=row.source,
                evidence_refs=(),
            )
        )

    blockers = tuple(sorted(set(freshness.blockers)))
    return EnterpriseRemediationReview(
        remediation_review_required=bool(items),
        operator_queue_ready=bool(items) and freshness.fresh_for_review,
        items=tuple(items),
        blockers=blockers,
    )
