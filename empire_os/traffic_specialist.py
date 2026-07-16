"""
Traffic Specialist — drives discovered → matched in the funnel.

This persona operates on the si_prospect_consent table (opt-in consent)
and the funnel. It is responsible for advancing prospects from
DISCOVERED to MATCHED when the engine produces a qualifying hit.

The traffic specialist never initiates an outbound action against
a prospect — it only operates on the funnel and consent table.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from empire_os.funnel import (
    SQLiteBackend,
    FunnelState,
    FunnelStateRow,
    transition,
    get_state,
    list_states,
)

logger = logging.getLogger("traffic_specialist")


@dataclass
class DiscoveredProspect:
    """A prospect that was discovered by the Neural Scout or another source."""
    prospect_id: str
    niche: str
    source: str
    discovered_at: str
    name: str = ""
    phone: str = ""
    zip_code: str = ""
    details: str = ""


def discover_one(
    backend: SQLiteBackend,
    prospect: DiscoveredProspect,
    actor: str = "traffic-specialist",
) -> int:
    """Manually register a single discovered prospect in the funnel.

    This is the programmatic way to seed a discovery. The Neural Scout
    typically handles this automatically, but this is the low-level API
    for direct use.
    """
    # Upsert consent
    backend.execute(
        """INSERT OR REPLACE INTO si_prospect_consent
           (prospect_id, opted_in, opted_in_at, niche, source)
           VALUES (?, 1, ?, ?, ?)""",
        (prospect.prospect_id, prospect.discovered_at, prospect.niche, prospect.source),
    )

    eid = transition(
        backend,
        prospect_id=prospect.prospect_id,
        to_state=FunnelState.DISCOVERED,
        actor=actor,
        notes=(
            f"niche={prospect.niche} source={prospect.source} "
            f"zip={prospect.zip_code}"
        ),
    )
    logger.info("Discovered prospect %s (niche=%s)", prospect.prospect_id, prospect.niche)
    return eid


def mark_matched(
    backend: SQLiteBackend,
    prospect_id: str,
    actor: str = "traffic-specialist",
    notes: str = "",
) -> int:
    """Advance a prospect from discovered to matched.

    The engine should call this when it produces a qualifying hit
    (e.g., lead score exceeds threshold, or a manual review passes).
    """
    state = get_state(backend, prospect_id)
    if state is None:
        raise ValueError(f"Prospect '{prospect_id}' not found in funnel — discover first")

    if state.current_state != FunnelState.DISCOVERED.value:
        raise ValueError(
            f"Prospect '{prospect_id}' is at '{state.current_state}', "
            f"not 'discovered'. Cannot mark as matched."
        )

    eid = transition(
        backend,
        prospect_id=prospect_id,
        to_state=FunnelState.MATCHED,
        actor=actor,
        notes=notes or "engine hit",
    )
    logger.info("Matched prospect %s (event %d)", prospect_id, eid)
    return eid


def pipeline_status(backend: SQLiteBackend) -> dict:
    """Return a summary of the current pipeline state.

    Returns:
        {"by_state": {"discovered": N, "matched": N, ...}, "total": N}
    """
    from empire_os.funnel import count_by_state
    counts = count_by_state(backend)
    return {
        "by_state": counts,
        "total": sum(counts.values()),
    }


def tick(
    backend: SQLiteBackend,
    discovered: Optional[list[DiscoveredProspect]] = None,
    matched: Optional[list[str]] = None,
) -> dict:
    """Run the traffic specialist tick.

    Args:
        discovered: New prospects to register as discovered.
        matched: List of prospect_ids that the engine matched.

    Returns:
        Summary dict with counts.
    """
    results = {"discovered": 0, "matched": 0}

    if discovered:
        for p in discovered:
            discover_one(backend, p)
            results["discovered"] += 1

    if matched:
        for pid in matched:
            try:
                mark_matched(backend, pid)
                results["matched"] += 1
            except (ValueError, Exception) as e:
                logger.warning("Failed to mark %s as matched: %s", pid, e)

    return results
