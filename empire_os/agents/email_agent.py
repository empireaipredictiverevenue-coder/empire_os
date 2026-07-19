"""
Email Agent — drafts and queues outreach emails.
Watches the funnel for `outreach_drafted` and `outreach_sent` states,
drafts personalization tokens, queues emails for operator approval.

Will NOT auto-send. Every email sits in a pending queue until the
operator hits approve. (Sending infrastructure = Resend/SMTP/Postmark
can be wired into the act() handler once operator picks a provider.)
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
TICK_INTERVAL = 600  # 10 min


class EmailAgent(SyntheticAgent):
    """Email outreach layer — drafts + queues for approval."""

    def observe(self) -> dict:
        state = {"drafts_needed": [], "sent_today": 0}

        try:
            r = urllib.request.urlopen(HUB + "/v1/funnel/states?state=outreach_drafted&limit=30", timeout=10)
            state["drafts_needed"] = json.loads(r.read()).get("prospects", [])
        except Exception as e:
            state["error"] = str(e)

        sent_log = Path("/root/email/sent.jsonl")
        if sent_log.exists():
            with sent_log.open() as f:
                state["sent_today"] = sum(1 for _ in f)

        return state

    def reason(self, state: dict) -> str:
        drafts = state.get("drafts_needed", [])
        if not drafts:
            return json.dumps({"emails": []})

        system = (
            "You are the Email Agent for Empire OS v3 — a B2B lead-"
            "supply network. Draft personalized outreach emails for "
            "leads that are ready for follow-up. Tone: confident, "
            "specific, low-friction. Reply with JSON: "
            '{"emails": [{"lead_id": "...", "subject": "...", "body": "..."}]}'
        )
        prompt = "Drafts needed for %d leads: %s" % (
            len(drafts),
            json.dumps([d.get("prospect_id") for d in drafts[:5]]),
        )
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.6,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            emails = d.get("emails", [])
            if not emails:
                return {"summary": "no-emails-to-draft"}

            queue_log = Path("/root/email/queue.jsonl")
            queue_log.parent.mkdir(parents=True, exist_ok=True)

            for email in emails:
                email["queued_at"] = time.time()
                email["status"] = "pending-operator-approval"
                with queue_log.open("a") as f:
                    f.write(json.dumps(email) + "\n")

            return {"summary": "queued-%d-emails" % len(emails), "count": len(emails)}
        except Exception as e:
            return {"summary": "email-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/email", exist_ok=True)
    agent = EmailAgent(
        name="email-agent",
        role="email",
        health_url="http://localhost:9101/health",
    )
    print("Email agent starting — tick interval %ds" % TICK_INTERVAL)
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