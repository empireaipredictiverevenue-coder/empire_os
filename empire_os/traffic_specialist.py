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


def review_organic_traffic(opportunities, search_intelligence):
    """Review validated Distribution evidence without invoking funnel writes.

    ZERO-CASH describes the proposed media channel, not the total action cost.
    No acquisition budget is needed to propose an evidence investigation.
    """
    actions = []

    def propose(kind, refs, opportunity=None):
        if not refs:
            return
        opportunity = opportunity or {}
        actions.append({
            "action_type": kind,
            "channel": "organic_search",
            "opportunity_key": opportunity.get("opportunity_key"),
            "evidence_refs": list(refs),
            "classification": "PROPOSAL",
            "proposal_only": True,
            "zero_cash_mode": True,
            "paid_media_spend_cents": 0,
            "total_action_cost_cents": None,
            "execution_authority": "none",
            "missing_evidence": sorted(set([
                "total_action_cost", "verified_search_gap",
                *opportunity.get("missing_evidence", []),
            ])),
            "canonical_prediction": opportunity.get("canonical_prediction"),
            "expected_canonical_revenue_contribution_cents": opportunity.get(
                "expected_canonical_revenue_contribution_cents"
            ),
        })

    for opportunity in opportunities:
        propose("review_opportunity_organic_evidence", opportunity["evidence_refs"], opportunity)
    for name, kind in (
        ("search", "review_organic_search_evidence"),
        ("aeo", "review_aeo_evidence"),
        ("competitor", "review_competitor_visibility"),
    ):
        source = search_intelligence.get(name, {})
        if source.get("status") == "available":
            propose(kind, source.get("evidence_refs", []))
    return {"actions": actions, "action_count": len(actions), "execution_authority": "none"}


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
    # Discovery is not consent. Preserve provenance without asserting opt-in.
    backend.execute(
        """INSERT OR REPLACE INTO si_prospect_consent
           (prospect_id, opted_in, opted_in_at, niche, source)
           VALUES (?, 0, NULL, ?, ?)""",
        (prospect.prospect_id, prospect.niche, prospect.source),
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
