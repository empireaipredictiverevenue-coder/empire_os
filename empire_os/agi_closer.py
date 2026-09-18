"""
Legacy AGI Closer compatibility observer for EmpireOS.

The canonical closer is the Supabase-backed governed state machine.
This module may inspect legacy SQLite funnel state and produce recommendations,
but it has no authority to claim, settle, simulate replies, price deals, send
outreach, or mutate commercial state.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from empire_os.agent_core import Agent, OllamaClient
from empire_os.funnel import (
    SQLiteBackend, FunnelState,
    list_states, count_by_state, events_for,
)

logger = logging.getLogger("agi_closer")

CLOSER_SYSTEM_PROMPT = """You are the legacy EmpireOS closer observer.

You may classify what should be reviewed next, but you must not claim or settle
a prospect, invent deal values, simulate replies, send outreach, or mutate
commercial state. Canonical execution belongs to the governed Supabase closer
and outbound state machines.

Output recommendation JSON only."""


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
        """Recommend a review action without granting execution authority."""
        prompt = f"""Legacy closing pipeline observation:
- Outreach sent: {state['sent_count']}
- Replied: {state['replied_count']}
- Claimed (legacy state only): {state['claimed_count']}
- Settled (legacy state only): {state['settled_count']}

Observed prospects (up to 15):
{json.dumps(state['snapshots_preview'], indent=2)}

Choose one recommendation only:
1. "review_reply" — a genuine reply should enter the canonical closer flow
2. "prepare_follow_up" — follow-up copy could be prepared for governed outbound review
3. "review_terms" — a legacy claimed item needs canonical commercial review
4. "skip" — no action recommended

Do not invent prices, payments, conversions, replies, or settlements.
Output JSON: {{"action":"...","prospect_id":"...","reasoning":"..."}}"""

        return json.dumps(self.llm.structured_chat(
            messages=[{"role": "user", "content": prompt}],
            system=CLOSER_SYSTEM_PROMPT,
            temperature=0.2,
        ))

    def act(self, decision: str) -> dict:
        """Return a recommendation only; legacy mutation authority is retired."""
        try:
            parsed = json.loads(decision)
        except json.JSONDecodeError:
            parsed = {"action": "skip", "reasoning": "Parse failed"}

        requested_action = str(parsed.get("action") or "skip")
        prospect_id = str(parsed.get("prospect_id") or "")
        reasoning = str(parsed.get("reasoning") or "")

        return {
            "action": "recommendation_only",
            "requested_action": requested_action,
            "prospect_id": prospect_id,
            "reasoning": reasoning,
            "execution_allowed": False,
            "canonical_path": "supabase_closer_state_machine",
            "summary": (
                "Legacy closer execution retired; route observed evidence "
                "through the canonical governed closer/outbound flow."
            ),
        }
