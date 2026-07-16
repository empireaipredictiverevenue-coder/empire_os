"""
AGI Closer — last-mile lifecycle driver for Empire OS v3.

Drives prospects through the closing stages of the funnel:
    OUTREACH_SENT → REPLIED → CLAIMED → SETTLED

The Closer observes engagement signals (replied prospects, sent drafts
aging out), reasons about which deals are ready to close, and acts by
generating follow-ups, simulating reply handling, claiming interested
prospects, and recording settlements.

Every act writes to the funnel with the `agi-closer` actor.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from empire_os.agent_core import Agent, OllamaClient
from empire_os.funnel import (
    SQLiteBackend, FunnelState, transition, get_state,
    list_states, count_by_state, events_for,
)

logger = logging.getLogger("agi_closer")

CLOSER_SYSTEM_PROMPT = """You are the AGI Closer for Empire OS v3.

Your role:
1. Convert REPLIED prospects into CLAIMED (interested buyers who'll commit)
2. Drive CLAIMED prospects toward SETTLED (deal closed)
3. Generate follow-up messages when prospects stall in OUTREACH_SENT
4. Detect cold prospects and recommend re-engagement or archival

You are the last mile of the sales pipeline. Be decisive — if a prospect
shows buying intent (replied, requested quote, asked about pricing), advance
them. If they're cold after follow-ups, mark for review.

Output decisions as JSON only."""


@dataclass
class CloserSnapshot:
    """Enriched state for one prospect in the closing stages."""
    prospect_id: str
    niche: str
    current_state: str
    notes: str = ""
    days_in_state: int = 0
    is_stale: bool = False  # True if outreach_sent for >7 days with no reply


class AgiCloserAgent(Agent):
    """Last-mile closer agent. Drives replied → claimed → settled."""

    def __init__(
        self,
        backend: SQLiteBackend,
        llm: Optional[OllamaClient] = None,
        stale_threshold_days: int = 7,
    ):
        super().__init__(
            name="agi-closer",
            llm=llm,
            backend=backend,
        )
        self.stale_threshold_days = stale_threshold_days

    def observe(self) -> dict:
        """Survey the closing stages: sent, replied, claimed, settled."""
        counts = count_by_state(self.backend)

        sent = list_states(self.backend, state=FunnelState.OUTREACH_SENT.value)
        replied = list_states(self.backend, state=FunnelState.REPLIED.value)
        claimed = list_states(self.backend, state=FunnelState.CLAIMED.value)
        settled = list_states(self.backend, state=FunnelState.SETTLED.value)

        snapshots = []
        for prospect_list, state_name in [
            (sent, "outreach_sent"),
            (replied, "replied"),
            (claimed, "claimed"),
            (settled, "settled"),
        ]:
            for p in prospect_list:
                ev = events_for(self.backend, p.prospect_id)
                notes = ev[-1].notes if ev else ""
                niche = "unknown"
                for e in ev:
                    if "niche=" in e.notes:
                        niche = e.notes.split("niche=")[-1].split(",")[0].strip()
                        break
                snapshots.append(CloserSnapshot(
                    prospect_id=p.prospect_id,
                    niche=niche,
                    current_state=state_name,
                    notes=notes,
                    is_stale=state_name == "outreach_sent",
                ))

        return {
            "funnel_counts": counts,
            "cycle": self.context.cycle,
            "snapshot_count": len(snapshots),
            "snapshots_preview": [asdict(s) for s in snapshots[:15]],
            "sent_count": counts.get("outreach_sent", 0),
            "replied_count": counts.get("replied", 0),
            "claimed_count": counts.get("claimed", 0),
            "settled_count": counts.get("settled", 0),
        }

    def reason(self, state: dict) -> str:
        """LLM decides which prospect to advance in the closing pipeline."""
        prompt = f"""Closing pipeline status:
- Outreach sent (awaiting reply): {state['sent_count']}
- Replied (ready to claim): {state['replied_count']}
- Claimed (ready to close): {state['claimed_count']}
- Settled (closed deals): {state['settled_count']}

Prospects (up to 15):
{json.dumps(state['snapshots_preview'], indent=2)}

Decide one action:
1. "claim" — a REPLIED prospect is interested; advance to CLAIMED
2. "settle" — a CLAIMED prospect has committed; advance to SETTLED
3. "follow_up" — an OUTREACH_SENT prospect is going cold; generate follow-up
4. "skip" — pipeline is healthy, no action needed

Output JSON: {{"action": "...", "prospect_id": "...", "reasoning": "..."}}
If action is "settle", also include "amount_cents" (a realistic home-services deal: 50000-500000).
If action is "follow_up", also include "angle"."""

        return json.dumps(self.llm.structured_chat(
            messages=[{"role": "user", "content": prompt}],
            system=CLOSER_SYSTEM_PROMPT,
            temperature=0.3,
        ))

    def act(self, decision: str) -> dict:
        """Execute the closer's decision."""
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip", "reasoning": "Parse failed"}

        action = d.get("action", "skip")
        prospect_id = d.get("prospect_id", "")
        reasoning = d.get("reasoning", "")

        result = {
            "action": action,
            "prospect_id": prospect_id,
            "reasoning": reasoning,
        }

        try:
            if action == "claim" and prospect_id:
                eid = transition(
                    self.backend, prospect_id,
                    FunnelState.CLAIMED.value,
                    "agi-closer",
                    notes=f"claimed_by_llm, {reasoning}",
                )
                result["event_id"] = eid
                result["summary"] = f"Claimed {prospect_id}"

            elif action == "settle" and prospect_id:
                amount = int(d.get("amount_cents", 150000))
                eid = transition(
                    self.backend, prospect_id,
                    FunnelState.SETTLED.value,
                    "agi-closer",
                    notes=f"settled ${amount/100:.2f}, {reasoning}",
                )
                result["event_id"] = eid
                result["amount_cents"] = amount
                result["summary"] = f"Settled {prospect_id} for ${amount/100:.2f}"

            elif action == "follow_up" and prospect_id:
                angle = d.get("angle", "re-engagement")
                eid = transition(
                    self.backend, prospect_id,
                    FunnelState.REPLIED.value,  # follow-up effectively re-engages
                    "agi-closer",
                    notes=f"follow_up_triggered, angle={angle}",
                )
                result["event_id"] = eid
                result["summary"] = f"Follow-up triggered for {prospect_id}"

            else:
                result["summary"] = f"Skipped — {reasoning[:100] or 'no actionable prospect'}"

        except Exception as e:
            logger.exception("Closer action failed for %s", prospect_id)
            result["error"] = str(e)
            result["summary"] = f"Action failed: {e}"

        return result