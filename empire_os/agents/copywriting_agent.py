"""
Copywriting Agent — generates high-converting copy.
Reads AEO pages, ad-gen briefs, lead-niche context, then produces:
  - Landing page copy (hero, subhead, CTA)
  - Email subject lines
  - Ad headlines (search, social, display)
  - Form copy (button text, microcopy)

All copy is operator-reviewed before publishing. The agent drafts;
the operator approves.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = "http://127.0.0.1:8081"
TICK_INTERVAL = 900  # 15 min


class CopywritingAgent(SyntheticAgent):
    """Copy generation layer — drafts conversion copy."""

    def observe(self) -> dict:
        state = {"niches": []}

        try:
            r = urllib.request.urlopen(HUB + "/v1/aeo/pages", timeout=10)
            pages = json.loads(r.read()).get("pages", [])
            state["aeo_pages"] = [p.get("niche") for p in pages][:20]
            state["niches"] = state["aeo_pages"][:10]
        except Exception as e:
            state["error"] = str(e)

        try:
            r = urllib.request.urlopen(HUB + "/v1/leads?limit=20", timeout=10)
            leads = json.loads(r.read()).get("leads", [])
            state["recent_leads"] = [{"niche": l.get("niche")} for l in leads[:10]]
        except Exception:
            pass

        return state

    def reason(self, state: dict) -> str:
        if not state.get("niches"):
            return json.dumps({"copy": "no niches to write for"})

        system = (
            "You are a conversion copywriter for Empire OS v3 — a B2B "
            "lead-supply network. Write copy that is direct, specific, "
            "and operator-grade. No fluff. No exclamation points. Reply "
            "with JSON: {\"niche\": \"...\", \"hero\": \"...\", \"subhead\": "
            "\"...\", \"cta\": \"...\", \"subject_lines\": [3 variations]}"
        )
        prompt = (
            "Generate copy for: %s\n\nContext: B2B lead network with "
            "636 lanes across 7 categories × 6 sub-niches × 10 metros. "
            "Pages are at empire-ai.co.uk/aeo/{niche}." % state["niches"][0]
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
            copy_log = Path("/root/copywriting/copy.jsonl")
            copy_log.parent.mkdir(parents=True, exist_ok=True)
            d["ts"] = time.time()
            d["status"] = "pending-operator-review"
            with copy_log.open("a") as f:
                f.write(json.dumps(d) + "\n")
            return {"summary": "copy-drafted: %s" % d.get("niche", "")}
        except Exception as e:
            return {"summary": "copy-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/copywriting", exist_ok=True)
    agent = CopywritingAgent(
        name="copywriting-agent",
        role="copywriting",
        health_url="http://localhost:9100/health",
    )
    print("Copywriting agent starting — tick interval %ds" % TICK_INTERVAL)
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({"cycle": result.get("cycle"), "summary": result.get("result", {}).get("summary", "")}))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff, "failures": consecutive_failures}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)