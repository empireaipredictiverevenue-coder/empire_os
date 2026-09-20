"""OBSERVE-only commercial loop blocker detection.

Modern recovery of the useful North Mini / loop-closure concept. The observer
never sends, allocates, charges, recognizes revenue, or fabricates missing
commercial evidence.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


STAGE_ORDER = (
    "real_acquisition",
    "qualification_v2",
    "omega_projection",
    "verified_buyer_capacity",
    "commercial_terms",
    "governed_outbound",
    "buyer_agreement",
    "bsc_usdt_payment",
    "fulfilment",
    "commercial_outcome",
    "recognized_revenue",
    "realized_gross_profit",
    "learning_feedback",
)


@dataclass(frozen=True)
class CommercialLoopObservation:
    stage: str
    observed: bool | None
    evidence_ref: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class CommercialLoopStatus:
    stages: tuple[CommercialLoopObservation, ...]
    highest_priority_blocker: str | None
    blocker_state: str | None
    loop_complete: bool
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    side_effects: str = "none"
    allocation_execution: bool = False
    outbound_execution: bool = False
    payment_execution: bool = False
    revenue_mutation: bool = False
    model_weight_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stages"] = [asdict(item) for item in self.stages]
        return data


def assess_commercial_loop(
    observations: dict[str, CommercialLoopObservation],
) -> CommercialLoopStatus:
    unknown_names = set(observations) - set(STAGE_ORDER)
    if unknown_names:
        raise ValueError(
            "unsupported commercial loop stage(s): "
            + ", ".join(sorted(unknown_names))
        )

    ordered: list[CommercialLoopObservation] = []
    blocker = None
    blocker_state = None
    for stage in STAGE_ORDER:
        item = observations.get(stage)
        if item is None:
            item = CommercialLoopObservation(
                stage=stage,
                observed=None,
                detail="stage evidence not loaded",
            )
        if item.stage != stage:
            raise ValueError(
                f"commercial loop observation stage mismatch: {stage}"
            )
        ordered.append(item)
        if blocker is None and item.observed is not True:
            blocker = stage
            blocker_state = (
                "blocked" if item.observed is False else "unknown"
            )

    return CommercialLoopStatus(
        stages=tuple(ordered),
        highest_priority_blocker=blocker,
        blocker_state=blocker_state,
        loop_complete=blocker is None,
    )


def observations_from_cycle(
    *,
    acquisition_accepted: int | None,
    qualification: dict[str, Any],
    omega: dict[str, Any],
    buyer_readiness: dict[str, Any],
) -> dict[str, CommercialLoopObservation]:
    qualified = int(qualification.get("qualified") or 0)
    scores = int(
        omega.get("scores_written")
        or omega.get("candidates_seen")
        or 0
    )
    ready = int(buyer_readiness.get("ready_count") or 0)

    return {
        "real_acquisition": CommercialLoopObservation(
            "real_acquisition",
            (
                None
                if acquisition_accepted is None
                else acquisition_accepted > 0
            ),
            evidence_ref="runtime:acquisition/latest.json",
            detail=(
                None
                if acquisition_accepted is None
                else f"{acquisition_accepted} real acquisition(s) accepted"
            ),
        ),
        "qualification_v2": CommercialLoopObservation(
            "qualification_v2",
            qualified > 0,
            evidence_ref="canonical:prospect_qualifications:v2",
            detail=f"{qualified} qualification(s) written in current cycle",
        ),
        "omega_projection": CommercialLoopObservation(
            "omega_projection",
            scores > 0,
            evidence_ref="canonical:intelligence_scores:omega_opportunity",
            detail=f"{scores} Omega candidate/score observation(s)",
        ),
        "verified_buyer_capacity": CommercialLoopObservation(
            "verified_buyer_capacity",
            ready > 0,
            evidence_ref="canonical:buyers:commercial_activation",
            detail=f"{ready} Omega prospect(s) with verified buyer capacity",
        ),
    }


def read_latest_acquisition_accepted(
    path: str | Path | None = None,
) -> int | None:
    source = Path(
        path
        or os.getenv(
            "EMPIRE_ACQUISITION_LATEST",
            "/srv/empire_os/runtime/acquisition/latest.json",
        )
    )
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    tail = str(raw.get("stdout_tail") or "")
    marker = '"accepted": '
    values: list[int] = []
    for segment in tail.split(marker)[1:]:
        digits = ""
        for char in segment:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            values.append(int(digits))
    if values:
        return values[-1]

    direct = raw.get("accepted")
    try:
        return int(direct) if direct is not None else None
    except (TypeError, ValueError):
        return None


def write_commercial_loop_snapshot(
    status: CommercialLoopStatus,
    path: str | Path | None = None,
) -> Path:
    target = Path(
        path
        or os.getenv(
            "EMPIRE_COMMERCIAL_LOOP_LATEST",
            "/srv/empire_os/runtime/commercial_loop/latest.json",
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(status.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    os.chmod(target, 0o600)
    return target
