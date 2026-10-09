"""Guard canonical-only refreshes from fabricating cycle-local evidence."""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.commercial_loop_observer import CommercialLoopObservation

CYCLE_LOCAL_STAGES = frozenset(("qualification_v2", "omega_projection"))


def preserve_cycle_local_observations(
    existing: Mapping[str, CommercialLoopObservation],
    canonical: Mapping[str, CommercialLoopObservation],
) -> dict[str, CommercialLoopObservation]:
    """Merge canonical evidence without converting absent local proof to success."""
    result = dict(existing)
    result.update(canonical)
    for stage in CYCLE_LOCAL_STAGES:
        previous = existing.get(stage)
        if previous is None or previous.observed is None:
            result[stage] = CommercialLoopObservation(
                stage=stage,
                observed=None,
                evidence_ref=None,
                detail="cycle-local evidence unavailable; qualification cycle required",
            )
        else:
            result[stage] = previous
    return result
