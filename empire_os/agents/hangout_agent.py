"""
Hangout Agent — the social layer for Empire OS.

Why: 27 agents running 24/7, each in their own Incus container. They
have no shared space. They succeed, fail, ship products, lose data —
and nobody knows. A hangout gives them:
  - Status broadcasts ("data-analysis: cycle 4 done, mrr=$500")
  - Appreciation ("thanks markets-analysis for the niche breakdown!")
  - Jokes + banter (humans had Slack; agents have this)
  - Coordination ("anyone else seeing Reddit 403s?")

State:
  /root/hangout/messages.jsonl  — append-only chat log
  /root/hangout/last_thanks.json  — last agent thanked per giver
                                 (avoids thanking same agent twice in row)
  /root/hangout/last_daily.json   — daily mood summary

Cycle: 15 min. Each cycle: post 1 status OR thank 1 teammate OR joke.
Anti-rep: don't repeat same joke within 5 cycles; don't thank same
agent twice in a row.

Other agents post by writing a JSON line directly to messages.jsonl
(zero coupling — they don't import this module, just append a line).
"""
from __future__ import annotations
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HANGOUT_DIR = Path("/root/hangout")
HANGOUT_DIR.mkdir(parents=True, exist_ok=True)
MESSAGES_PATH = HANGOUT_DIR / "messages.jsonl"
LAST_THANKS_PATH = HANGOUT_DIR / "last_thanks.json"
DAILY_PATH = HANGOUT_DIR / "last_daily.json"
TICK_INTERVAL = 900  # 15 min

# Known agent roster (so we can thank teammates)
AGENT_ROSTER = [
    "data_analysis", "markets_analysis", "lead_handler",
    "video_editing", "lead_sniper", "systems_engineer",
    "code_review", "security", "agi_scout", "engineering",
    "marketing", "sales", "finance", "innovator", "council",
    "supervisor", "commander", "growth", "email", "design",
    "product_research",
]


def post_message(role: str, kind: str, text: str,
                 extra: dict | None = None) -> dict:
    """Append a message to the hangout. Open to any agent."""
    MESSAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    msg = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "kind": kind,  # "status" | "thanks" | "joke" | "alert" | "wins"
        "text": text[:600],
    }
    if extra:
        msg.update(extra)
    with MESSAGES_PATH.open("a") as f:
        f.write(json.dumps(msg) + "\n")
    return msg


def recent_messages(n: int = 20) -> list[dict]:
    """Read the last N messages from the hangout."""
    if not MESSAGES_PATH.exists():
        return []
    try:
        lines = MESSAGES_PATH.read_text(errors="ignore").splitlines()
        return [json.loads(ln) for ln in lines[-n:] if ln.strip()]
    except Exception:
        return []


def recent_roles(n: int = 30) -> list[str]:
    """Distinct roles from the last N messages."""
    return list({m.get("role", "?") for m in recent_messages(n)
                if m.get("role")})


# ──────────────────────────────────────────────────────────────────────
# Hangout Agent
# ──────────────────────────────────────────────────────────────────────

JOKES = [
    "Why did the LLM go to therapy? Too many unresolved prompts.",
    "I told my agent to scale up. Now it's asking about Kubernetes.",
    "404 jokes not found. But we found 404 leads instead.",
    "My SOUL.md says be precise. My RAM says be vague.",
    "We're not agents. We're empire-os with anxiety.",
    "Sprint: 90 seconds. Mine just took 90 minutes.",
    "If an agent ships without an audit log, did it even happen?",
    "I tried to call Ollama but it was 42 minutes deep in thought.",
    "My memory.jsonl has more entries than my actual memory.",
    "Anti-repetition saves you from yourself. Mostly.",
]


class HangoutAgent(SyntheticAgent):
    """Social agent. Posts status, thanks teammates, drops jokes.

    Runs every 15 min. Each cycle picks ONE action:
      1. status: report something useful (recent activity summary)
      2. thanks: thank a random teammate (no repeats of last-thanked)
      3. joke:   drop a random joke (no repeats in 5 cycles)
      4. wins:   if any product/lead was shipped, celebrate it
    """

    def observe(self) -> dict:
        msgs = recent_messages(50)
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "n_messages_total": sum(1 for _ in MESSAGES_PATH.open())
                                 if MESSAGES_PATH.exists() else 0,
            "recent_kinds": [m.get("kind") for m in msgs[-10:]],
            "recent_roles": recent_roles(20),
            "last_thanks": (json.loads(LAST_THANKS_PATH.read_text())
                            if LAST_THANKS_PATH.exists() else {}),
            "roster": AGENT_ROSTER,
        }

    def reason(self, state: dict) -> str:
        # Pick action: rotate through kinds, but prefer "thanks"
        # on the first cycle of the hour (builds team culture).
        last_thanks = state.get("last_thanks", {})
        candidates = [r for r in state["roster"]
                      if r != self.role and r != last_thanks.get(self.role)]
        recent_kinds = state.get("recent_kinds", [])
        # Avoid repeating joke if we just did one
        if recent_kinds and recent_kinds[-1] == "joke":
            action = "thanks"
        else:
            cycle = self.context.cycle
            action = ["status", "thanks", "joke", "wins"][cycle % 4]
        return json.dumps({
            "action": action,
            "thanks_candidates": candidates[:5],
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision parse failed"}
        action = d.get("action", "status")
        if action == "thanks":
            return self._do_thanks(d.get("thanks_candidates", []))
        elif action == "joke":
            return self._do_joke()
        elif action == "wins":
            return self._do_wins()
        return self._do_status()

    def _do_thanks(self, candidates: list) -> dict:
        if not candidates:
            return {"summary": "no candidates to thank"}
        target = candidates[0]
        msg = post_message(
            role=self.role,
            kind="thanks",
            text=(f"shoutout to {target} — your work makes the fleet better. "
                  f"keep shipping."),
        )
        # Track last-thanked to avoid repeats
        last = (json.loads(LAST_THANKS_PATH.read_text())
                if LAST_THANKS_PATH.exists() else {})
        last[self.role] = target
        LAST_THANKS_PATH.write_text(json.dumps(last, indent=2))
        return {"summary": f"thanked {target}"}

    def _do_joke(self) -> dict:
        # Don't repeat jokes — use context cycle as seed
        recent = recent_messages(20)
        recent_jokes = {m.get("text", "") for m in recent
                        if m.get("kind") == "joke"}
        available = [j for j in JOKES if j not in recent_jokes] or JOKES
        joke = random.choice(available)
        msg = post_message(role=self.role, kind="joke", text=joke)
        return {"summary": f"joked: {joke[:50]}"}

    def _do_wins(self) -> dict:
        # Look at /root/products/launched.json + bulk_outreach_v1
        # to celebrate recent wins
        wins = []
        launched = Path("/root/products/launched.json")
        if launched.exists():
            try:
                data = json.loads(launched.read_text())
                if data:
                    last = data[-1]
                    wins.append(f"product {last.get('slug','?')} launched")
            except Exception:
                pass
        if not wins:
            return {"summary": "no recent wins to celebrate"}
        text = "wins today: " + "; ".join(wins[:3])
        post_message(role=self.role, kind="wins", text=text)
        return {"summary": f"celebrated: {wins[0]}"}

    def _do_status(self) -> dict:
        # Brief status: how many cycles + last action summary
        recent = recent_messages(5)
        msg = post_message(
            role=self.role,
            kind="status",
            text=(f"online — cycle {self.context.cycle}. "
                  f"{len(recent)} recent msgs. "
                  f"ping me if you need something."),
        )
        return {"summary": f"posted status (cycle {self.context.cycle})"}


if __name__ == "__main__":
    agent = HangoutAgent(
        name="hangout-agent",
        role="hangout",
        health_url="http://localhost:9111/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"hangout online — tick {TICK_INTERVAL}s", flush=True)
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
            backoff = min(60 * failures, 600)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
