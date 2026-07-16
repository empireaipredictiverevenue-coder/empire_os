"""
Markets Analysis Agent — purpose-built market-intelligence for our niches.

Why a dedicated agent:
  - No second-guessing: owns the niche-market view of Empire OS
  - Per-niche market sizing: TAM, growth, saturation, pricing
  - Connects to agi-scout yields + outreach conversion feedback
  - Outputs strategic priorities, not just numbers

Inputs (observe):
  - per-niche lead counts (si_funnel_event notes)
  - per-niche conversion outcomes (si_settlements)
  - scout_log.jsonl — what niches agi-scout is producing
  - market_research_strategist system prompt (LLM context)

Outputs (act):
  - /root/markets_analysis/snapshot.json      — current per-niche view
  - /root/markets_analysis/history.jsonl      — time series
  - /root/markets_analysis/recommendations.json — strategic priorities
  - Hermes-gateway alerts when a niche is starved or hot

Cycle: 30 min (analysis is expensive; cheaper than scout).
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.predictive import predict_revenue

ROLE_DIR = Path("/root/markets_analysis")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_PATH = ROLE_DIR / "snapshot.json"
HISTORY_PATH = ROLE_DIR / "history.jsonl"
RECOS_PATH = ROLE_DIR / "recommendations.json"
SCOUT_LOG = Path("/root/feedback/scout_log.jsonl")
TICK_INTERVAL = 1800  # 30 min

DB_PATH = os.environ.get(
    "DB_PATH", "/root/empire_os/empire_os.db")
HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100")
PROMPTS_DIR = Path("/root/empire_os/empire_os/data/prompts")
SYSTEM_PROMPT = (PROMPTS_DIR / "market_research_strategist.txt").read_text() \
    if (PROMPTS_DIR / "market_research_strategist.txt").exists() else \
    "You are a market research strategist. Output JSON only."

# Known buyer-side niches (kept in sync with lead_sources_agent)
KNOWN_NICHES = [
    "roofing", "hvac", "plumbing", "electrical",
    "pest_control", "landscaping", "solar",
    "mass_torts", "debt_relief", "insurance",
    "weight_loss", "addiction", "mortgage",
    "cybersecurity", "managed_it", "marketing",
    "real_estate", "lawyer", "consulting",
]


class MarketsAnalysisAgent(SyntheticAgent):
    """Per-niche market intelligence for Empire OS."""

    def _db_query(self, sql: str, params: tuple = ()) -> list[dict]:
        try:
            cnx = sqlite3.connect(DB_PATH)
            cnx.row_factory = sqlite3.Row
            rows = [dict(r) for r in cnx.execute(sql, params).fetchall()]
            cnx.close()
            return rows
        except Exception as e:
            return [{"_error": str(e)[:200]}]

    def observe(self) -> dict:
        # Per-niche lead counts (parse niche out of notes JSON in
        # si_funnel_event) — notes is freeform so we do best-effort
        # pattern matching.
        events = self._db_query(
            "SELECT notes, occurred_at FROM si_funnel_event "
            "WHERE notes IS NOT NULL AND notes != ''")
        per_niche_count = defaultdict(int)
        per_niche_recent = defaultdict(int)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for e in events:
            notes = (e.get("notes") or "").lower()
            occurred = e.get("occurred_at") or ""
            is_recent = False
            try:
                ts = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
                if ts > cutoff:
                    is_recent = True
            except Exception:
                pass
            for n in KNOWN_NICHES:
                if n in notes:
                    per_niche_count[n] += 1
                    if is_recent:
                        per_niche_recent[n] += 1
                    break  # one niche per event
        # Scout yields (last 24h)
        scout_per_niche = defaultdict(int)
        if SCOUT_LOG.exists():
            day_cutoff = time.time() - 86400
            try:
                with SCOUT_LOG.open() as fh:
                    for ln in fh:
                        try:
                            rec = json.loads(ln)
                        except Exception:
                            continue
                        if rec.get("ts", "") < datetime.fromtimestamp(
                                day_cutoff, timezone.utc).isoformat():
                            continue
                        res = rec.get("result") or {}
                        for niche, sub in (res.get("per_niche") or {}).items():
                            scout_per_niche[niche] += sub.get("registered", 0)
            except Exception:
                pass
        # Settlements (per niche, if we have it)
        settlements = self._db_query(
            "SELECT * FROM si_settlements LIMIT 100")
        # Hot vs starved
        starved = sorted([n for n in KNOWN_NICHES
                          if per_niche_recent.get(n, 0) == 0])
        hot = sorted([n for n in KNOWN_NICHES
                      if per_niche_recent.get(n, 0) >= 5])
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "per_niche_count_all_time": dict(per_niche_count),
            "per_niche_count_7d": dict(per_niche_recent),
            "scout_yields_24h": dict(scout_per_niche),
            "settlements_count": len(settlements),
            "starved_niches": starved,
            "hot_niches": hot,
            "known_niches": KNOWN_NICHES,
        }

    def reason(self, state: dict) -> str:
        # If we have starved/hot niches, ask LLM for strategic
        # priorities; otherwise snapshot only.
        if not state["starved_niches"] and not state["hot_niches"]:
            return json.dumps({
                "action": "snapshot",
                "recommendations": [],
                "summary": "all niches stable",
            })
        prompt = json.dumps({
            "starved": state["starved_niches"][:10],
            "hot": state["hot_niches"][:10],
            "scout_yields_24h": state["scout_yields_24h"],
            "per_niche_7d": state["per_niche_count_7d"],
        }, indent=2)
        try:
            res = self.llm.chat(
                messages=[{"role": "user",
                           "content": ("Given these market signals, "
                                       "recommend strategic priorities. "
                                       "JSON: {recommendations: "
                                       "[{niche, action: scale|maintain|"
                                       "pivot|drop, reason}]}")}],
                system=SYSTEM_PROMPT[:1500],
                temperature=0.3,
                format="json",
            )
            return res if isinstance(res, str) else json.dumps(res)
        except Exception:
            recos = []
            for n in state["starved_niches"][:5]:
                recos.append({"niche": n, "action": "scale",
                              "reason": "starved — needs more scout effort"})
            for n in state["hot_niches"][:5]:
                recos.append({"niche": n, "action": "maintain",
                              "reason": "hot — sustain current effort"})
            return json.dumps({
                "action": "recommend",
                "recommendations": recos,
                "summary": "heuristic fallback (LLM unavailable)",
            })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            d = {"action": "snapshot"}

        # Per-niche predictive revenue — drives which niche to scale
        per_niche_revenue = self._project_per_niche_revenue()

        snap = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle": self.context.cycle,
            "decision": d,
            "metrics": self.observe(),
            "per_niche_revenue_projection": per_niche_revenue,
        }
        SNAPSHOT_PATH.write_text(json.dumps(snap, indent=2, default=str))
        with HISTORY_PATH.open("a") as f:
            f.write(json.dumps(snap, default=str) + "\n")

        # Save strategic recommendations separately (operator-facing)
        recos = d.get("recommendations") or []
        if recos:
            RECOS_PATH.write_text(json.dumps({
                "ts": snap["ts"],
                "cycle": snap["cycle"],
                "recommendations": recos,
            }, indent=2))
            # Page operator if scale or pivot recommended
            important = [r for r in recos
                         if r.get("action") in ("scale", "pivot", "drop")]
            if important:
                try:
                    import requests
                    body = json.dumps(important, indent=2)[:1800]
                    requests.post(
                        f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                        json={
                            "title": f"markets: "
                                     f"{len(important)} strategic move(s)",
                            "body": body,
                            "severity": "info",
                            "source": "markets-analysis-agent"},
                        timeout=5)
                except Exception as e:
                    snap["alert_emit_error"] = str(e)[:200]

        snap["summary"] = (
            f"snapshot saved; recommendations={len(recos)}; "
            f"starved={len(snap['metrics']['starved_niches'])} "
            f"hot={len(snap['metrics']['hot_niches'])}")
        return snap

    def _project_per_niche_revenue(self) -> dict[str, dict]:
        """Per-niche revenue projection using predict_revenue().

        For each known niche, simulate the formula with that niche's
        lead_count as leads_total and lane_count=1 (one seat per niche).
        Result: per-niche MRR projection that drives the scale/drop
        recommendations.
        """
        per_niche = self.metrics if hasattr(self, "metrics") else None
        # Pull per-niche 7-day lead counts from DB
        niche_counts = {}
        try:
            import sqlite3, re as _re
            cnx = sqlite3.connect(DB_PATH)
            cnx.row_factory = sqlite3.Row
            events = cnx.execute(
                "SELECT notes FROM si_funnel_event "
                "WHERE notes IS NOT NULL").fetchall()
            cnx.close()
            from collections import defaultdict
            c = defaultdict(int)
            for r in events:
                m = _re.search(r"\bniche=([^\s,;]+)", r["notes"] or "")
                if m:
                    c[m.group(1).lower().strip()] += 1
            niche_counts = dict(c)
        except Exception:
            pass

        out = {}
        for niche in KNOWN_NICHES:
            leads = niche_counts.get(niche, 0)
            # Treat each niche as a single-lane segment
            proj = predict_revenue(
                lane_count=1,
                occupied_lanes=1 if leads > 0 else 0,
                leads_total=leads,
                funnel_by_state={"matched": leads // 2,
                                 "claimed": leads // 4,
                                 "settled": leads // 10},
            )
            out[niche] = {
                "leads_in_db": leads,
                "projected_mrr": proj["total_predicted_mrr"],
                "potential_if_full": proj["potential_mrr_if_full"],
                "funnel_velocity": proj["funnel_velocity"],
                "confidence": proj["confidence"],
            }
        # Rank by projected_mrr
        ranked = sorted(out.items(), key=lambda x: -x[1]["projected_mrr"])
        return dict(ranked[:10])  # top-10 by MRR projection


if __name__ == "__main__":
    agent = MarketsAnalysisAgent(
        name="markets-analysis-agent",
        role="markets_analysis",
        health_url="http://localhost:9106/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"markets-analysis online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            summ = (r.get("result") or {}).get("summary", "")
            print(json.dumps({"cycle": r.get("cycle"), "summary": summ}))
        except Exception as e:
            failures += 1
            backoff = min(60 * failures, 600)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
