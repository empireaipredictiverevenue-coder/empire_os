"""OBSERVE-only health probe for real acquisition sources."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from empire_os.candidate_quality import assess_candidate


@dataclass(frozen=True)
class SourceHealthObservation:
    source: str
    metro: str
    observed_at: str
    endpoint_healthy: bool
    candidates_seen: int
    quality_accepted: int
    quality_rejected: int
    canonical_ingest_authorized: bool
    canonical_ingest_scheduled: bool
    end_to_end_healthy: bool
    blockers: tuple[str, ...]
    errors: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    canonical_writes: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)




def resolve_overpass_probe_metro(
    latest: dict[str, Any],
    success: dict[str, Any],
    valid_metros: set[str] | frozenset[str],
    default: str = "Austin, TX",
) -> str:
    """Choose a valid Overpass geography from acquisition runtime state."""
    candidates = (
        latest.get("overpass_metro_cursor"),
        latest.get("metro"),
        success.get("metro"),
        default,
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value in valid_metros:
            return value
    raise ValueError("no valid Overpass probe metro configured")

def observe_source_health(
    *,
    source: str,
    metro: str,
    runner: Callable[[str], Iterable[Any]],
    max_candidates: int = 5,
    canonical_ingest_authorized: bool = False,
    canonical_ingest_scheduled: bool = False,
    now: datetime | None = None,
) -> SourceHealthObservation:
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")

    seen = accepted = rejected = 0
    errors: list[str] = []
    try:
        for candidate in runner(metro):
            if seen >= max_candidates:
                break
            seen += 1
            quality = assess_candidate(candidate)
            if quality.accepted:
                accepted += 1
            else:
                rejected += 1
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {str(exc)[:300]}")


    endpoint_healthy = not errors and seen > 0 and accepted > 0
    blockers: list[str] = []
    if errors:
        blockers.append("source_probe_error")
    if seen == 0:
        blockers.append("no_source_candidates_observed")
    elif accepted == 0:
        blockers.append("no_quality_accepted_candidates")
    if not canonical_ingest_authorized:
        blockers.append("canonical_ingest_not_authorized")
    if not canonical_ingest_scheduled:
        blockers.append("canonical_ingest_not_scheduled")

    end_to_end = (
        endpoint_healthy
        and canonical_ingest_authorized
        and canonical_ingest_scheduled
    )
    return SourceHealthObservation(
        source=source,
        metro=metro,
        observed_at=current.astimezone(timezone.utc).isoformat(),
        endpoint_healthy=endpoint_healthy,
        candidates_seen=seen,
        quality_accepted=accepted,
        quality_rejected=rejected,
        canonical_ingest_authorized=canonical_ingest_authorized,
        canonical_ingest_scheduled=canonical_ingest_scheduled,
        end_to_end_healthy=end_to_end,
        blockers=tuple(sorted(set(blockers))),
        errors=tuple(errors),
    )


def atomic_write_observation(
    path: str | Path,
    observation: SourceHealthObservation,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(
        json.dumps(
            observation.as_dict(),
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    temp.replace(target)
