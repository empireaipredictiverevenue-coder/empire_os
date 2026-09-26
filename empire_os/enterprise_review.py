"""Phase 17 enterprise control and SLO review aggregation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from empire_os.enterprise_controls import ControlEvidence, SloObservation


@dataclass(frozen=True)
class EnterpriseReadinessReview:
    control_passes: int
    control_failures: int
    control_unknowns: int
    slo_passes: int
    slo_failures: int
    slo_unknowns: int
    ready_for_enterprise_review: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_enterprise_readiness(
    *,
    controls: Iterable[ControlEvidence],
    slos: Iterable[SloObservation],
) -> EnterpriseReadinessReview:
    control_rows = list(controls)
    slo_rows = list(slos)

    for control in control_rows:
        control.validate()

    control_passes = sum(row.status == "pass" for row in control_rows)
    control_failures = sum(row.status == "fail" for row in control_rows)
    control_unknowns = sum(row.status == "unknown" for row in control_rows)

    slo_results = [row.meets_target for row in slo_rows]
    slo_passes = sum(result is True for result in slo_results)
    slo_failures = sum(result is False for result in slo_results)
    slo_unknowns = sum(result is None for result in slo_results)

    blockers: list[str] = []
    if not control_rows:
        blockers.append("no_control_evidence")
    if not slo_rows:
        blockers.append("no_slo_observations")
    if control_failures:
        blockers.append("control_failures_present")
    if control_unknowns:
        blockers.append("control_unknowns_present")
    if slo_failures:
        blockers.append("slo_failures_present")
    if slo_unknowns:
        blockers.append("slo_unknowns_present")

    return EnterpriseReadinessReview(
        control_passes=control_passes,
        control_failures=control_failures,
        control_unknowns=control_unknowns,
        slo_passes=slo_passes,
        slo_failures=slo_failures,
        slo_unknowns=slo_unknowns,
        ready_for_enterprise_review=not blockers,
        blockers=tuple(blockers),
    )
