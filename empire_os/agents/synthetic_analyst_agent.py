#!/usr/bin/env python3
"""
Synthetic Analyst - Station 1 of the AGI Swarm.

In role in the self-discovery loop:
  Step B: ingest MarketOpportunityFound events emitted by the
  Keyword Expert. Use LLM (qwen2.5:7b via Ollama) to perform an
  'Ugly Banner' gap analysis on the niche. Output a Directive JSON
  that downstream Design/List stations pick up.

Schema per spec:
{
    "niche_analysis": {
        "niche_id": "uuid",
        "market_gap": "identifies low-quality competition",
        "profit_margin_score": 0.85,
        "suggested_platform": "etsy"
    },
    "directive_payload": {
        "style_prompt": "...",
        "listing_metadata": {...}
    }
}

HITL gate: if profit_margin_score > 0.9, status=pending_approval.
Operators must approve before Design/List stations execute.
"""
from __future__ import annotations
import json, re, sys, time, uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.skills_library import skills_context_for_role

WORKDIR = Path("/root/swarms")
EVENTS_LOG = WORKDIR / "events.jsonl"
DIRECTIVES_LOG = WORKDIR / "directives.jsonl"
APPROVAL_LOG = WORKDIR / "approvals.jsonl"
TICK_INTERVAL = 300  # 5 min (poll new events often)

HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")


def poll_events_from_hub(limit: int = 50) -> list[dict]:
    """Poll /v1/swarms/events on the hub. Falls back to local file
    if hub unreachable (so agents can run isolated too)."""
    try:
        import requests as _req
        r = _req.get(f"{HUB_URL}/v1/swarms/events", timeout=4)
        if r.status_code == 200:
            return r.json().get("events", [])
    except Exception:
        pass
    # Local fallback
    if not EVENTS_LOG.exists():
        return []
    out = []
    for line in EVENTS_LOG.read_text().splitlines()[-limit:]:
        try:
            d = json.loads(line)
            if d.get("event_type") == "MarketOpportunityFound":
                out.append(d)
        except Exception:
            continue
    return out

# Plausible platform mappings per niche family
PLATFORM_DEFAULTS = {
    "roofing": ["angi", "thumbtack", "homeadvisor"],
    "hvac": ["angi", "homeadvisor"],
    "plumbing": ["angi", "homeadvisor", "thumbtack"],
    "electrical": ["angi", "homeadvisor"],
    "pest_control": ["angi", "thumbtack"],
    "mass_torts": ["facebook_ads", "google_ads"],
    "weight_loss": ["amazon", "clickbank", "facebook_ads"],
    "cybersecurity": ["digitalocean_marketplace", "partnerstack"],
    "default": ["facebook_ads", "google_ads", "angi"],
}


def _list_platforms_for(niche):
    return PLATFORM_DEFAULTS.get(niche, PLATFORM_DEFAULTS["default"])


def _parse_event(line):
    try:
        return json.loads(line)
    except Exception:
        return None


def _run_llm_directive(event) -> dict:
    """Call qwen2.5:7b to produce Directive JSON. Heuristic fallback
    if Ollama times out - so the loop never starves."""
    llm = OllamaClient(model="qwen2.5:7b")
    niche = event.get("niche", "")
    trend_count = event.get("trend_count", 0)
    trends = event.get("trends", [])
    trend_titles = [t.get("trend_title", "") for t in trends[:3]]
    prompt = f"""You are a market analyst. Niche: {niche}. Recent Google Trends hits ({trend_count}):
{chr(10).join(trend_titles)}

Identify the lowest-quality competition gap (the 'Ugly Banner' effect -
pages with bad copy / bad design that leave room for quality entrants).
Output JSON ONLY, no prose:
{{"market_gap":"...","profit_margin_score":0.0-1.0,"suggested_platform":"etsy|amazon|angi|homeadvisor|thumbtack|clickbank|facebook_ads|google_ads|digitalocean_marketplace","rationale":"..."}}"""
    raw = ""
    try:
        raw = llm.chat(
            [{"role": "user", "content": prompt}],
            timeout=30, max_tokens=300)
        raw = raw.strip()
    except Exception:
        raw = ""
    # Try parse JSON
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            analysis = json.loads(m.group(0))
        except Exception:
            analysis = {}
    else:
        analysis = {}
    # Heuristic fallback when LLM doesn't parse
    if not analysis or "profit_margin_score" not in analysis:
        pms = min(0.95, 0.45 + trend_count * 0.05)
        analysis = {
            "market_gap": (f"{niche}: low-quality competition in top "
                          f"{trend_count} trends, room for quality entrant"),
            "profit_margin_score": round(pms, 2),
            "suggested_platform": _list_platforms_for(niche)[0],
            "rationale": "heuristic fallback (LLM empty/timeout)",
        }
    # clamp
    analysis["profit_margin_score"] = round(
        float(analysis.get("profit_margin_score", 0.5)), 2)
    # HITL gate
    needs_approval = analysis["profit_margin_score"] >= 0.90
    return {
        "niche_analysis": {
            "niche_id": event.get("niche_id"),
            "niche": niche,
            "market_gap": analysis.get("market_gap", ""),
            "profit_margin_score": analysis["profit_margin_score"],
            "suggested_platform": analysis.get("suggested_platform", "facebook_ads"),
            "rationale": analysis.get("rationale", ""),
        },
        "directive_payload": {
            "style_prompt": (
                f"Clean modern banner for {niche} niche. "
                f"Gap framing: {analysis.get('market_gap', '')[:120]}. "
                f"Avoid stock-photo cliche; lean to before/after "
                f"transformation or quantified result."
            ),
            "listing_metadata": {
                "platform_target": analysis.get("suggested_platform"),
                "niche_id": event.get("niche_id"),
                "platforms_options": _list_platforms_for(niche),
                "trend_count": trend_count,
            },
        },
        "workflow_state": "pending_approval" if needs_approval else "ready",
        "needs_approval": needs_approval,
    }


def emit_directive(directive: dict):
    DIRECTIVES_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "directive": directive,
    }
    with DIRECTIVES_LOG.open("a") as f:
        f.write(json.dumps(rec) + chr(10))
    return rec


class SyntheticAnalystAgent(SyntheticAgent):
    """Station 1 - polls events.jsonl, runs directive, gates HITL."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._processed_event_ids = deque(maxlen=500)
        # Seed from existing directives log so restarts don't reprocess
        if DIRECTIVES_LOG.exists():
            try:
                for line in DIRECTIVES_LOG.read_text().splitlines()[-100:]:
                    rec = json.loads(line)
                    nid = (rec.get("directive", {})
                           .get("niche_analysis", {})
                           .get("niche_id"))
                    if nid:
                        self._processed_event_ids.append(nid)
            except Exception:
                pass

    def observe(self) -> dict:
        events = poll_events_from_hub(limit=50)
        n_pending = sum(1 for e in events
                       if e.get("event_type") == "MarketOpportunityFound"
                       and e.get("niche_id")
                       not in self._processed_event_ids)
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "events_to_process": n_pending,
            "n_processed": len(self._processed_event_ids),
        }

    def reason(self, state: dict) -> str:
        if state.get("events_to_process", 0) > 0:
            return json.dumps({"action": "process_pending"})
        return json.dumps({"action": "idle"})

    def _audit_compat(self, event: dict):
        """Safe-dispatch - v2 base may or may not expose _audit.
        Fall back to a JSONL in /root/swarms/audit.jsonl."""
        try:
            return self._audit(event)
        except AttributeError:
            try:
                audit_log = WORKDIR / "audit.jsonl"
                audit_log.parent.mkdir(parents=True, exist_ok=True)
                line = {"ts": datetime.now(timezone.utc).isoformat(),
                        "role": self.role, "cycle": self.context.cycle,
                        **event}
                with audit_log.open("a") as f:
                    f.write(json.dumps(line) + chr(10))
            except Exception:
                pass

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision parse failed"}
        if d.get("action") != "process_pending":
            return {"summary": "idle"}
        # Pull events from hub
        events = poll_events_from_hub(limit=50)
        processed = 0
        for evt in events:
            if (evt.get("event_type") != "MarketOpportunityFound"
                    or evt.get("niche_id") in self._processed_event_ids):
                continue
            try:
                directive = _run_llm_directive(evt)
                emit_directive(directive)
                self._processed_event_ids.append(evt["niche_id"])
                processed += 1
                self._audit_compat({
                    "event": "directive_emitted",
                    "niche_id": evt["niche_id"],
                    "niche": evt.get("niche"),
                    "score": directive["niche_analysis"]
                                          ["profit_margin_score"],
                    "workflow_state": directive["workflow_state"],
                })
                break
            except Exception as e:
                self._audit_compat({
                    "event": "directive_failed",
                    "niche_id": evt.get("niche_id"),
                    "err": str(e)[:200],
                })
                return {"summary": f"failed: {str(e)[:80]}"}
        return {"summary": f"processed {processed}", "n": processed}


if __name__ == "__main__":
    agent = SyntheticAnalystAgent(
        name="synthetic-analyst-agent",
        role="synthetic_analyst",
        health_url="http://localhost:9114/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"synthetic-analyst online - tick {TICK_INTERVAL}s",
          flush=True)
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
