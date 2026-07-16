"""
AGI Sales — autonomous deal pipeline & outreach generation agent.

Drives prospects through the funnel: DISCOVERED → MATCHED → OUTREACH_DRAFTED
→ OUTREACH_SENT → REPLIED → CLAIMED → SETTLED.

The LLM generates personalised outreach drafts and decides which prospects
to advance each cycle based on urgency, fit, and pipeline balance.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from empire_os.agent_core import Agent, OllamaClient
from empire_os.funnel import (
    SQLiteBackend, FunnelState, transition, get_state,
    list_states, count_by_state, events_for,
)

logger = logging.getLogger("agi_sales")

SALES_SYSTEM_PROMPT = """You are the AGI Sales Strategist for Empire OS v3.

Your role:
1. Review discovered prospects and decide which to advance to MATCHED
2. Generate personalised outreach drafts for matched prospects
3. Prioritise prospects based on niche demand, lead quality, and pipeline balance

Focus on B2B outreach in home services: roofing, hvac, plumbing, solar, electrical.
Output decisions as JSON."""


@dataclass
class DealSnapshot:
    """A single deal/prospect in the pipeline with enrichment."""
    prospect_id: str
    niche: str
    current_state: str
    source: str = ""
    notes: str = ""
    days_in_state: int = 0
    priority: int = 3  # 1=hot, 2=warm, 3=cold


class AgiSalesAgent(Agent):
    """AGI-powered Sales agent that drives prospects through the funnel."""

    def __init__(
        self,
        backend: SQLiteBackend,
        llm: Optional[OllamaClient] = None,
        min_priority: int = 2,
        outreach_template: Optional[str] = None,
    ):
        super().__init__(
            name="agi-sales",
            llm=llm,
            backend=backend,
        )
        self.min_priority = min_priority
        self.outreach_template = outreach_template or (
            "Subject: {angle}\n\n"
            "Hi {prospect_id},\n\n"
            "{body}\n\n"
            "Best regards,\nEmpire OS"
        )

    def observe(self) -> dict:
        """Gather funnel state, deal snapshots, and pipeline balance."""
        counts = count_by_state(self.backend)
        discovered = list_states(self.backend, state=FunnelState.DISCOVERED.value)
        matched = list_states(self.backend, state=FunnelState.MATCHED.value)
        drafted = list_states(self.backend, state=FunnelState.OUTREACH_DRAFTED.value)
        sent = list_states(self.backend, state=FunnelState.OUTREACH_SENT.value)

        # Enrich with notes/niche info
        deals = []
        for prospect_list, state_name in [
            (discovered, "discovered"),
            (matched, "matched"),
            (drafted, "outreach_drafted"),
            (sent, "outreach_sent"),
        ]:
            for p in prospect_list:
                ev = events_for(self.backend, p.prospect_id)
                notes = ev[-1].notes if ev else ""
                niche = "unknown"
                for e in ev:
                    if "niche=" in e.notes:
                        niche = e.notes.split("niche=")[-1].split(",")[0].strip()
                        break
                deals.append(DealSnapshot(
                    prospect_id=p.prospect_id,
                    niche=niche,
                    current_state=state_name,
                    notes=notes,
                ))

        return {
            "funnel_counts": counts,
            "deal_count": len(deals),
            "deals_preview": [asdict(d) for d in deals[:15]],  # top 15
            "discovered_count": counts.get("discovered", 0),
            "matched_count": counts.get("matched", 0),
            "drafted_count": counts.get("outreach_drafted", 0),
            "sent_count": counts.get("outreach_sent", 0),
            "cycle": self.context.cycle,
        }

    def reason(self, state: dict) -> str:
        """LLM decides which prospects to advance and what content to generate."""
        prompt = f"""Pipeline status:
- Discovered (needs matching): {state['discovered_count']}
- Matched (needs draft): {state['matched_count']}
- Outreach drafted (needs send): {state['drafted_count']}
- Outreach sent (awaiting reply): {state['sent_count']}
- Total deals: {state['deal_count']}

Recent deals (up to 15):
{json.dumps(state['deals_preview'], indent=2)}

Decide what action to take:
1. "match" — advance a discovered prospect to matched (pick one)
2. "draft" — generate outreach content for a matched prospect
3. "advance" — mark an outreach_drafted prospect as outreach_sent
4. "skip" — wait, pipeline is balanced

Output JSON: {{"action": "...", "prospect_id": "...", "niche": "...", "angle": "...", "reasoning": "..."}}"""

        result = self.llm.structured_chat(
            messages=[{"role": "user", "content": prompt}],
            system=SALES_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return json.dumps(result)

    def act(self, decision: str) -> dict:
        """Execute the sales decision: match, draft, or advance."""
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip", "reasoning": "Parse failed"}

        action = d.get("action", "skip")
        prospect_id = d.get("prospect_id", "")
        niche = d.get("niche", "")
        angle = d.get("angle", "")
        reasoning = d.get("reasoning", "")

        result = {"action": action, "prospect_id": prospect_id,
                  "niche": niche, "reasoning": reasoning}

        try:
            if action == "match" and prospect_id:
                eid = transition(
                    self.backend, prospect_id,
                    FunnelState.MATCHED.value,
                    "agi-sales",
                    notes=f"niche={niche}, angle={angle}, matched_by_llm",
                )
                result["event_id"] = eid
                result["summary"] = f"Matched {prospect_id} → {niche}"

            elif action == "draft" and prospect_id:
                # Generate personalised outreach via LLM
                draft_content = self._generate_outreach(prospect_id, niche, angle)
                eid = transition(
                    self.backend, prospect_id,
                    FunnelState.OUTREACH_DRAFTED.value,
                    "agi-sales",
                    notes=f"draft: {draft_content[:100]}",
                )
                result["event_id"] = eid
                result["draft"] = draft_content
                result["summary"] = f"Drafted outreach for {prospect_id}"

            elif action == "advance" and prospect_id:
                eid = transition(
                    self.backend, prospect_id,
                    FunnelState.OUTREACH_SENT.value,
                    "agi-sales",
                    notes=f"outreach_sent, angle={angle}",
                )
                result["event_id"] = eid
                result["summary"] = f"Advanced {prospect_id} to outreach_sent"

            else:
                result["summary"] = f"Skipped — {reasoning[:100]}"

        except Exception as e:
            logger.exception("Sales action failed for %s", prospect_id)
            result["error"] = str(e)
            result["summary"] = f"Action failed: {e}"

        return result

    def _generate_outreach(self, prospect_id: str, niche: str, angle: str) -> str:
        """Generate a personalised outreach message via LLM."""
        prompt = f"""Write a brief, professional B2B outreach message for:
- Prospect: {prospect_id}
- Niche: {niche}
- Angle: {angle}

The message should be concise (3-4 sentences), personalised, and include
a clear call to action. Output just the message body, no subject line."""
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
