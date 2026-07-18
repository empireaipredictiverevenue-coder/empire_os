"""
Lead Handler Agent — cross-niche routing for discovered prospects.

Why this exists:
  agi-scout discovers leads with a single `source` label. Real leads
  often fit multiple niches (a "Dallas roofing contractor" might also
  do gutters, solar, storm-damage repair). If the lead was tagged
  `roofing` but actually scores higher on `solar`, the original
  routing wastes the lead.

  This agent:
    1. Reads discovered prospects from si_funnel_event
    2. Scores each against ALL niches via synthetic_intelligence
    3. Routes strong-fit leads to outreach (via hub /v1/outbox)
    4. Re-routes weak-fit leads to a better-matching niche
    5. Parks leads that fit nothing (with reasoning logged)

Agentic loop, no scripts. Cycle: 5 min. SOUL at souls/lead_handler_SOUL.md.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.synthetic_intelligence import (
    analyze_lead, NICHE_KEYWORDS,
)

ROLE_DIR = Path("/root/lead_handler")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
ROUTED_LOG = ROLE_DIR / "routed.jsonl"
TICK_INTERVAL = 300  # 5 min

DB_PATH = os.environ.get("DB_PATH", "/root/empire_os/empire_os.db")
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100")


class LeadHandlerAgent(SyntheticAgent):
    """Reads discovered leads, routes them to the best-fit niche."""

    def _db_query(self, sql: str, params: tuple = ()) -> list[dict]:
        try:
            cnx = sqlite3.connect(DB_PATH)
            cnx.row_factory = sqlite3.Row
            rows = [dict(r) for r in cnx.execute(sql, params).fetchall()]
            cnx.close()
            return rows
        except Exception as e:
            return [{"_error": str(e)[:200]}]

    def _post_outreach(self, lead: dict, niche: str) -> dict:
        """Queue a lead into hub /v1/outbox for the matched niche."""
        try:
            import requests
            subject = (f"Empire OS for {lead.get('metro', 'your area')} "
                       f"{niche}: real leads, USDC billing")
            body = (f"Hey {lead.get('name', 'there')},\n\n"
                    f"this is the Empire OS team reaching out about your "
                    f"{niche} project in {lead.get('metro', '?')}. "
                    f"We deliver exclusive leads to high-revenue agencies "
                    f"across 462 lanes. All billing is in USDC on Solana.\n\n"
                    f"The Silver tier is the best fit. Want a free 1-day "
                    f"trial of the pipeline?\n\nFirst 14 days free. "
                    f"Cancel anytime.\n\n---\nEmpire OS\n"
                    f"Unsubscribe: https://empire-ai.co.uk/unsub/{niche}-"
                    f"{lead.get('metro', 'x').lower().replace(' ', '-')}")
            r = requests.post(
                f"{HUB_URL}/v1/outbox/enqueue",
                json={"to": lead.get("email") or "founder@empire-ai.co.uk",
                      "subject": subject, "body": body,
                      "niche": niche, "source": "lead-handler"},
                timeout=8)
            return {"ok": r.status_code in (200, 201),
                    "status": r.status_code,
                    "body": r.text[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def observe(self) -> dict:
        # Pull recent discovered prospects from si_funnel_event
        events = self._db_query(
            "SELECT id, prospect_id, actor, notes, occurred_at "
            "FROM si_funnel_event "
            "WHERE to_state = 'discovered' "
            "ORDER BY id DESC LIMIT 100")
        # Parse each notes blob into a lead dict
        leads = []
        for e in events:
            try:
                blob = json.loads(e.get("notes") or "{}")
            except Exception:
                blob = {}
            if not isinstance(blob, dict):
                blob = {}
            leads.append({
                "id": e.get("id"),
                "prospect_id": e.get("prospect_id"),
                "actor": e.get("actor"),
                "niche": blob.get("niche", ""),
                "name": blob.get("name") or blob.get("business_name", ""),
                "phone": blob.get("phone", ""),
                "zip": blob.get("zip", "") or blob.get("zip_code", ""),
                "metro": blob.get("metro", ""),
                "source": blob.get("source", ""),
                "details": blob.get("details", {}),
                "discovered_at": e.get("occurred_at"),
            })
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "candidate_count": len(leads),
            "leads": leads,
            "niches_known": list(NICHE_KEYWORDS.keys()),
        }

    def reason(self, state: dict) -> str:
        """Decide how many leads to process this cycle."""
        n = state["candidate_count"]
        if n == 0:
            return json.dumps({
                "action": "idle",
                "batch_size": 0,
                "use_llm": False,
                "reasoning": "no discovered leads to route",
            })
        # Use LLM if available to decide batch size
        # Cheap heuristic: cap at min(n, 20)
        cap = min(n, 20)
        use_llm = (cap >= 5)  # only call LLM when batch is meaningful
        return json.dumps({
            "action": "route",
            "batch_size": cap,
            "use_llm": use_llm,
            "reasoning": f"routing up to {cap} leads",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            d = {"action": "idle"}
        if d.get("action") != "route":
            return {"summary": "idle"}

        batch_size = int(d.get("batch_size", 0))
        use_llm = bool(d.get("use_llm", False))
        # Re-observe fresh leads (avoid stale state)
        fresh = self.observe()["leads"][:batch_size]

        routed: list[dict] = []
        parked: list[dict] = []
        rerouted: list[dict] = []

        for lead in fresh:
            analysis = analyze_lead(lead,
                                   llm=self.llm if use_llm else None)
            if analysis.recommendation == "send_to_outreach":
                post = self._post_outreach(lead, analysis.primary_niche)
                routed.append({
                    "lead_id": analysis.lead_id,
                    "niche": analysis.primary_niche,
                    "fit": analysis.primary_fit,
                    "post_result": post,
                })
            elif analysis.recommendation == "re_route":
                target = (analysis.secondary_niches[0][0]
                          if analysis.secondary_niches
                          else analysis.primary_niche)
                target_fit = (analysis.secondary_niches[0][1]
                              if analysis.secondary_niches else 0.0)
                post = self._post_outreach(lead, target)
                rerouted.append({
                    "lead_id": analysis.lead_id,
                    "from_niche": lead.get("niche"),
                    "to_niche": target,
                    "fit_at_target": round(target_fit, 3),
                    "post_result": post,
                })
            else:
                parked.append({
                    "lead_id": analysis.lead_id,
                    "niche": analysis.primary_niche,
                    "fit": analysis.primary_fit,
                    "reason": analysis.reasoning,
                })

        # Persist
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle": self.context.cycle,
            "batch_size": batch_size,
            "n_routed": len(routed),
            "n_rerouted": len(rerouted),
            "n_parked": len(parked),
            "routed": routed,
            "rerouted": rerouted,
            "parked": parked,
        }
        with ROUTED_LOG.open("a") as f:
            f.write(json.dumps(record) + "\n")

        # Alert if many parked (could mean niche definitions are off)
        if len(parked) >= max(5, batch_size // 2):
            try:
                import requests
                requests.post(
                    f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                    json={
                        "title": f"lead-handler: {len(parked)} parked",
                        "body": (f"cycle={self.context.cycle} "
                                 f"parked sample: {parked[:3]}"),
                        "severity": "warn",
                        "source": "lead-handler-agent"},
                    timeout=5)
            except Exception:
                pass

        return {
            "summary": (f"routed={len(routed)} rerouted={len(rerouted)} "
                        f"parked={len(parked)} (of {batch_size})"),
            "n_routed": len(routed),
            "n_rerouted": len(rerouted),
            "n_parked": len(parked),
        }


if __name__ == "__main__":
    agent = LeadHandlerAgent(
        name="lead-handler-agent",
        role="lead_handler",
        health_url="http://localhost:9107/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"lead-handler online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({"cycle": r.get("cycle"),
                              "summary": r.get("result", {}).get(
                                  "summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(30 * failures, 300)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
