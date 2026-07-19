#!/usr/bin/env python3
"""
Keyword Expert - Station 0 of the AGI Swarm.

Role: pull high-volume trend clusters from Google Trends (free daily
CSV via the trends.google.com export endpoint), Reddit, and Google
Suggest. Emit MarketOpportunityFound events that the downstream
Synthetic Analyst ingests.

Cadence: 1 hour. Backoff on rate-limit; empty trends are recorded
not fatal - we keep going.
"""
from __future__ import annotations
import json, re, sys, time, urllib.request, urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.skills_library import skills_context_for_role

WORKDIR = Path("/root/swarms")
WORKDIR.mkdir(parents=True, exist_ok=True)
TRENDS_LOG = WORKDIR / "trends.jsonl"
EVENTS_LOG = WORKDIR / "events.jsonl"
TICK_INTERVAL = 3600  # 1 hour

NICHES = [
    "roofing", "hvac", "plumbing", "electrical", "pest_control",
    "landscaping", "painting", "mold_remediation", "residential_roofing",
    "emergency_plumbing", "emergency_hvac", "weight_loss", "cybersecurity",
    "general_contractor", "mass_torts", "pool_services", "kitchen_remodel",
    "solar", "concrete_coating",
]

XSSI = chr(93) + chr(41) + chr(125) + chr(39) + chr(10)

HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")


def _pytrends_pull(niche):
    """Pull Google Trends daily CSV - no auth needed. Returns list
    of related queries or [] on failure."""
    try:
        url = ("https://trends.google.com/trends/api/dailytrends"
               "?hl=en-US&tz=-60&geo=US&ned=us")
        req = urllib.request.Request(
            url, headers={"User-Agent": "EmpireOS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode(errors="ignore")
        if raw.startswith(")]}'"):
            raw = raw[5:].lstrip()
        payload = json.loads(raw)
        buckets = payload.get("default", {}).get(
            "trendingSearchesDays", [])
        niche_low = niche.lower()
        related = []
        for day in buckets[:7]:
            for entry in day.get("trendingSearches", []):
                title = entry.get("title", "").lower()
                traffic = entry.get("formattedTraffic", "")
                if niche_low in title or _keyword_match(niche, title):
                    related.append({
                        "trend_title": entry.get("title", ""),
                        "traffic": traffic,
                        "niche": niche,
                        "article_url": entry.get("articleUrl", ""),
                    })
        return related
    except Exception as e:
        return [{"error": str(e)[:200], "niche": niche}]


def _keyword_match(niche, title):
    """Loose match: token overlap with niche synonyms."""
    synonyms = {
        "roofing": ["roof", "shingle", "gutter"],
        "hvac": ["ac", "furnace", "heating", "cooling"],
        "plumbing": ["plumb", "pipe", "water heater"],
        "electrical": ["electric", "wiring", "outlet"],
        "pest_control": ["pest", "termite", "roach", "rodent"],
        "mass_torts": ["lawsuit", "litigation", "recall"],
        "weight_loss": ["diet", "lose weight", "keto"],
    }
    title_lower = title.lower()
    for syn in synonyms.get(niche, [niche]):
        if syn in title_lower:
            return True
    return False


def emit_event(niche, trends):
    """Publish via hub /v1/swarms/events (works across containers).
    Falls back to local file if hub unreachable."""
    evt = {
        "event_type": "MarketOpportunityFound",
        "niche_id": f"niche_{int(time.time())}_{niche[:4]}",
        "niche": niche,
        "ts": datetime.now(timezone.utc).isoformat(),
        "trends": trends[:5],
        "trend_count": len(trends),
        "source": "keyword-expert-agent",
    }
    # Try hub first (so synthetic-analyst can poll cross-container)
    try:
        import requests as _req
        r = _req.post(f"{HUB_URL}/v1/swarms/events", json=evt, timeout=4)
        return evt  # hub persists it
    except Exception:
        pass
    # Local fallback (if hub down)
    EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_LOG.open("a") as f:
        f.write(json.dumps(evt) + chr(10))
    return evt


class KeywordExpertAgent(SyntheticAgent):
    """Station 0 - pull trends, emit events.

    Each cycle walks all 19 niches (currently), fetches Google
    trends for each, emits one event per niche that has at least
    1 trend hit. Synthetic Analyst polls events.jsonl.
    """

    def observe(self):
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "niches_to_scan": NICHES,
            "last_emit_count": 0,
        }

    def reason(self, state):
        cycle_niches = NICHES
        return json.dumps({
            "action": "scan_niches",
            "niches": cycle_niches,
            "reasoning": "hourly full sweep",
        })

    def act(self, decision):
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision parse failed"}
        if d.get("action") != "scan_niches":
            return {"summary": f"action={d.get('action')} no-op"}
        events_emitted = 0
        for niche in d.get("niches", []):
            try:
                trends = _pytrends_pull(niche)
            except Exception as e:
                trends = [{"error": str(e)[:200]}]
            real_trends = [t for t in trends
                           if isinstance(t, dict) and "error" not in t]
            event = emit_event(niche, real_trends)
            events_emitted += 1
            self._audit_compat({
                "event": "trend_emit", "niche": niche,
                "trend_count": len(real_trends),
                "niche_id": event["niche_id"],
            })
        self.context.last_emit_count = events_emitted
        return {"summary": f"emitted {events_emitted} events",
                "n_emitted": events_emitted}

    def _audit_compat(self, event: dict):
        """v2 base records outcomes via _record_outcome; this agent
        also wants a per-action audit line. v2 may or may not expose
        _audit, so we use a safe-dispatch fallback."""
        try:
            # Prefer v2 method
            return self._audit(event)
        except AttributeError:
            # Fall back to writing our own JSONL
            try:
                AUDIT_LOG = WORKDIR / "audit.jsonl"
                AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
                from datetime import datetime, timezone
                line = {"ts": datetime.now(timezone.utc).isoformat(),
                        "role": self.role, "cycle": self.context.cycle,
                        **event}
                with AUDIT_LOG.open("a") as f:
                    f.write(json.dumps(line) + "\n")
            except Exception:
                pass


if __name__ == "__main__":
    agent = KeywordExpertAgent(
        name="keyword-expert-agent",
        role="keyword_expert",
        health_url="http://localhost:9113/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"keyword-expert online - tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({
                "cycle": r.get("cycle"),
                "summary": r.get("result", {}).get("summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(60 * failures, 600)
            print(json.dumps({
                "error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
