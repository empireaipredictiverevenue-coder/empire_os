"""
Conversion Expert Agent — A/B testing + landing page optimization +
CRO (conversion rate optimization). Reads page analytics + lead
conversion data and proposes experiments for the operator to run.

The agent designs tests, the operator deploys. Results are tracked
in /root/conversion/experiments.jsonl.
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
TICK_INTERVAL = 3600  # 1h


class ConversionExpertAgent(SyntheticAgent):
    """CRO layer — proposes A/B tests + landing page experiments."""

    def observe(self) -> dict:
        state = {"pages": [], "low_converting": []}

        try:
            r = urllib.request.urlopen(HUB + "/v1/aeo/pages", timeout=10)
            pages = json.loads(r.read()).get("pages", [])
            state["pages"] = [p.get("niche") for p in pages]
        except Exception as e:
            state["error"] = str(e)

        try:
            r = urllib.request.urlopen(HUB + "/v1/funnel/counts", timeout=5)
            counts = json.loads(r.read())
            discovered = counts.get("discovered", 0)
            matched = counts.get("matched", 0)
            if discovered > 5 and matched / max(discovered, 1) < 0.3:
                state["low_converting"].append({
                    "stage": "discovered → matched",
                    "rate": round(matched / max(discovered, 1), 2),
                    "action": "improve routing/scoring",
                })
        except Exception:
            pass

        return state

    def reason(self, state: dict) -> str:
        if not state.get("pages"):
            return json.dumps({"experiment": "no pages to test"})

        system = (
            "You are the Conversion Expert for Empire OS v3 — a B2B "
            "lead network. Design ONE A/B test that could lift conversion. "
            "Reply with JSON: {\"experiment_name\": \"...\", "
            "\"hypothesis\": \"...\", \"variant_a\": \"...\", "
            "\"variant_b\": \"...\", \"success_metric\": \"...\", "
            "\"min_sample_size\": N}"
        )
        prompt = "Pages: %d. Low converting stages: %s" % (
            len(state.get("pages", [])),
            json.dumps(state.get("low_converting", [])),
        )
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.5,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            out = Path("/root/conversion/experiments.jsonl")
            out.parent.mkdir(parents=True, exist_ok=True)
            d["ts"] = time.time()
            d["status"] = "pending-operator-review"
            with out.open("a") as f:
                f.write(json.dumps(d) + "\n")
            return {"summary": "experiment: %s" % d.get("experiment_name", "")[:50]}
        except Exception as e:
            return {"summary": "conversion-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/conversion", exist_ok=True)
    agent = ConversionExpertAgent(
        name="conversion-agent",
        role="conversion",
        health_url="http://localhost:9106/health",
    )
    print("Conversion expert agent starting — tick interval %ds" % TICK_INTERVAL)
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