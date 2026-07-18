"""
Design Agent — visual + UX + brand.
Reads AEO pages, ad creatives, landing page screenshots, and produces:
  - Design system tokens (colors, type, spacing) per niche
  - Landing page wireframes (text-block layouts)
  - Brand voice per niche (already partially handled by copywriting agent)
  - Visual QA scorecard (does this page look professional)

All output goes to pending operator review. No auto-deploy.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = "http://127.0.0.1:8000"
TICK_INTERVAL = 1200  # 20 min


class DesignAgent(SyntheticAgent):
    """Design + UX layer — proposes visuals, wireframes, tokens."""

    def observe(self) -> dict:
        state = {"pages": [], "missing": []}

        try:
            r = urllib.request.urlopen(HUB + "/v1/aeo/pages", timeout=10)
            state["pages"] = json.loads(r.read()).get("pages", [])
        except Exception as e:
            state["error"] = str(e)

        try:
            r = urllib.request.urlopen(HUB + "/health", timeout=5)
            state["hub_healthy"] = "online" in r.read().decode().lower()
        except Exception:
            state["hub_healthy"] = False

        return state

    def reason(self, state: dict) -> str:
        if not state.get("pages"):
            return json.dumps({"design": "no pages to design for"})

        system = (
            "You are a senior product designer for Empire OS v3 — a B2B "
            "lead-supply network. Produce a design spec for the next AEO "
            "page. Reply with JSON: {\"niche\": \"...\", \"palette\": "
            "[3 hex colors], \"typography\": \"headline/body fonts\", "
            "\"wireframe\": [section blocks], \"hero_image_prompt\": \"...\"}"
        )
        prompt = (
            "Design the next AEO page. Examples of existing pages: %s. "
            "Network has 636 lanes across 7 categories x 6 sub-niches x "
            "10 metros. Pages live at empire-ai.co.uk/aeo/{niche}."
            % state["pages"][:5]
        )
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.7,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            design_log = Path("/root/design/specs.jsonl")
            design_log.parent.mkdir(parents=True, exist_ok=True)
            d["ts"] = time.time()
            d["status"] = "pending-operator-review"
            with design_log.open("a") as f:
                f.write(json.dumps(d) + "\n")
            return {"summary": "design-spec: %s" % d.get("niche", "")[:50]}
        except Exception as e:
            return {"summary": "design-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/design", exist_ok=True)
    agent = DesignAgent(
        name="design-agent",
        role="design",
        health_url="http://localhost:9103/health",
    )
    print("Design agent starting — tick interval %ds" % TICK_INTERVAL)
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({"cycle": result.get("cycle"), "summary": result.get("result", {}).get("summary", "")}))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)